# API Examples

This document provides detailed examples for using the IP Reputation Monitor API.

## Base URL

```
http://localhost:8000
```

All API endpoints are prefixed with `/api`.

## Check Endpoints

### Check IPs Against DNSBL

Check multiple IPs against all configured DNSBL zones.

```bash
curl -X POST http://localhost:8000/api/check \
  -H "Content-Type: application/json" \
  -d '{
    "ips": ["1.2.3.4", "8.8.8.8", "192.168.1.1"],
    "include_txt": false,
    "timeout_ms": 2500,
    "concurrency": 50
  }'
```

**Response:**

```json
{
  "summary": {
    "total_ips": 3,
    "listed_ips": 1,
    "blocked_ips": 0,
    "error_ips": 0
  },
  "results": [
    {
      "target": "1.2.3.4",
      "type": "ip",
      "listed": [
        {
          "zone": "zen.spamhaus.org",
          "a": ["127.0.0.2"],
          "txt": null
        },
        {
          "zone": "bl.spamcop.net",
          "a": ["127.0.0.2"],
          "txt": null
        }
      ],
      "blocked": [],
      "errors": [],
      "not_listed_zones_count": 48
    },
    {
      "target": "8.8.8.8",
      "type": "ip",
      "listed": [],
      "blocked": [],
      "errors": [],
      "not_listed_zones_count": 50
    },
    {
      "target": "192.168.1.1",
      "type": "ip",
      "listed": [],
      "blocked": [],
      "errors": [],
      "not_listed_zones_count": 50
    }
  ]
}
```

### Check with Specific Zones

Override default zones and check against specific ones only.

```bash
curl -X POST http://localhost:8000/api/check \
  -H "Content-Type: application/json" \
  -d '{
    "ips": ["1.2.3.4"],
    "zones": ["zen.spamhaus.org", "bl.spamcop.net"],
    "include_txt": true
  }'
```

### Check with TXT Records

Include TXT records for more detailed information.

```bash
curl -X POST http://localhost:8000/api/check \
  -H "Content-Type: application/json" \
  -d '{
    "ips": ["1.2.3.4"],
    "include_txt": true
  }'
```

### Get Cache Statistics

```bash
curl http://localhost:8000/api/check/cache/stats
```

**Response:**

```json
{
  "size": 1500,
  "max_size": 10000
}
```

### Clear DNS Cache

```bash
curl -X POST http://localhost:8000/api/check/cache/clear
```

## Target Management

### Add New Targets

Add multiple IP addresses for monitoring.

```bash
curl -X POST http://localhost:8000/api/targets \
  -H "Content-Type: application/json" \
  -d '{
    "targets": ["1.2.3.4", "8.8.8.8", "9.9.9.9"],
    "type": "ip",
    "label": "Production Mail Servers",
    "tags": ["production", "email"],
    "enabled": true
  }'
```

**Response:**

```json
{
  "message": "Created 3 targets",
  "id": null
}
```

### Add Domains (Future Extension)

```bash
curl -X POST http://localhost:8000/api/targets \
  -H "Content-Type: application/json" \
  -d '{
    "targets": ["example.com", "mail.example.com"],
    "type": "domain",
    "label": "Email Domains",
    "enabled": true
  }'
```

### List All Targets

```bash
curl http://localhost:8000/api/targets
```

**Response:**

```json
{
  "total": 10,
  "items": [
    {
      "id": 1,
      "target": "1.2.3.4",
      "type": "ip",
      "label": "Production Mail Servers",
      "tags": ["production", "email"],
      "enabled": true,
      "created_at": "2024-01-01T00:00:00",
      "updated_at": "2024-01-01T00:00:00"
    }
  ]
}
```

### List Targets with Filters

```bash
# Filter by type
curl "http://localhost:8000/api/targets?type_filter=ip&limit=50"

# Filter by status
curl "http://localhost:8000/api/targets?status_filter=enabled"

# Search by IP or label
curl "http://localhost:8000/api/targets?search=1.2.3.4"

# Filter by tags
curl "http://localhost:8000/api/targets?tags=production,email"

# Paginate
curl "http://localhost:8000/api/targets?offset=0&limit=50"
```

### Get Single Target

```bash
curl http://localhost:8000/api/targets/1
```

### Update Target

```bash
curl -X PATCH http://localhost:8000/api/targets/1 \
  -H "Content-Type: application/json" \
  -d '{
    "label": "Updated Label",
    "tags": ["production", "email", "critical"],
    "enabled": false
  }'
```

### Delete Target

```bash
curl -X DELETE http://localhost:8000/api/targets/1
```

### Bulk Delete Targets

```bash
curl -X POST http://localhost:8000/api/targets/bulk/delete \
  -H "Content-Type: application/json" \
  -d '{
    "target_ids": [1, 2, 3]
  }'
```

## Zone Management

### Add New Zone

```bash
curl -X POST http://localhost:8000/api/zones \
  -H "Content-Type: application/json" \
  -d '{
    "zone": "custom.dnsbl.example.org",
    "description": "Custom DNSBL Zone",
    "enabled": true
  }'
```

**Response:**

```json
{
  "message": "Zone custom.dnsbl.example.org created successfully",
  "id": 51
}
```

### List All Zones

```bash
curl http://localhost:8000/api/zones
```

**Response:**

```json
{
  "total": 51,
  "items": [
    {
      "id": 1,
      "zone": "zen.spamhaus.org",
      "description": "Default DNSBL zone",
      "enabled": true,
      "is_spamhaus": true,
      "created_at": "2024-01-01T00:00:00",
      "updated_at": "2024-01-01T00:00:00"
    }
  ]
}
```

### List Enabled Zones Only

```bash
curl "http://localhost:8000/api/zones?enabled_filter=true"
```

### Search Zones

```bash
curl "http://localhost:8000/api/zones?search=spamhaus"
```

### Get Single Zone

```bash
curl http://localhost:8000/api/zones/1
```

### Update Zone

```bash
curl -X PATCH http://localhost:8000/api/zones/1 \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Updated description",
    "enabled": false
  }'
```

### Delete Zone

```bash
curl -X DELETE http://localhost:8000/api/zones/1
```

### Initialize Default Zones

Load all default DNSBL zones from configuration.

```bash
curl -X POST http://localhost:8000/api/zones/default/initialize
```

**Response:**

```json
{
  "message": "Added 50 default zones, skipped 0 existing zones"
}
```

## Monitoring

### Trigger Manual Monitoring Run

Run a full monitoring check over all enabled targets and zones.

```bash
curl -X POST "http://localhost:8000/api/monitor/run?triggered_by=manual"
```

**Response:**

```json
{
  "id": 1,
  "triggered_by": "manual",
  "status": "running",
  "error_message": null,
  "total_targets": 10,
  "total_zones": 50,
  "total_checks": 0,
  "listed_count": 0,
  "blocked_count": 0,
  "error_count": 0,
  "started_at": "2024-01-01T00:00:00",
  "finished_at": null,
  "duration_seconds": null
}
```

### Run Monitoring on Specific Targets

```bash
curl -X POST http://localhost:8000/api/monitor/run \
  -H "Content-Type: application/json" \
  -d '{
    "target_ids": [1, 2, 3],
    "zone_ids": [1, 2, 3]
  }'
```

### List Monitoring Runs

```bash
curl http://localhost:8000/api/monitor/runs
```

**Response:**

```json
{
  "total": 10,
  "items": [
    {
      "id": 10,
      "triggered_by": "scheduler",
      "status": "completed",
      "error_message": null,
      "total_targets": 10,
      "total_zones": 50,
      "total_checks": 500,
      "listed_count": 5,
      "blocked_count": 0,
      "error_count": 2,
      "started_at": "2024-01-01T00:00:00",
      "finished_at": "2024-01-01T00:05:30",
      "duration_seconds": 330
    }
  ]
}
```

### Filter Monitoring Runs

```bash
# Filter by trigger type
curl "http://localhost:8000/api/monitor/runs?triggered_by=scheduler"

# Filter by status
curl "http://localhost:8000/api/monitor/runs?status_filter=completed"

# Paginate
curl "http://localhost:8000/api/monitor/runs?offset=0&limit=50"
```

### Get Specific Monitoring Run

```bash
curl http://localhost:8000/api/monitor/runs/10
```

## Status & History

### Get Latest Status for All Targets

```bash
curl http://localhost:8000/api/status
```

**Response:**

```json
[
  {
    "id": 1,
    "target": "1.2.3.4",
    "type": "ip",
    "label": "Production Mail Servers",
    "tags": ["production", "email"],
    "listed_count": 2,
    "blocked_count": 0,
    "error_count": 0,
    "last_checked": "2024-01-01T12:00:00",
    "issues": [
      {
        "zone": "zen.spamhaus.org",
        "status": "listed",
        "a_records": ["127.0.0.2"],
        "last_seen": "2024-01-01T12:00:00"
      }
    ]
  }
]
```

### Get Targets with Issues Only

```bash
curl "http://localhost:8000/api/status?has_issues_only=true"
```

### Filter Status by Type

```bash
curl "http://localhost:8000/api/status?type_filter=ip"
```

### Get Status Summary

```bash
curl http://localhost:8000/api/status/summary
```

**Response:**

```json
{
  "total_targets": 10,
  "listed_targets": 3,
  "blocked_targets": 0,
  "error_targets": 1,
  "last_run": {
    "id": 10,
    "triggered_by": "scheduler",
    "status": "completed",
    "started_at": "2024-01-01T00:00:00",
    "finished_at": "2024-01-01T00:05:30",
    "duration_seconds": 330,
    "listed_count": 5,
    "blocked_count": 0,
    "error_count": 2
  }
}
```

### Get Target History

```bash
curl http://localhost:8000/api/status/history/1?limit=50
```

**Response:**

```json
[
  {
    "zone": "zen.spamhaus.org",
    "status": "listed",
    "a_records": ["127.0.0.2"],
    "error_reason": null,
    "last_checked": "2024-01-01T12:00:00",
    "last_seen": "2024-01-01T12:00:00"
  },
  {
    "zone": "bl.spamcop.net",
    "status": "not_listed",
    "a_records": [],
    "error_reason": null,
    "last_checked": "2024-01-01T12:00:00",
    "last_seen": "2024-01-01T12:00:00"
  }
]
```

## Reports

### Generate Report

Create a new report (async generation).

```bash
curl -X POST http://localhost:8000/api/reports \
  -H "Content-Type: application/json" \
  -d '{
    "report_type": "csv",
    "date_from": "2024-01-01T00:00:00Z",
    "date_to": "2024-01-31T23:59:59Z",
    "target_ids": [1, 2, 3],
    "zone_ids": [1, 2, 3],
    "status_filter": "listed"
  }'
```

**Response:**

```json
{
  "id": 1,
  "report_type": "csv",
  "status": "pending",
  "error_message": null,
  "date_from": "2024-01-01T00:00:00",
  "date_to": "2024-01-31T23:59:59",
  "file_path": null,
  "file_size_bytes": null,
  "created_at": "2024-01-01T00:00:00",
  "completed_at": null
}
```

### Generate Excel Report

```bash
curl -X POST http://localhost:8000/api/reports \
  -H "Content-Type: application/json" \
  -d '{
    "report_type": "xlsx",
    "date_from": "2024-01-01T00:00:00Z",
    "date_to": "2024-12-31T23:59:59Z"
  }'
```

### Generate PDF Report

```bash
curl -X POST http://localhost:8000/api/reports \
  -H "Content-Type: application/json" \
  -d '{
    "report_type": "pdf"
  }'
```

### List Reports

```bash
curl http://localhost:8000/api/reports
```

**Response:**

```json
{
  "total": 5,
  "items": [
    {
      "id": 1,
      "report_type": "csv",
      "status": "completed",
      "error_message": null,
      "date_from": "2024-01-01T00:00:00",
      "date_to": "2024-01-31T23:59:59",
      "file_path": "./reports/report_20240101_120000.csv",
      "file_size_bytes": 45678,
      "created_at": "2024-01-01T12:00:00",
      "completed_at": "2024-01-01T12:00:05"
    }
  ]
}
```

### Get Specific Report

```bash
curl http://localhost:8000/api/reports/1
```

### Download Report

```bash
curl -O http://localhost:8000/api/reports/1/download
```

Or in a browser, navigate to:
```
http://localhost:8000/api/reports/1/download
```

### Delete Report

```bash
curl -X DELETE http://localhost:8000/api/reports/1
```

### Clean Up Old Reports

```bash
curl -X POST "http://localhost:8000/api/reports/cleanup?retention_days=30"
```

## Metrics

### Get Prometheus Metrics

```bash
curl http://localhost:8000/api/metrics
```

**Response (Prometheus format):**

```
# HELP dnsbl_check_requests_total Total number of DNSBL check requests
# TYPE dnsbl_check_requests_total counter
dnsbl_check_requests_total 1523

# HELP dnsbl_checks_completed_total Total number of DNSBL checks completed
# TYPE dnsbl_checks_completed_total counter
dnsbl_checks_completed_total 75432

# HELP dnsbl_checks_listed_total Total number of DNSBL checks that returned listed status
# TYPE dnsbl_checks_listed_total counter
dnsbl_checks_listed_total 1234

# HELP dnsbl_current_targets Current number of targets
# TYPE dnsbl_current_targets gauge
dnsbl_current_targets{type="ip",enabled="true"} 10
dnsbl_current_targets{type="ip",enabled="false"} 2
```

### Update Metrics

Manually trigger metrics update from database.

```bash
curl -X POST http://localhost:8000/api/metrics/update
```

## Health Check

```bash
curl http://localhost:8000/health
```

**Response:**

```json
{
  "status": "healthy",
  "app_name": "IP Reputation Monitor",
  "version": "1.0.0"
}
```

## Error Handling

### Rate Limit Exceeded

```json
{
  "detail": "Rate limit exceeded: 60 requests per minute"
}
```

### Validation Error

```json
{
  "detail": [
    {
      "loc": ["body", "ips"],
      "msg": "ensure this value has at least 1 items",
      "type": "value_error.list.min_items"
    }
  ]
}
```

### Not Found

```json
{
  "detail": "Target 999 not found"
}
```

## Tips

1. **Bulk Operations**: Use the batch endpoints for adding multiple targets
2. **Pagination**: Always use pagination for large datasets (`offset` and `limit` parameters)
3. **Filters**: Combine filters to narrow down results
4. **Cache**: Use cache endpoints to manage DNS query cache
5. **Async Operations**: Reports and monitor runs are asynchronous - poll the status endpoint

## Rate Limits

- **Default**: 60 requests per minute per client
- **Exceeded**: HTTP 429 with error message

## Notes

- All timestamps are in UTC
- `listed` status means the target is on the DNSBL
- `blocked` status (Spamhaus only) means query limit exceeded, not listed
- `error` status indicates DNS query failures
- `not_listed` means the target is clean on that zone
