"""API endpoints for Prometheus metrics."""

from fastapi import APIRouter, Depends
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.database import CheckResult, MonitorRun, Target, Zone, Alert

router = APIRouter(tags=["metrics"])

# Define Prometheus metrics
check_requests_total = Counter(
    'dnsbl_check_requests_total',
    'Total number of DNSBL check requests',
)

checks_completed_total = Counter(
    'dnsbl_checks_completed_total',
    'Total number of DNSBL checks completed',
)

checks_listed_total = Counter(
    'dnsbl_checks_listed_total',
    'Total number of DNSBL checks that returned listed status',
)

checks_blocked_total = Counter(
    'dnsbl_checks_blocked_total',
    'Total number of DNSBL checks that returned blocked status',
)

checks_error_total = Counter(
    'dnsbl_checks_error_total',
    'Total number of DNSBL checks that returned error status',
)

monitor_runs_total = Counter(
    'dnsbl_monitor_runs_total',
    'Total number of monitor runs',
    ['triggered_by', 'status']
)

monitor_run_duration_seconds = Histogram(
    'dnsbl_monitor_run_duration_seconds',
    'Duration of monitor runs in seconds',
)

current_targets_gauge = Gauge(
    'dnsbl_current_targets',
    'Current number of targets',
    ['type', 'enabled']
)

current_zones_gauge = Gauge(
    'dnsbl_current_zones',
    'Current number of zones',
    ['enabled']
)

cache_size_gauge = Gauge(
    'dnsbl_cache_size',
    'Current DNS cache size',
)

cache_max_size_gauge = Gauge(
    'dnsbl_cache_max_size',
    'Maximum DNS cache size',
)

alerts_total = Gauge(
    'dnsbl_alerts_total',
    'Total number of alerts',
    ['alert_type']
)


@router.get("", include_in_schema=False)
async def metrics():
    """
    Get Prometheus metrics.

    This endpoint returns metrics in Prometheus format for monitoring and alerting.
    """
    metrics_data = generate_latest()
    from fastapi import Response
    return Response(content=metrics_data, media_type=CONTENT_TYPE_LATEST)


@router.get("/update", dependencies=[Depends(get_db)])
async def update_metrics(db: Session = Depends(get_db)):
    """
    Update Prometheus metrics from database.

    This endpoint updates all gauge metrics with current values from the database.
    This is typically called by a background task or scheduler.
    """
    from app.services.dnsbl_checker import get_checker

    # Update target gauges
    total_targets = db.query(Target).count()
    enabled_targets = db.query(Target).filter(Target.enabled == True).count()
    disabled_targets = total_targets - enabled_targets

    ip_targets = db.query(Target).filter(Target.type == 'ip').count()
    domain_targets = db.query(Target).filter(Target.type == 'domain').count()

    current_targets_gauge.labels(type='ip', enabled='true').set(ip_targets)
    current_targets_gauge.labels(type='ip', enabled='false').set(total_targets - enabled_targets)
    current_targets_gauge.labels(type='domain', enabled='true').set(domain_targets)
    current_targets_gauge.labels(type='domain', enabled='false').set(total_targets - enabled_targets)

    # Update zone gauges
    total_zones = db.query(Zone).count()
    enabled_zones = db.query(Zone).filter(Zone.enabled == True).count()
    disabled_zones = total_zones - enabled_zones

    current_zones_gauge.labels(enabled='true').set(enabled_zones)
    current_zones_gauge.labels(enabled='false').set(disabled_zones)

    # Update cache gauges
    checker = get_checker()
    cache_stats = checker.get_cache_stats()
    cache_size_gauge.set(cache_stats['size'])
    cache_max_size_gauge.set(cache_stats['max_size'])

    # Update alert gauges
    from app.models.database import Alert

    newly_listed_alerts = db.query(Alert).filter(Alert.alert_type == 'newly_listed').count()
    delisted_alerts = db.query(Alert).filter(Alert.alert_type == 'delisted').count()
    blocked_alerts = db.query(Alert).filter(Alert.alert_type == 'blocked').count()
    error_alerts = db.query(Alert).filter(Alert.alert_type == 'error').count()
    persistent_alerts = db.query(Alert).filter(Alert.alert_type == 'persistent').count()

    alerts_total.labels(alert_type='newly_listed').set(newly_listed_alerts)
    alerts_total.labels(alert_type='delisted').set(delisted_alerts)
    alerts_total.labels(alert_type='blocked').set(blocked_alerts)
    alerts_total.labels(alert_type='error').set(error_alerts)
    alerts_total.labels(alert_type='persistent').set(persistent_alerts)

    return {"status": "metrics updated"}
