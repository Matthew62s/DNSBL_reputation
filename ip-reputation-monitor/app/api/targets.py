"""API endpoints for target management."""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.database import Target
from app.models.schemas import (
    TargetCreate,
    TargetUpdate,
    TargetResponse,
    TargetListResponse,
    MessageResponse,
)

router = APIRouter(prefix="/targets", tags=["targets"])


@router.post("", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def create_targets(
    request: TargetCreate,
    db: Session = Depends(get_db),
):
    """
    Add new targets (IPs or domains) for monitoring.

    **Parameters:**
    - targets: List of IP addresses or domain names (max 1000)
    - type: Target type - 'ip' or 'domain' (default: 'ip')
    - label: Optional label for the targets
    - tags: Optional list of tags
    - enabled: Whether the targets are enabled (default: true)
    """
    created_count = 0
    errors = []

    for target_str in request.targets:
        # Check if target already exists
        existing = db.query(Target).filter(Target.target == target_str).first()
        if existing:
            errors.append(f"{target_str}: Already exists")
            continue

        # Create new target
        target = Target(
            target=target_str,
            type=request.type,
            label=request.label,
            tags=json.dumps(request.tags) if request.tags else None,
            enabled=request.enabled,
        )
        db.add(target)
        created_count += 1

    db.commit()

    if created_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No targets created. Errors: {', '.join(errors)}",
        )

    return MessageResponse(
        message=f"Created {created_count} targets",
    )


@router.get("", response_model=TargetListResponse)
async def list_targets(
    type_filter: Optional[str] = Query(None, description="Filter by type (ip/domain)"),
    status_filter: Optional[str] = Query(None, description="Filter by status (enabled/disabled)"),
    search: Optional[str] = Query(None, description="Search by target or label"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """
    List targets with optional filters.

    **Query Parameters:**
    - type_filter: Filter by type ('ip' or 'domain')
    - status_filter: Filter by status ('enabled' or 'disabled')
    - search: Search by target address or label
    - tags: Filter by tags (comma-separated)
    - offset: Pagination offset (default: 0)
    - limit: Results per page (default: 100, max: 1000)
    """
    query = db.query(Target)

    # Apply filters
    if type_filter:
        query = query.filter(Target.type == type_filter)

    if status_filter:
        enabled = status_filter.lower() == "enabled"
        query = query.filter(Target.enabled == enabled)

    if search:
        query = query.filter(
            (Target.target.ilike(f"%{search}%")) | (Target.label.ilike(f"%{search}%"))
        )

    if tags:
        tag_list = [t.strip() for t in tags.split(",")]
        for tag in tag_list:
            query = query.filter(Target.tags.like(f'%"{tag}"%'))

    # Get total count
    total = query.count()

    # Apply pagination
    items = query.order_by(Target.created_at.desc()).offset(offset).limit(limit).all()

    # Convert tags from JSON
    response_items = []
    for item in items:
        response_items.append(
            TargetResponse(
                id=item.id,
                target=item.target,
                type=item.type,
                label=item.label,
                tags=json.loads(item.tags) if item.tags else [],
                enabled=item.enabled,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
        )

    return TargetListResponse(total=total, items=response_items)


@router.get("/{target_id}", response_model=TargetResponse)
async def get_target(
    target_id: int,
    db: Session = Depends(get_db),
):
    """Get a specific target by ID."""
    target = db.query(Target).filter(Target.id == target_id).first()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {target_id} not found",
        )

    return TargetResponse(
        id=target.id,
        target=target.target,
        type=target.type,
        label=target.label,
        tags=json.loads(target.tags) if target.tags else [],
        enabled=target.enabled,
        created_at=target.created_at,
        updated_at=target.updated_at,
    )


@router.patch("/{target_id}", response_model=TargetResponse)
async def update_target(
    target_id: int,
    request: TargetUpdate,
    db: Session = Depends(get_db),
):
    """
    Update a target.

    **Parameters:**
    - label: Optional new label
    - tags: Optional new list of tags
    - enabled: Optional enabled status
    """
    target = db.query(Target).filter(Target.id == target_id).first()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {target_id} not found",
        )

    # Update fields
    if request.label is not None:
        target.label = request.label

    if request.tags is not None:
        target.tags = json.dumps(request.tags)

    if request.enabled is not None:
        target.enabled = request.enabled

    db.commit()
    db.refresh(target)

    return TargetResponse(
        id=target.id,
        target=target.target,
        type=target.type,
        label=target.label,
        tags=json.loads(target.tags) if target.tags else [],
        enabled=target.enabled,
        created_at=target.created_at,
        updated_at=target.updated_at,
    )


@router.delete("/{target_id}", response_model=MessageResponse)
async def delete_target(
    target_id: int,
    db: Session = Depends(get_db),
):
    """Delete a target."""
    target = db.query(Target).filter(Target.id == target_id).first()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {target_id} not found",
        )

    db.delete(target)
    db.commit()

    return MessageResponse(message=f"Target {target_id} deleted successfully")


@router.post("/bulk/delete", response_model=MessageResponse)
async def bulk_delete_targets(
    target_ids: list[int],
    db: Session = Depends(get_db),
):
    """Delete multiple targets."""
    if not target_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No target IDs provided",
        )

    deleted_count = db.query(Target).filter(Target.id.in_(target_ids)).delete(synchronize_session=False)
    db.commit()

    return MessageResponse(message=f"Deleted {deleted_count} targets")
