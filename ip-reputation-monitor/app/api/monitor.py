"""API endpoints for monitoring runs."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.database import MonitorRun
from app.models.schemas import (
    MonitorRunRequest,
    MonitorRunResponse,
    MonitorRunListResponse,
    MessageResponse,
)
from app.services.monitoring import get_monitoring_service

router = APIRouter(prefix="/monitor", tags=["monitor"])


@router.post("/run", response_model=MonitorRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_monitor_run(
    request: MonitorRunRequest,
    background_tasks: BackgroundTasks,
    triggered_by: str = Query("api", description="Who triggered the run (api/manual/scheduler)"),
    db: Session = Depends(get_db),
):
    """
    Trigger a monitoring run (async).

    **Parameters:**
    - target_ids: Optional list of target IDs to check (default: all enabled)
    - zone_ids: Optional list of zone IDs to check (default: all enabled)

    The run is executed in the background. Use GET /monitor/runs/{id} to check status.
    """
    # Create a monitor run record
    monitoring_service = get_monitoring_service()

    # Create initial run record
    run = MonitorRun(
        triggered_by=triggered_by,
        status="running",
        started_at=datetime.utcnow(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Run in background
    async def run_monitoring():
        try:
            await monitoring_service.run_monitoring(
                triggered_by=triggered_by,
                target_ids=request.target_ids,
                zone_ids=request.zone_ids,
            )
        except Exception as e:
            # Error is already handled in run_monitoring
            pass

    background_tasks.add_task(run_monitoring)

    return MonitorRunResponse(
        id=run.id,
        triggered_by=run.triggered_by,
        status=run.status,
        error_message=run.error_message,
        total_targets=run.total_targets,
        total_zones=run.total_zones,
        total_checks=run.total_checks,
        listed_count=run.listed_count,
        blocked_count=run.blocked_count,
        error_count=run.error_count,
        started_at=run.started_at,
        finished_at=run.finished_at,
        duration_seconds=run.duration_seconds,
    )


@router.get("/runs", response_model=MonitorRunListResponse)
async def list_monitor_runs(
    triggered_by: str = Query(None, description="Filter by who triggered the run"),
    status_filter: str = Query(None, description="Filter by status (running/completed/failed)"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """
    List monitoring runs with filters.

    **Query Parameters:**
    - triggered_by: Filter by who triggered the run (api/manual/scheduler)
    - status_filter: Filter by status (running/completed/failed)
    - offset: Pagination offset (default: 0)
    - limit: Results per page (default: 100, max: 1000)
    """
    from datetime import datetime

    query = db.query(MonitorRun)

    # Apply filters
    if triggered_by:
        query = query.filter(MonitorRun.triggered_by == triggered_by)

    if status_filter:
        query = query.filter(MonitorRun.status == status_filter)

    # Get total count
    total = query.count()

    # Apply pagination
    items = query.order_by(MonitorRun.started_at.desc()).offset(offset).limit(limit).all()

    # Convert to response models
    response_items = [
        MonitorRunResponse(
            id=item.id,
            triggered_by=item.triggered_by,
            status=item.status,
            error_message=item.error_message,
            total_targets=item.total_targets,
            total_zones=item.total_zones,
            total_checks=item.total_checks,
            listed_count=item.listed_count,
            blocked_count=item.blocked_count,
            error_count=item.error_count,
            started_at=item.started_at,
            finished_at=item.finished_at,
            duration_seconds=item.duration_seconds,
        )
        for item in items
    ]

    return MonitorRunListResponse(total=total, items=response_items)


@router.get("/runs/{run_id}", response_model=MonitorRunResponse)
async def get_monitor_run(
    run_id: int,
    db: Session = Depends(get_db),
):
    """Get details of a specific monitoring run."""
    run = db.query(MonitorRun).filter(MonitorRun.id == run_id).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Monitor run {run_id} not found",
        )

    return MonitorRunResponse(
        id=run.id,
        triggered_by=run.triggered_by,
        status=run.status,
        error_message=run.error_message,
        total_targets=run.total_targets,
        total_zones=run.total_zones,
        total_checks=run.total_checks,
        listed_count=run.listed_count,
        blocked_count=run.blocked_count,
        error_count=run.error_count,
        started_at=run.started_at,
        finished_at=run.finished_at,
        duration_seconds=run.duration_seconds,
    )
