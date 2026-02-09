"""API endpoints for status and history."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.database import CheckResult, Zone
from app.models.schemas import (
    TargetStatusResponse,
    TargetHistoryResponse,
)
from app.services.monitoring import get_monitoring_service

router = APIRouter(prefix="/status", tags=["status"])


@router.get("", response_model=list[TargetStatusResponse])
async def get_status(
    type_filter: str = Query(None, description="Filter by target type (ip/domain)"),
    has_issues_only: bool = Query(False, description="Only return targets with issues"),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """
    Get latest status for all targets.

    **Query Parameters:**
    - type_filter: Filter by target type ('ip' or 'domain')
    - has_issues_only: Only return targets with listed/blocked/error statuses
    - limit: Maximum number of results (default: 100, max: 1000)

    **Returns:**
    - Latest status for each target including listed, blocked, and error counts
    - Top 10 issues per target
    """
    monitoring_service = get_monitoring_service()

    # Get all status data
    all_status = monitoring_service.get_latest_status(db, limit=None)

    # Apply filters
    if type_filter:
        all_status = [s for s in all_status if s["type"] == type_filter]

    if has_issues_only:
        all_status = [s for s in all_status if s["listed_count"] > 0 or s["blocked_count"] > 0 or s["error_count"] > 0]

    # Apply limit
    all_status = all_status[:limit]

    # Convert to response models
    response_items = [
        TargetStatusResponse(
            id=item["id"],
            target=item["target"],
            type=item["type"],
            label=item["label"],
            tags=item["tags"],
            listed_count=item["listed_count"],
            blocked_count=item["blocked_count"],
            error_count=item["error_count"],
            last_checked=item["last_checked"].isoformat() if item["last_checked"] else None,
            issues=item["issues"],
        )
        for item in all_status
    ]

    return response_items


@router.get("/summary")
async def get_status_summary(
    db: Session = Depends(get_db),
):
    """
    Get aggregated status summary.

    **Returns:**
    - total_targets: Total number of enabled targets
    - listed_targets: Number of targets with at least one listing
    - blocked_targets: Number of targets with at least one block
    - error_targets: Number of targets with at least one error
    - last_run: Information about the most recent monitoring run
    """
    from app.models.database import Target, MonitorRun
    from datetime import datetime

    # Count targets
    total_targets = db.query(Target).filter(Target.enabled == True).count()

    # Count targets with issues
    # This is an approximation - checking targets with recent check results
    listed_targets = 0
    blocked_targets = 0
    error_targets = 0

    enabled_targets = db.query(Target).filter(Target.enabled == True).all()
    for target in enabled_targets:
        # Get latest results
        latest = (
            db.query(CheckResult)
            .filter(CheckResult.target_id == target.id)
            .order_by(CheckResult.last_checked.desc())
            .first()
        )
        if not latest:
            continue

        # Check status
        all_status = (
            db.query(CheckResult)
            .filter(CheckResult.target_id == target.id)
            .all()
        )

        for r in all_status:
            if r.status == "listed":
                listed_targets += 1
                break
        else:
            for r in all_status:
                if r.status == "blocked":
                    blocked_targets += 1
                    break
            else:
                for r in all_status:
                    if r.status == "error":
                        error_targets += 1
                        break

    # Get last run
    last_run = (
        db.query(MonitorRun)
        .order_by(MonitorRun.started_at.desc())
        .first()
    )

    last_run_info = None
    if last_run:
        last_run_info = {
            "id": last_run.id,
            "triggered_by": last_run.triggered_by,
            "status": last_run.status,
            "started_at": last_run.started_at.isoformat(),
            "finished_at": last_run.finished_at.isoformat() if last_run.finished_at else None,
            "duration_seconds": last_run.duration_seconds,
            "listed_count": last_run.listed_count,
            "blocked_count": last_run.blocked_count,
            "error_count": last_run.error_count,
        }

    return {
        "total_targets": total_targets,
        "listed_targets": listed_targets,
        "blocked_targets": blocked_targets,
        "error_targets": error_targets,
        "last_run": last_run_info,
    }


@router.get("/history/{target_id}", response_model=list[TargetHistoryResponse])
async def get_target_history(
    target_id: int,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """
    Get history for a specific target.

    **Query Parameters:**
    - limit: Maximum number of history entries (default: 50, max: 500)

    **Returns:**
    - List of check results with timestamps
    """
    from app.models.database import Target

    # Verify target exists
    target = db.query(Target).filter(Target.id == target_id).first()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {target_id} not found",
        )

    monitoring_service = get_monitoring_service()
    history = monitoring_service.get_target_history(db, target_id, limit)

    return [TargetHistoryResponse(**item) for item in history]
