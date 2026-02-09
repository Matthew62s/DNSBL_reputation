"""Database models for IP Reputation Monitor."""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    Integer,
    Text,
    ForeignKey,
    Index,
    JSON,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class Target(Base):
    """Represents an IP address or domain to monitor."""

    __tablename__ = "targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False, default="ip")  # 'ip' or 'domain'
    label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string array
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    check_results: Mapped[list["CheckResult"]] = relationship(
        "CheckResult", back_populates="target", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_target_enabled", "enabled"),
        Index("idx_target_type", "type"),
    )


class Zone(Base):
    """Represents a DNSBL/RBL blacklist zone."""

    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    zone: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_spamhaus: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    check_results: Mapped[list["CheckResult"]] = relationship(
        "CheckResult", back_populates="zone", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_zone_enabled", "enabled"),
    )


class CheckResult(Base):
    """Represents a DNSBL check result for a target against a zone."""

    __tablename__ = "check_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("targets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    zone_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("zones.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Result status
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # 'listed', 'not_listed', 'error', 'blocked'

    # DNS responses
    a_records: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string array
    txt_records: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string array

    # Error information
    error_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Timestamps
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_checked: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Monitoring run reference
    run_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("monitor_runs.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    target: Mapped["Target"] = relationship("Target", back_populates="check_results")
    zone: Mapped["Zone"] = relationship("Zone", back_populates="check_results")
    run: Mapped[Optional["MonitorRun"]] = relationship("MonitorRun", back_populates="check_results")

    __table_args__ = (
        Index("idx_check_result_status", "status"),
        Index("idx_check_result_target_zone", "target_id", "zone_id", unique=False),
        Index("idx_check_result_last_seen", "last_seen"),
    )


class MonitorRun(Base):
    """Represents a scheduled or manual monitoring run."""

    __tablename__ = "monitor_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    triggered_by: Mapped[str] = mapped_column(String(50), nullable=False, default="scheduler")  # 'scheduler', 'manual', 'api'

    # Status
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")  # 'running', 'completed', 'failed'
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Counts
    total_targets: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_zones: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_checks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    listed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    blocked_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Timing
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Integer, nullable=True)

    # Metadata
    metadata: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON

    # Relationships
    check_results: Mapped[list["CheckResult"]] = relationship("CheckResult", back_populates="run")

    __table_args__ = (
        Index("idx_monitor_run_started_at", "started_at"),
        Index("idx_monitor_run_status", "status"),
    )


class Report(Base):
    """Represents a generated report."""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_type: Mapped[str] = mapped_column(String(10), nullable=False)  # 'csv', 'xlsx', 'pdf'

    # Status
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # 'pending', 'generating', 'completed', 'failed'
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Filters
    filters: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON

    # Date range
    date_from: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    date_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # File information
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Metadata
    metadata: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON

    __table_args__ = (
        Index("idx_report_created_at", "created_at"),
        Index("idx_report_status", "status"),
    )


class Alert(Base):
    """Represents an alert notification."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'newly_listed', 'delisted', 'blocked', 'error', 'persistent'

    # Target reference
    target_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("targets.id", ondelete="SET NULL"), nullable=True
    )

    # Alert details
    zone: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    old_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    new_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Notification status
    webhook_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    webhook_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    webhook_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_alert_created_at", "created_at"),
        Index("idx_alert_target_id", "target_id"),
    )
