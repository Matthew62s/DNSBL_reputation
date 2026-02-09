"""Monitoring service for scheduled checks and alerts."""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional

import httpx

from app.core.database import get_db_context
from app.models.database import (
    Alert,
    CheckResult,
    MonitorRun,
    Target,
    Zone,
)
from app.services.dnsbl_checker import CheckResult as DNSBLCheckResult, get_checker
from app.core.config import settings


class MonitoringService:
    """Service for running scheduled monitoring checks."""

    def __init__(self):
        self.checker = get_checker()
        self._is_running = False

    async def run_monitoring(
        self,
        triggered_by: str = "scheduler",
        target_ids: Optional[List[int]] = None,
        zone_ids: Optional[List[int]] = None,
    ) -> MonitorRun:
        """Run a full monitoring check."""
        if self._is_running:
            raise RuntimeError("Monitoring is already running")

        self._is_running = True

        with get_db_context() as db:
            # Create monitor run record
            run = MonitorRun(
                triggered_by=triggered_by,
                status="running",
                started_at=datetime.utcnow(),
            )
            db.add(run)
            db.flush()

            try:
                # Get targets to check
                query = db.query(Target).filter(Target.enabled == True)
                if target_ids:
                    query = query.filter(Target.id.in_(target_ids))
                targets = query.all()

                # Get zones to check
                query = db.query(Zone).filter(Zone.enabled == True)
                if zone_ids:
                    query = query.filter(Zone.id.in_(zone_ids))
                zones = query.all()

                run.total_targets = len(targets)
                run.total_zones = len(zones)
                db.flush()

                if not targets or not zones:
                    run.status = "completed"
                    run.finished_at = datetime.utcnow()
                    run.duration_seconds = 0
                    db.commit()
                    self._is_running = False
                    return run

                # Prepare zone list
                zone_list = [z.zone for z in zones]

                # Track previous statuses for alerting
                previous_statuses = {}
                for target in targets:
                    previous_results = (
                        db.query(CheckResult)
                        .filter(CheckResult.target_id == target.id)
                        .filter(CheckResult.zone_id.in_([z.id for z in zones]))
                        .all()
                    )
                    for pr in previous_results:
                        key = (target.id, pr.zone_id)
                        previous_statuses[key] = pr.status

                # Run checks
                total_checks = 0
                listed_count = 0
                blocked_count = 0
                error_count = 0

                target_list = [t.target for t in targets]
                summary, target_results = await self.checker.check_multiple(
                    targets=target_list,
                    zones=zone_list,
                    include_txt=False,
                    concurrency=settings.DNS_CONCURRENCY,
                )

                # Process results and save to database
                zone_map = {z.zone: z for z in zones}
                target_map = {t.target: t for t in targets}

                for result in target_results:
                    target = target_map.get(result["target"])
                    if not target:
                        continue

                    for listed in result["listed"]:
                        zone = zone_map.get(listed["zone"])
                        if zone:
                            self._save_check_result(
                                db, target, zone, "listed", listed["a"], run.id
                            )
                            listed_count += 1
                            total_checks += 1

                            # Check for alert
                            prev_status = previous_statuses.get((target.id, zone.id))
                            if prev_status != "listed":
                                self._create_alert(
                                    db,
                                    target,
                                    "newly_listed",
                                    zone.zone,
                                    prev_status,
                                    "listed",
                                    f"Target {target.target} is now listed on {zone.zone}",
                                )

                    for blocked in result["blocked"]:
                        zone = zone_map.get(blocked["zone"])
                        if zone:
                            self._save_check_result(
                                db, target, zone, "blocked", blocked["a"], run.id
                            )
                            blocked_count += 1
                            total_checks += 1

                            prev_status = previous_statuses.get((target.id, zone.id))
                            if prev_status != "blocked":
                                self._create_alert(
                                    db,
                                    target,
                                    "blocked",
                                    zone.zone,
                                    prev_status,
                                    "blocked",
                                    f"Target {target.target} is blocked on {zone.zone} (limits reached)",
                                )

                    for error in result["errors"]:
                        zone = zone_map.get(error["zone"])
                        if zone:
                            self._save_check_result(
                                db, target, zone, "error", [], run.id, error["error"]
                            )
                            error_count += 1
                            total_checks += 1

                    # Note: not_listed zones are not saved individually for performance

                # Update run with final stats
                run.total_checks = total_checks
                run.listed_count = listed_count
                run.blocked_count = blocked_count
                run.error_count = error_count
                run.status = "completed"
                run.finished_at = datetime.utcnow()
                run.duration_seconds = int((run.finished_at - run.started_at).total_seconds())

                db.commit()

                # Send webhooks for alerts
                await self._send_webhooks(db, run)

                return run

            except Exception as e:
                run.status = "failed"
                run.finished_at = datetime.utcnow()
                run.duration_seconds = int((run.finished_at - run.started_at).total_seconds())
                run.error_message = str(e)
                db.commit()
                raise
            finally:
                self._is_running = False

    def _save_check_result(
        self,
        db,
        target: Target,
        zone: Zone,
        status: str,
        a_records: List[str],
        run_id: int,
        error_reason: Optional[str] = None,
    ) -> None:
        """Save a check result to the database."""
        # Check if there's already a recent result for this target/zone
        existing = (
            db.query(CheckResult)
            .filter(CheckResult.target_id == target.id)
            .filter(CheckResult.zone_id == zone.id)
            .first()
        )

        if existing:
            # Update existing
            existing.status = status
            existing.a_records = json.dumps(a_records) if a_records else None
            existing.last_checked = datetime.utcnow()
            if status != "not_listed":
                existing.last_seen = datetime.utcnow()
            existing.error_reason = error_reason
            existing.run_id = run_id
        else:
            # Create new
            result = CheckResult(
                target_id=target.id,
                zone_id=zone.id,
                status=status,
                a_records=json.dumps(a_records) if a_records else None,
                error_reason=error_reason,
                last_seen=datetime.utcnow() if status != "not_listed" else datetime.utcnow(),
                last_checked=datetime.utcnow(),
                run_id=run_id,
            )
            db.add(result)

    def _create_alert(
        self,
        db,
        target: Optional[Target],
        alert_type: str,
        zone: str,
        old_status: Optional[str],
        new_status: str,
        message: str,
    ) -> Alert:
        """Create an alert."""
        alert = Alert(
            alert_type=alert_type,
            target_id=target.id if target else None,
            zone=zone,
            old_status=old_status,
            new_status=new_status,
            message=message,
            webhook_sent=False,
        )
        db.add(alert)
        return alert

    async def _send_webhooks(self, db, run: MonitorRun) -> None:
        """Send webhooks for unsent alerts."""
        if not settings.ALERT_WEBHOOK_URL:
            return

        # Get unsent alerts from this run
        alerts = (
            db.query(Alert)
            .filter(Alert.webhook_sent == False)
            .filter(Alert.created_at >= run.started_at)
            .all()
        )

        if not alerts:
            return

        # Prepare webhook payload
        payload = {
            "run_id": run.id,
            "triggered_by": run.triggered_by,
            "started_at": run.started_at.isoformat(),
            "summary": {
                "listed_count": run.listed_count,
                "blocked_count": run.blocked_count,
                "error_count": run.error_count,
            },
            "alerts": [
                {
                    "type": a.alert_type,
                    "target": db.query(Target).filter(Target.id == a.target_id).first().target if a.target_id else None,
                    "zone": a.zone,
                    "old_status": a.old_status,
                    "new_status": a.new_status,
                    "message": a.message,
                    "created_at": a.created_at.isoformat(),
                }
                for a in alerts
            ],
        }

        # Send webhook
        try:
            async with httpx.AsyncClient(timeout=settings.ALERT_WEBHOOK_TIMEOUT_SEC) as client:
                response = await client.post(settings.ALERT_WEBHOOK_URL, json=payload)
                response.raise_for_status()

                # Mark alerts as sent
                for alert in alerts:
                    alert.webhook_sent = True
                    alert.webhook_status = "sent"
                db.commit()

        except Exception as e:
            # Mark alerts as failed
            for alert in alerts:
                alert.webhook_sent = False
                alert.webhook_status = "failed"
                alert.webhook_error = str(e)
            db.commit()

    def get_latest_status(self, db, limit: int = 100) -> List[Dict]:
        """Get latest status for all targets."""
        # Get all enabled targets with their latest results
        targets = db.query(Target).filter(Target.enabled == True).all()

        results = []
        for target in targets:
            # Get latest results for this target
            latest_results = (
                db.query(CheckResult, Zone)
                .join(Zone, CheckResult.zone_id == Zone.id)
                .filter(CheckResult.target_id == target.id)
                .filter(CheckResult.status.in_(["listed", "blocked", "error"]))
                .order_by(CheckResult.last_seen.desc())
                .all()
            )

            results.append({
                "id": target.id,
                "target": target.target,
                "type": target.type,
                "label": target.label,
                "tags": json.loads(target.tags) if target.tags else [],
                "listed_count": sum(1 for r, z in latest_results if r.status == "listed"),
                "blocked_count": sum(1 for r, z in latest_results if r.status == "blocked"),
                "error_count": sum(1 for r, z in latest_results if r.status == "error"),
                "last_checked": max([r.last_checked for r, z in latest_results]) if latest_results else None,
                "issues": [
                    {
                        "zone": z.zone,
                        "status": r.status,
                        "a_records": json.loads(r.a_records) if r.a_records else [],
                        "last_seen": r.last_seen.isoformat(),
                    }
                    for r, z in latest_results[:10]  # Top 10 issues
                ],
            })

        return results

    def get_target_history(
        self, db, target_id: int, limit: int = 50
    ) -> List[Dict]:
        """Get history for a specific target."""
        results = (
            db.query(CheckResult, Zone)
            .join(Zone, CheckResult.zone_id == Zone.id)
            .filter(CheckResult.target_id == target_id)
            .order_by(CheckResult.last_checked.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "zone": z.zone,
                "status": r.status,
                "a_records": json.loads(r.a_records) if r.a_records else [],
                "error_reason": r.error_reason,
                "last_checked": r.last_checked.isoformat(),
                "last_seen": r.last_seen.isoformat(),
            }
            for r, z in results
        ]


# Global monitoring service instance
_monitoring_service: Optional[MonitoringService] = None


def get_monitoring_service() -> MonitoringService:
    """Get or create global monitoring service instance."""
    global _monitoring_service
    if _monitoring_service is None:
        _monitoring_service = MonitoringService()
    return _monitoring_service
