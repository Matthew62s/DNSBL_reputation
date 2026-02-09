"""API endpoint for DNSBL checks."""

from fastapi import APIRouter, Depends, HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.models.schemas import (
    CheckRequest,
    CheckResponse,
    MessageResponse,
)
from app.services.dnsbl_checker import get_checker
from app.core.config import settings

router = APIRouter(prefix="/check", tags=["check"])
limiter = Limiter(key_func=get_remote_address)


@router.post("", response_model=CheckResponse, status_code=status.HTTP_200_OK)
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def check_ips(request: CheckRequest):
    """
    Check IPs/Domains against DNSBL blacklists.

    This endpoint checks multiple targets against DNSBL/RBL blacklists.
    Returns detailed results including listed, blocked, and error statuses.

    **Rate Limiting:** {settings.RATE_LIMIT_PER_MINUTE} requests per minute per client.

    **Parameters:**
    - ips: List of IP addresses or domains to check (max 1000)
    - zones: Optional list of zones to check (defaults to all enabled zones)
    - include_txt: Whether to include TXT records (default: false)
    - timeout_ms: DNS query timeout in milliseconds (default: 2500)
    - concurrency: Max concurrent DNS queries (default: 50)

    **Returns:**
    - summary: Aggregate counts of listed/blocked/error targets
    - results: Detailed results for each target
    """
    try:
        checker = get_checker()

        # Get zones to check
        zones = request.zones
        if not zones:
            # Get default zones from settings
            zones = settings.DEFAULT_ZONES

        # Perform checks
        summary_data, results_data = await checker.check_multiple(
            targets=request.ips,
            zones=zones,
            include_txt=request.include_txt,
            concurrency=request.concurrency,
        )

        return CheckResponse(
            summary=summary_data,
            results=results_data,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Check failed: {str(e)}",
        )


@router.get("/cache/stats", response_model=dict)
async def get_cache_stats():
    """Get DNS cache statistics."""
    checker = get_checker()
    return checker.get_cache_stats()


@router.post("/cache/clear", response_model=MessageResponse)
async def clear_cache():
    """Clear the DNS cache."""
    checker = get_checker()
    checker.clear_cache()
    return MessageResponse(message="Cache cleared successfully")
