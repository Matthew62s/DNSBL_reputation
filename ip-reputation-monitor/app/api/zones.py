"""API endpoints for zone (blacklist) management."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.database import Zone
from app.models.schemas import (
    ZoneCreate,
    ZoneUpdate,
    ZoneResponse,
    ZoneListResponse,
    MessageResponse,
)

router = APIRouter(prefix="/zones", tags=["zones"])


def is_spamhaus_zone(zone: str) -> bool:
    """Check if a zone is a Spamhaus zone."""
    return zone.lower() in [z.lower() for z in settings.SPAMHAUS_ZONES]


@router.post("", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def create_zone(
    request: ZoneCreate,
    db: Session = Depends(get_db),
):
    """
    Add a new DNSBL blacklist zone.

    **Parameters:**
    - zone: The DNSBL zone name (e.g., zen.spamhaus.org)
    - description: Optional description of the zone
    - enabled: Whether the zone is enabled (default: true)
    """
    # Check if zone already exists
    existing = db.query(Zone).filter(Zone.zone == request.zone).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Zone {request.zone} already exists",
        )

    # Create new zone
    zone = Zone(
        zone=request.zone,
        description=request.description,
        enabled=request.enabled,
        is_spamhaus=is_spamhaus_zone(request.zone),
    )
    db.add(zone)
    db.commit()

    return MessageResponse(message=f"Zone {request.zone} created successfully", id=zone.id)


@router.get("", response_model=ZoneListResponse)
async def list_zones(
    enabled_filter: bool = Query(None, description="Filter by enabled status"),
    search: Optional[str] = Query(None, description="Search by zone or description"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """
    List zones with optional filters.

    **Query Parameters:**
    - enabled_filter: Filter by enabled status
    - search: Search by zone name or description
    - offset: Pagination offset (default: 0)
    - limit: Results per page (default: 100, max: 1000)
    """
    query = db.query(Zone)

    # Apply filters
    if enabled_filter is not None:
        query = query.filter(Zone.enabled == enabled_filter)

    if search:
        query = query.filter(
            (Zone.zone.ilike(f"%{search}%")) | (Zone.description.ilike(f"%{search}%"))
        )

    # Get total count
    total = query.count()

    # Apply pagination
    items = query.order_by(Zone.zone).offset(offset).limit(limit).all()

    # Convert to response models
    response_items = [
        ZoneResponse(
            id=item.id,
            zone=item.zone,
            description=item.description,
            enabled=item.enabled,
            is_spamhaus=item.is_spamhaus,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in items
    ]

    return ZoneListResponse(total=total, items=response_items)


@router.get("/{zone_id}", response_model=ZoneResponse)
async def get_zone(
    zone_id: int,
    db: Session = Depends(get_db),
):
    """Get a specific zone by ID."""
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zone {zone_id} not found",
        )

    return ZoneResponse(
        id=zone.id,
        zone=zone.zone,
        description=zone.description,
        enabled=zone.enabled,
        is_spamhaus=zone.is_spamhaus,
        created_at=zone.created_at,
        updated_at=zone.updated_at,
    )


@router.patch("/{zone_id}", response_model=ZoneResponse)
async def update_zone(
    zone_id: int,
    request: ZoneUpdate,
    db: Session = Depends(get_db),
):
    """
    Update a zone.

    **Parameters:**
    - description: Optional new description
    - enabled: Optional enabled status
    """
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zone {zone_id} not found",
        )

    # Update fields
    if request.description is not None:
        zone.description = request.description

    if request.enabled is not None:
        zone.enabled = request.enabled

    db.commit()
    db.refresh(zone)

    return ZoneResponse(
        id=zone.id,
        zone=zone.zone,
        description=zone.description,
        enabled=zone.enabled,
        is_spamhaus=zone.is_spamhaus,
        created_at=zone.created_at,
        updated_at=zone.updated_at,
    )


@router.delete("/{zone_id}", response_model=MessageResponse)
async def delete_zone(
    zone_id: int,
    db: Session = Depends(get_db),
):
    """Delete a zone."""
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zone {zone_id} not found",
        )

    zone_name = zone.zone
    db.delete(zone)
    db.commit()

    return MessageResponse(message=f"Zone {zone_name} deleted successfully")


@router.post("/default/initialize", response_model=MessageResponse)
async def initialize_default_zones(db: Session = Depends(get_db)):
    """
    Initialize default DNSBL zones from configuration.

    This endpoint adds all default zones from settings if they don't already exist.
    """
    added_count = 0
    skipped_count = 0

    for zone_name in settings.DEFAULT_ZONES:
        existing = db.query(Zone).filter(Zone.zone == zone_name).first()
        if existing:
            skipped_count += 1
            continue

        zone = Zone(
            zone=zone_name,
            description="Default DNSBL zone",
            enabled=True,
            is_spamhaus=is_spamhaus_zone(zone_name),
        )
        db.add(zone)
        added_count += 1

    db.commit()

    return MessageResponse(
        message=f"Added {added_count} default zones, skipped {skipped_count} existing zones"
    )
