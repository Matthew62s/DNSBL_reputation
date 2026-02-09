"""API endpoints for reports."""

import logging
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db, SessionLocal
from app.models.database import Report
from app.models.schemas import (
    ReportCreate,
    ReportResponse,
    ReportListResponse,
    MessageResponse,
)
from app.services.reports import get_report_service

router = APIRouter(prefix="/reports", tags=["reports"])
logger = logging.getLogger(__name__)


@router.post("", response_model=ReportResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_report(
    request: ReportCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Create a new report (async generation).

    **Parameters:**
    - report_type: Type of report ('csv', 'xlsx', or 'pdf')
    - date_from: Optional start date for report data
    - date_to: Optional end date for report data
    - target_ids: Optional list of target IDs to include
    - zone_ids: Optional list of zone IDs to include
    - status_filter: Optional filter by status ('listed', 'blocked', 'error', or 'all')

    The report is generated in the background. Use GET /reports/{id} to check status.
    """
    # Create report record
    report = Report(
        report_type=request.report_type,
        status="pending",
        date_from=request.date_from,
        date_to=request.date_to,
        report_metadata="{}",
    )
    if request.target_ids or request.zone_ids or request.status_filter:
        filters = {
            "target_ids": request.target_ids,
            "zone_ids": request.zone_ids,
            "status_filter": request.status_filter,
        }
        report.filters = str(filters)
    db.add(report)
    db.commit()
    db.refresh(report)

    # Generate report in background
    def generate_report(report_id: int):
        report_service = get_report_service()
        background_db = SessionLocal()

        try:
            background_report = background_db.query(Report).filter(Report.id == report_id).first()
            if not background_report:
                logger.error("Report %s not found when starting background generation", report_id)
                return

            # Update status
            background_report.status = "generating"
            background_db.commit()

            # Generate report
            filepath, file_size = report_service.generate_report(
                report_type=background_report.report_type,
                date_from=background_report.date_from,
                date_to=background_report.date_to,
            )

            # Update report
            background_report.file_path = filepath
            background_report.file_size_bytes = file_size
            background_report.status = "completed"
            background_report.completed_at = datetime.utcnow()
            background_db.commit()

        except Exception as e:
            logger.exception("Failed to generate report %s", report_id)
            background_db.rollback()

            try:
                background_report = background_db.query(Report).filter(Report.id == report_id).first()
                if background_report:
                    background_report.status = "failed"
                    background_report.error_message = str(e)
                    background_db.commit()
            except Exception:
                logger.exception("Failed to mark report %s as failed", report_id)
                background_db.rollback()
        finally:
            background_db.close()

    background_tasks.add_task(generate_report, report.id)

    return ReportResponse(
        id=report.id,
        report_type=report.report_type,
        status=report.status,
        error_message=report.error_message,
        date_from=report.date_from,
        date_to=report.date_to,
        file_path=report.file_path,
        file_size_bytes=report.file_size_bytes,
        created_at=report.created_at,
        completed_at=report.completed_at,
    )


@router.get("", response_model=ReportListResponse)
async def list_reports(
    status_filter: str = Query(None, description="Filter by status (pending/generating/completed/failed)"),
    report_type: str = Query(None, description="Filter by report type (csv/xlsx/pdf)"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """
    List reports with optional filters.

    **Query Parameters:**
    - status_filter: Filter by status
    - report_type: Filter by report type
    - offset: Pagination offset (default: 0)
    - limit: Results per page (default: 100, max: 1000)
    """
    query = db.query(Report)

    # Apply filters
    if status_filter:
        query = query.filter(Report.status == status_filter)

    if report_type:
        query = query.filter(Report.report_type == report_type)

    # Get total count
    total = query.count()

    # Apply pagination
    items = query.order_by(Report.created_at.desc()).offset(offset).limit(limit).all()

    # Convert to response models
    response_items = [
        ReportResponse(
            id=item.id,
            report_type=item.report_type,
            status=item.status,
            error_message=item.error_message,
            date_from=item.date_from,
            date_to=item.date_to,
            file_path=item.file_path,
            file_size_bytes=item.file_size_bytes,
            created_at=item.created_at,
            completed_at=item.completed_at,
        )
        for item in items
    ]

    return ReportListResponse(total=total, items=response_items)


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: int,
    db: Session = Depends(get_db),
):
    """Get a specific report by ID."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report {report_id} not found",
        )

    return ReportResponse(
        id=report.id,
        report_type=report.report_type,
        status=report.status,
        error_message=report.error_message,
        date_from=report.date_from,
        date_to=report.date_to,
        file_path=report.file_path,
        file_size_bytes=report.file_size_bytes,
        created_at=report.created_at,
        completed_at=report.completed_at,
    )


@router.get("/{report_id}/download")
async def download_report(
    report_id: int,
    db: Session = Depends(get_db),
):
    """Download a generated report file."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report {report_id} not found",
        )

    if report.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Report {report_id} is not ready for download (status: {report.status})",
        )

    if not report.file_path or not os.path.exists(report.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report file not found",
        )

    # Determine media type
    media_types = {
        "csv": "text/csv",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pdf": "application/pdf",
    }
    media_type = media_types.get(report.report_type, "application/octet-stream")

    # Get filename
    filename = os.path.basename(report.file_path)

    return FileResponse(
        report.file_path,
        media_type=media_type,
        filename=filename,
    )


@router.delete("/{report_id}", response_model=MessageResponse)
async def delete_report(
    report_id: int,
    db: Session = Depends(get_db),
):
    """Delete a report."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report {report_id} not found",
        )

    # Delete file if exists
    if report.file_path and os.path.exists(report.file_path):
        os.remove(report.file_path)

    # Delete database record
    db.delete(report)
    db.commit()

    return MessageResponse(message=f"Report {report_id} deleted successfully")


@router.post("/cleanup", response_model=MessageResponse)
async def cleanup_reports(
    background_tasks: BackgroundTasks,
    retention_days: int = Query(None, ge=1),
    db: Session = Depends(get_db),
):
    """
    Clean up old reports.

    **Query Parameters:**
    - retention_days: Number of days to retain (default: from config)
    """
    def cleanup():
        report_service = get_report_service()
        removed = report_service.cleanup_old_reports(retention_days)
        return removed

    # Run in background
    removed_count = await cleanup()

    return MessageResponse(message=f"Cleaned up {removed_count} old reports")
