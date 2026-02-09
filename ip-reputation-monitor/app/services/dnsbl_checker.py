"""DNSBL checker service with async DNS queries, caching, and rate limiting."""

import asyncio
import ipaddress
import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

import aiohttp
import dns.asyncresolver
from cachetools import TTLCache
from dns.exception import DNSException, NXDOMAIN, Timeout
from dns.resolver import NoAnswer

from app.core.config import settings


@dataclass
class CheckResult:
    """Result of a DNSBL check."""
    zone: str
    status: str  # 'listed', 'not_listed', 'error', 'blocked'
    a_records: List[str]
    txt_records: List[str]
    error_reason: Optional[str] = None


@dataclass
class TargetResult:
    """Aggregate results for a target."""
    target: str
    target_type: str
    listed: List[Dict]
    blocked: List[Dict]
    errors: List[Dict]
    not_listed_zones_count: int


class RateLimiter:
    """Per-zone rate limiter."""

    def __init__(self, max_requests_per_second: int = 10):
        self.max_requests = max_requests_per_second
        self.requests: Dict[str, List[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def acquire(self, zone: str) -> None:
        """Acquire permission to query a zone."""
        async with self._lock:
            now = datetime.now().timestamp()
            # Clean old requests
            cutoff = now - 1.0  # Keep only requests from the last second
            self.requests[zone] = [t for t in self.requests[zone] if t > cutoff]

            if len(self.requests[zone]) >= self.max_requests:
                # Wait until we can make a request
                sleep_time = self.requests[zone][0] - cutoff
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                    # Clean again after sleeping
                    self.requests[zone] = [t for t in self.requests[zone] if t > cutoff]

            self.requests[zone].append(now)


class DNSBLChecker:
    """DNSBL checker with caching and rate limiting."""

    def __init__(
        self,
        ttl_minutes: int = None,
        max_cache_size: int = None,
        per_zone_rate_limit: int = None,
        timeout_ms: int = None,
        dns_nameservers: List[str] = None,
    ):
        self.ttl_minutes = ttl_minutes or settings.CACHE_TTL_MINUTES
        self.cache_ttl = timedelta(minutes=self.ttl_minutes)
        self.max_cache_size = max_cache_size or settings.CACHE_MAX_SIZE

        # Cache: (target, zone, rrtype) -> result
        self._cache: TTLCache = TTLCache(
            maxsize=self.max_cache_size,
            ttl=self.cache_ttl.total_seconds(),
        )

        self._cache_lock = asyncio.Lock()

        # Rate limiter
        self.per_zone_rate_limit = per_zone_rate_limit or settings.DNS_PER_ZONE_RATE_LIMIT
        self.rate_limiter = RateLimiter(self.per_zone_rate_limit)

        # DNS resolver settings
        self.timeout_ms = timeout_ms or settings.DNS_TIMEOUT_MS
        self.dns_nameservers = dns_nameservers or settings.DNS_NAMESERVERS

        # Spamhaus zones for special handling
        self.spamhaus_zones = set(settings.SPAMHAUS_ZONES)

        # Create resolver
        self.resolver = dns.asyncresolver.Resolver()
        if self.dns_nameservers:
            self.resolver.nameservers = self.dns_nameservers
        self.resolver.timeout = self.timeout_ms / 1000.0
        self.resolver.lifetime = self.timeout_ms / 1000.0

    def _make_cache_key(self, target: str, zone: str, rrtype: str) -> str:
        """Create cache key."""
        return f"{target}:{zone}:{rrtype}"

    async def _get_cached(self, target: str, zone: str, rrtype: str) -> Optional[Dict]:
        """Get cached result if available and not expired."""
        key = self._make_cache_key(target, zone, rrtype)
        async with self._cache_lock:
            return self._cache.get(key)

    async def _set_cache(self, target: str, zone: str, rrtype: str, result: Dict) -> None:
        """Set cached result."""
        key = self._make_cache_key(target, zone, rrtype)
        async with self._cache_lock:
            self._cache[key] = result

    def _is_spamhaus_blocked(self, ip_str: str) -> bool:
        """Check if IP is in Spamhaus blocked range (127.255.255.x)."""
        try:
            ip = ipaddress.IPv4Address(ip_str)
            return ip in ipaddress.IPv4Network("127.255.255.0/24")
        except (ipaddress.AddressValueError, ValueError):
            return False

    def _is_spamhaus_listed(self, ip_str: str) -> bool:
        """Check if IP is in Spamhaus listed range (127.0.0.x)."""
        try:
            ip = ipaddress.IPv4Address(ip_str)
            return ip in ipaddress.IPv4Network("127.0.0.0/24")
        except (ipaddress.AddressValueError, ValueError):
            return False

    async def _query_dns(
        self, target: str, zone: str, rrtype: str = "A"
    ) -> Tuple[str, List[str]]:
        """Query DNS for target against zone."""
        # Apply rate limiting
        await self.rate_limiter.acquire(zone)

        # Check cache first
        cached = await self._get_cached(target, zone, rrtype)
        if cached is not None:
            return cached["status"], cached["records"]

        try:
            # Build DNSBL query
            if rrtype == "A":
                query_target = self._build_dnsbl_query(target, zone)
            else:
                query_target = self._build_dnsbl_query(target, zone)

            # Query DNS
            answer = await self.resolver.resolve(query_target, rrtype)

            # Extract records
            records = [str(rdata) for rdata in answer]

            # Cache result
            await self._set_cache(target, zone, rrtype, {"status": "success", "records": records})

            return "success", records

        except NXDOMAIN:
            # Not listed
            await self._set_cache(target, zone, rrtype, {"status": "nxdomain", "records": []})
            return "nxdomain", []

        except NoAnswer:
            # Not listed for this record type
            await self._set_cache(target, zone, rrtype, {"status": "noanswer", "records": []})
            return "noanswer", []

        except Timeout:
            # Timeout error
            await self._set_cache(target, zone, rrtype, {"status": "timeout", "records": []})
            return "timeout", []

        except DNSException as e:
            # Other DNS errors
            await self._set_cache(target, zone, rrtype, {"status": "error", "records": []})
            return "error", []

    def _build_dnsbl_query(self, ip: str, zone: str) -> str:
        """Build DNSBL query string for an IP."""
        try:
            ip_obj = ipaddress.IPv4Address(ip)
            # Reverse the IP
            octets = str(ip_obj).split(".")
            reversed_ip = ".".join(reversed(octets))
            return f"{reversed_ip}.{zone}"
        except (ipaddress.AddressValueError, ValueError):
            # Invalid IP, return as-is for domain queries
            return f"{ip}.{zone}"

    async def check_zone(self, target: str, zone: str, include_txt: bool = False) -> CheckResult:
        """Check a target against a single DNSBL zone."""
        # Query A record
        a_status, a_records = await self._query_dns(target, zone, "A")

        # Determine status
        if a_status in ["nxdomain", "noanswer"]:
            return CheckResult(
                zone=zone,
                status="not_listed",
                a_records=[],
                txt_records=[],
            )
        elif a_status in ["timeout", "error"]:
            return CheckResult(
                zone=zone,
                status="error",
                a_records=[],
                txt_records=[],
                error_reason=a_status,
            )

        # We have A records - check if listed or blocked
        if not a_records:
            return CheckResult(
                zone=zone,
                status="not_listed",
                a_records=[],
                txt_records=[],
            )

        # Check for Spamhaus special handling
        if zone in self.spamhaus_zones:
            for a_record in a_records:
                if self._is_spamhaus_blocked(a_record):
                    return CheckResult(
                        zone=zone,
                        status="blocked",
                        a_records=a_records,
                        txt_records=[],
                        error_reason="Blocked/limits",
                    )

        # Listed
        txt_records = []
        if include_txt:
            _, txt_records = await self._query_dns(target, zone, "TXT")

        return CheckResult(
            zone=zone,
            status="listed",
            a_records=a_records,
            txt_records=txt_records,
        )

    async def check_target(
        self,
        target: str,
        zones: List[str],
        include_txt: bool = False,
        concurrency: int = 50,
    ) -> TargetResult:
        """Check a target against multiple zones concurrently."""
        # Determine target type
        try:
            ipaddress.IPv4Address(target)
            target_type = "ip"
        except (ipaddress.AddressValueError, ValueError):
            target_type = "domain"

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(concurrency)

        async def check_single(zone: str) -> Tuple[str, CheckResult]:
            async with semaphore:
                result = await self.check_zone(target, zone, include_txt)
                return zone, result

        # Run all checks concurrently
        tasks = [check_single(zone) for zone in zones]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate results
        listed = []
        blocked = []
        errors = []
        not_listed_count = 0

        for zone, result in results:
            if isinstance(result, Exception):
                errors.append({
                    "zone": zone,
                    "error": str(result),
                })
                continue

            if result.status == "listed":
                listed.append({
                    "zone": zone,
                    "a": result.a_records,
                    "txt": result.txt_records,
                })
            elif result.status == "blocked":
                blocked.append({
                    "zone": zone,
                    "a": result.a_records,
                    "error": result.error_reason,
                })
            elif result.status == "error":
                errors.append({
                    "zone": zone,
                    "error": result.error_reason or "Unknown error",
                })
            elif result.status == "not_listed":
                not_listed_count += 1

        return TargetResult(
            target=target,
            target_type=target_type,
            listed=listed,
            blocked=blocked,
            errors=errors,
            not_listed_zones_count=not_listed_count,
        )

    async def check_multiple(
        self,
        targets: List[str],
        zones: List[str],
        include_txt: bool = False,
        concurrency: int = 50,
    ) -> Tuple[Dict, List[Dict]]:
        """Check multiple targets against multiple zones."""
        # Create semaphore for target-level concurrency
        semaphore = asyncio.Semaphore(concurrency)

        results = []

        async def check_single_target(target: str) -> TargetResult:
            async with semaphore:
                return await self.check_target(target, zones, include_txt, concurrency)

        # Run all target checks concurrently
        target_results = await asyncio.gather(
            *[check_single_target(t) for t in targets],
            return_exceptions=True,
        )

        # Process results and build summary
        total_ips = len(targets)
        listed_ips = 0
        blocked_ips = 0
        error_ips = 0

        for result in target_results:
            if isinstance(result, Exception):
                error_ips += 1
                continue

            # Convert to dict format
            result_dict = {
                "target": result.target,
                "type": result.target_type,
                "listed": result.listed,
                "blocked": result.blocked,
                "errors": result.errors,
                "not_listed_zones_count": result.not_listed_zones_count,
            }
            results.append(result_dict)

            if result.listed:
                listed_ips += 1
            if result.blocked:
                blocked_ips += 1
            if result.errors and not result.listed and not result.blocked:
                error_ips += 1

        summary = {
            "total_ips": total_ips,
            "listed_ips": listed_ips,
            "blocked_ips": blocked_ips,
            "error_ips": error_ips,
        }

        return summary, results

    def clear_cache(self) -> None:
        """Clear the cache."""
        self._cache.clear()

    def get_cache_stats(self) -> Dict:
        """Get cache statistics."""
        return {
            "size": len(self._cache),
            "max_size": self._cache.maxsize,
            "ttl_seconds": self._cache.ttl,
        }


# Global checker instance
_checker: Optional[DNSBLChecker] = None


def get_checker() -> DNSBLChecker:
    """Get or create global checker instance."""
    global _checker
    if _checker is None:
        _checker = DNSBLChecker()
    return _checker
