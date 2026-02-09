# IP Reputation Monitor

A production-ready system for continuously monitoring email reputation of IP addresses and domains against DNSBL/RBL blacklists.

## Features

### Core Capabilities
- **DNSBL/RBL Checking**: Query multiple blacklist zones for IP addresses
- **Async DNS Resolution**: High-performance concurrent DNS queries with rate limiting
- **Smart Classification**: Proper handling of Spamhaus special return codes (127.255.255.x = BLOCKED, not LISTED)
- **In-Memory Caching**: Configurable TTL cache to reduce DNS queries
- **Rate Limiting**: Per-client API rate limits and per-zone DNS query throttling

### Monitoring & Automation
- **Scheduled Runs**: Background scheduler for automatic monitoring checks
- **Manual Triggers**: On-demand monitoring via API or UI
- **Alerting**: Webhook notifications on status changes
- **History Tracking**: Full audit trail of check results

### API
- **RESTful API**: Complete CRUD operations for targets and zones
- **Check Endpoint**: Bulk IP/DNSBL checking
- **Status API**: Latest status and historical data
- **Metrics**: Prometheus metrics endpoint
- **Rate Limited**: Per-client rate limiting protection

### Reports
- **Multiple Formats**: CSV, Excel (XLSX), PDF
- **Asynchronous Generation**: Background report generation
- **Flexible Filters**: Date range, target, zone, and status filters
- **Downloadable**: Direct download links for generated reports

### Web UI
- **Dashboard**: Overview cards with quick stats
- **Target Management**: Add, remove, enable/disable targets
- **Zone Management**: Manage blacklist zones
- **Reports**: Generate and download reports
- **Responsive**: Mobile-friendly design

## Quick Start

### Docker (Recommended)

```bash
# Clone or download the project
cd ip-reputation-monitor

# Start with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f

# Access the web UI
open http://localhost:8000
```

### Local Development

```bash
# Install Python 3.11+
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python -m app.main
```

The application will start on `http://localhost:8000`

## Configuration

Configure via environment variables or `.env` file:

```env
# App Settings
APP_NAME=IP Reputation Monitor
APP_VERSION=1.0.0
DEBUG=false

# Database
DATABASE_URL=sqlite:///./data/ip_reputation.db

# DNS Settings
DNS_TIMEOUT_MS=2500
DNS_NAMESERVERS=
DNS_CONCURRENCY=50
DNS_PER_ZONE_RATE_LIMIT=10

# Cache Settings
CACHE_TTL_MINUTES=60
CACHE_MAX_SIZE=10000

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60

# Scheduler
SCHEDULER_ENABLED=true
SCHEDULER_INTERVAL_MINUTES=30

# Alert Webhook
ALERT_WEBHOOK_URL=
ALERT_WEBHOOK_TIMEOUT_SEC=10

# Reports
REPORTS_DIR=./reports
REPORT_RETENTION_DAYS=30
REPORT_MAX_ROWS=50000

# CORS
CORS_ORIGINS=*

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### Configuration Details

| Variable | Default | Description |
|----------|---------|-------------|
| `DNS_TIMEOUT_MS` | 2500 | DNS query timeout in milliseconds |
| `DNS_CONCURRENCY` | 50 | Max concurrent DNS queries |
| `DNS_PER_ZONE_RATE_LIMIT` | 10 | Max DNS queries per second per zone |
| `CACHE_TTL_MINUTES` | 60 | Cache time-to-live in minutes |
| `RATE_LIMIT_PER_MINUTE` | 60 | API rate limit per client |
| `SCHEDULER_INTERVAL_MINUTES` | 30 | Monitoring run interval |
| `REPORT_RETENTION_DAYS` | 30 | Report file retention period |

## Default DNSBL Zones

The system includes 50+ default DNSBL zones:

- **Spamhaus**: zen.spamhaus.org, sbl.spamhaus.org, xbl.spamhaus.org, pbl.spamhaus.org
- **Spamcop**: bl.spamcop.net
- **Barracuda**: b.barracudacentral.org
- **CBL**: cbl.abuseat.org
- **Sorbs**: dnsbl.sorbs.net, smtp.dnsbl.sorbs.net, spam.dnsbl.sorbs.net
- **Abuse.ch**: spam.abuse.ch, drone.abuse.ch, combined.abuse.ch
- And many more...

See `app/core/config.py` for the complete list.

## API Documentation

Once running, access the interactive API documentation at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

### Quick API Examples

#### Check IPs against DNSBL

```bash
curl -X POST http://localhost:8000/api/check \
  -H "Content-Type: application/json" \
  -d '{
    "ips": ["1.2.3.4", "8.8.8.8"],
    "include_txt": false,
    "timeout_ms": 2500,
    "concurrency": 50
  }'
```

Response:
```json
{
  "summary": {
    "total_ips": 2,
    "listed_ips": 0,
    "blocked_ips": 0,
    "error_ips": 0
  },
  "results": [
    {
      "target": "1.2.3.4",
      "type": "ip",
      "listed": [],
      "blocked": [],
      "errors": [],
      "not_listed_zones_count": 50
    }
  ]
}
```

#### Add Targets

```bash
curl -X POST http://localhost:8000/api/targets \
  -H "Content-Type: application/json" \
  -d '{
    "targets": ["1.2.3.4", "8.8.8.8"],
    "type": "ip",
    "label": "Production Servers",
    "tags": ["production", "email"],
    "enabled": true
  }'
```

#### List Targets

```bash
curl http://localhost:8000/api/targets?limit=100
```

#### Trigger Monitoring Run

```bash
curl -X POST http://localhost:8000/api/monitor/run?triggered_by=manual
```

#### Get Status Summary

```bash
curl http://localhost:8000/api/status/summary
```

#### Generate Report

```bash
curl -X POST http://localhost:8000/api/reports \
  -H "Content-Type: application/json" \
  -d '{
    "report_type": "csv",
    "date_from": "2024-01-01T00:00:00Z",
    "date_to": "2024-12-31T23:59:59Z",
    "status_filter": "listed"
  }'
```

## Web UI

Access the web interface at `http://localhost:8000`:

### Pages
- **Dashboard**: Overview with stats and recent issues
- **Targets**: Manage IP addresses and domains
- **Zones**: Manage DNSBL blacklist zones
- **Reports**: Generate and download reports

## DNSBL Classification

The system classifies DNSBL query results as:

- **LISTED**: DNSBL returns an A record (except Spamhaus 127.255.255.x)
- **NOT_LISTED**: NXDOMAIN or NoAnswer for A record
- **ERROR**: Timeout, SERVFAIL, or other DNS errors
- **BLOCKED**: Spamhaus returns 127.255.255.x (limits exceeded, not actually listed)

### Spamhaus Special Handling

Spamhaus uses specific return codes that require special handling:

- `127.0.0.x` - The IP is LISTED
- `127.255.255.x` - Query is BLOCKED/limited (NOT listed)

This system correctly distinguishes between these cases.

## Important Notes

### DNSBL Usage Policies

**Please respect DNSBL usage policies:**

1. **Throttle Queries**: Use the per-zone rate limiting (default: 10 queries/second/zone)
2. **Cache Results**: The built-in cache helps reduce repeated queries
3. **Reasonable Intervals**: Don't query more frequently than needed (default: 30 minutes)
4. **Monitor for Blocks**: Check for 127.255.255.x returns which indicate you're being rate-limited

### Rate Limiting

The system implements multiple levels of rate limiting:

1. **API Rate Limiting**: Per-client limit (default: 60 requests/minute)
2. **Per-Zone DNS Throttling**: Maximum queries per second per zone
3. **Global Concurrency**: Max concurrent DNS queries

### Performance Considerations

- **Memory Usage**: Cache uses ~1KB per cached entry (10,000 entries = ~10MB)
- **Database**: SQLite for small deployments, PostgreSQL recommended for large scale
- **Concurrent Queries**: Adjust `DNS_CONCURRENCY` based on available bandwidth and DNS server limits

## Monitoring & Observability

### Health Check

```bash
curl http://localhost:8000/health
```

### Prometheus Metrics

```bash
curl http://localhost:8000/api/metrics
```

Available metrics:
- `dnsbl_check_requests_total` - Total check requests
- `dnsbl_checks_completed_total` - Completed checks
- `dnsbl_checks_listed_total` - Listed results
- `dnsbl_checks_blocked_total` - Blocked results
- `dnsbl_monitor_runs_total` - Monitor runs by type and status
- `dnsbl_current_targets` - Current target count by type and enabled status
- `dnsbl_cache_size` - Current cache size
- `dnsbl_alerts_total` - Alerts by type

### Logging

Logs are output in JSON format by default (configurable):

```json
{
  "asctime": "2024-01-01T12:00:00.000Z",
  "name": "app.main",
  "levelname": "INFO",
  "message": "Scheduled monitoring completed: 5 listed, 0 blocked, 2 errors"
}
```

## Troubleshooting

### High Blocked Count

If you see many BLOCKED results:
1. Reduce `DNS_PER_ZONE_RATE_LIMIT`
2. Increase `CACHE_TTL_MINUTES`
3. Increase `SCHEDULER_INTERVAL_MINUTES`

### Timeouts

If queries timeout frequently:
1. Increase `DNS_TIMEOUT_MS`
2. Reduce `DNS_CONCURRENCY`
3. Check network connectivity to DNS servers

### Database Lock Errors

For high-volume deployments:
1. Switch from SQLite to PostgreSQL
2. Update `DATABASE_URL` to PostgreSQL connection string

## Project Structure

```
ip-reputation-monitor/
├── app/
│   ├── api/              # API endpoints
│   ├── core/             # Core functionality (config, database)
│   ├── models/           # Database models and schemas
│   ├── services/         # Business logic (DNSBL, monitoring, reports)
│   ├── static/           # Static assets
│   ├── templates/        # Jinja2 templates for web UI
│   └── main.py           # FastAPI application
├── data/                 # Database storage (Docker volume)
├── reports/              # Generated reports (Docker volume)
├── Dockerfile            # Docker image definition
├── docker-compose.yml    # Docker Compose configuration
├── requirements.txt      # Python dependencies
└── README.md             # This file
```

## License

This project is provided as-is for monitoring email reputation purposes. Please respect DNSBL usage policies and terms of service.

## Support

For issues and questions:
1. Check the API documentation at `/docs`
2. Review the configuration examples in `.env.example`
3. Check logs for detailed error messages
