"""Pydantic models for API requests and responses."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# ===== Check Endpoints =====

class CheckRequest(BaseModel):
    """Request model for /check endpoint."""
    ips: List[str] = Field(..., min_length=1, max_length=1000, description="List of IP addresses to check")
    zones: Optional[List[str]] = Field(None, description="Override default zones")
    include_txt: bool = Field(False, description="Include TXT records")
    timeout_ms: int = Field(2500, ge=100, le=30000, description="DNS query timeout in milliseconds")
    concurrency: int = Field(50, ge=1, le=500, description="Max concurrent DNS queries")

    @field_validator("ips")
    @classmethod
    def validate_ips(cls, v):
        """Validate IP addresses."""
        for ip in v:
            # Allow both IPv4 and domain names for future extension
            if len(ip) > 255:
                raise ValueError(f"IP or domain too long: {ip}")
        return v


class ZoneResult(BaseModel):
    """Result for a single zone check."""
    zone: str
    a: List[str]
    txt: Optional[str] = None


class BlockedZoneResult(BaseModel):
    """Result for a blocked zone check."""
    zone: str
    a: List[str]
    error: str


class ErrorZoneResult(BaseModel):
    """Result for a zone with error."""
    zone: str
    error: str


class TargetCheckResult(BaseModel):
    """Check result for a single target."""
    target: str
    type: str
    listed: List[ZoneResult]
    blocked: List[BlockedZoneResult]
    errors: List[ErrorZoneResult]
    not_listed_zones_count: int


class CheckSummary(BaseModel):
    """Summary of check results."""
    total_ips: int
    listed_ips: int
    blocked_ips: int
    error_ips: int


class CheckResponse(BaseModel):
    """Response model for /check endpoint."""
    summary: CheckSummary
    results: List[TargetCheckResult]


# ===== Target Management =====

class TargetCreate(BaseModel):
    """Request model for creating a target."""
    targets: List[str] = Field(..., min_length=1, max_length=1000)
    type: str = Field("ip", pattern="^(ip|domain)$")
    label: Optional[str] = Field(None, max_length=255)
    tags: Optional[List[str]] = Field(None)
    enabled: bool = Field(True)


class TargetUpdate(BaseModel):
    """Request model for updating a target."""
    label: Optional[str] = Field(None, max_length=255)
    tags: Optional[List[str]] = Field(None)
    enabled: Optional[bool] = Field(None)


class TargetResponse(BaseModel):
    """Response model for a target."""
    id: int
    target: str
    type: str
    label: Optional[str]
    tags: List[str]
    enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TargetListResponse(BaseModel):
    """Response model for target list."""
    total: int
    items: List[TargetResponse]


# ===== Zone Management =====

class ZoneCreate(BaseModel):
    """Request model for creating a zone."""
    zone: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None)
    enabled: bool = Field(True)


class ZoneUpdate(BaseModel):
    """Request model for updating a zone."""
    description: Optional[str] = Field(None)
    enabled: Optional[bool] = Field(None)


class ZoneResponse(BaseModel):
    """Response model for a zone."""
    id: int
    zone: str
    description: Optional[str]
    enabled: bool
    is_spamhaus: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ZoneListResponse(BaseModel):
    """Response model for zone list."""
    total: int
    items: List[ZoneResponse]


# ===== Monitoring =====

class MonitorRunRequest(BaseModel):
    """Request model for triggering a monitor run."""
    target_ids: Optional[List[int]] = Field(None)
    zone_ids: Optional[List[int]] = Field(None)


class MonitorRunResponse(BaseModel):
    """Response model for a monitor run."""
    id: int
    triggered_by: str
    status: str
    error_message: Optional[str]
    total_targets: int
    total_zones: int
    total_checks: int
    listed_count: int
    blocked_count: int
    error_count: int
    started_at: datetime
    finished_at: Optional[datetime]
    duration_seconds: Optional[int]

    class Config:
        from_attributes = True


class MonitorRunListResponse(BaseModel):
    """Response model for monitor run list."""
    total: int
    items: List[MonitorRunResponse]


# ===== Status & History =====

class TargetStatusIssue(BaseModel):
    """Issue item in target status."""
    zone: str
    status: str
    a_records: List[str]
    last_seen: str


class TargetStatusResponse(BaseModel):
    """Response model for target status."""
    id: int
    target: str
    type: str
    label: Optional[str]
    tags: List[str]
    listed_count: int
    blocked_count: int
    error_count: int
    last_checked: Optional[str]
    issues: List[TargetStatusIssue]


class TargetHistoryResponse(BaseModel):
    """Response model for target history."""
    zone: str
    status: str
    a_records: List[str]
    error_reason: Optional[str]
    last_checked: str
    last_seen: str


# ===== Reports =====

class ReportCreate(BaseModel):
    """Request model for creating a report."""
    report_type: str = Field(..., pattern="^(csv|xlsx|pdf)$")
    date_from: Optional[datetime] = Field(None)
    date_to: Optional[datetime] = Field(None)
    target_ids: Optional[List[int]] = Field(None)
    zone_ids: Optional[List[int]] = Field(None)
    status_filter: Optional[str] = Field(None, pattern="^(listed|blocked|error|all)$")


class ReportResponse(BaseModel):
    """Response model for a report."""
    id: int
    report_type: str
    status: str
    error_message: Optional[str]
    date_from: Optional[datetime]
    date_to: Optional[datetime]
    file_path: Optional[str]
    file_size_bytes: Optional[int]
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class ReportListResponse(BaseModel):
    """Response model for report list."""
    total: int
    items: List[ReportResponse]


# ===== Common =====

class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
    id: Optional[int] = None


# ===== Metrics =====

class MetricsData(BaseModel):
    """Prometheus metrics data."""
    metrics: str
