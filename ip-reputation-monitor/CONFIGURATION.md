# Configuration Guide

This guide explains all configuration options for the IP Reputation Monitor.

## Environment Variables

Configure the application via environment variables or a `.env` file.

### Application Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | IP Reputation Monitor | Application name |
| `APP_VERSION` | 1.0.0 | Application version |
| `DEBUG` | false | Enable debug mode (more verbose logging, auto-reload) |

### Server Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | 0.0.0.0 | Server bind address |
| `PORT` | 8000 | Server port |
| `WORKERS` | 4 | Number of worker processes (production) |

### Database Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | sqlite:///./data/ip_reputation.db | Database connection string |

**Database URL Formats:**

- **SQLite**: `sqlite:///./data/ip_reputation.db`
- **PostgreSQL**: `postgresql://user:password@host:port/database`
- **MySQL**: `mysql://user:password@host:port/database`

**Recommendation:**
- Small deployments (< 1000 targets): SQLite
- Large deployments (> 1000 targets): PostgreSQL

### DNS Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DNS_TIMEOUT_MS` | 2500 | DNS query timeout in milliseconds (100-30000) |
| `DNS_NAMESERVERS` | (empty) | Comma-separated list of DNS servers |
| `DNS_MAX_RETRIES` | 2 | Max retry attempts for failed DNS queries |
| `DNS_CONCURRENCY` | 50 | Max concurrent DNS queries (1-500) |
| `DNS_PER_ZONE_RATE_LIMIT` | 10 | Max DNS queries per second per zone |

**DNS Nameservers Example:**
```
DNS_NAMESERVERS=8.8.8.8,1.1.1.1,8.8.4.4
```

**Performance Tuning:**
- **Fast network**: Increase `DNS_CONCURRENCY` to 100-200
- **Slow DNS servers**: Decrease `DNS_CONCURRENCY` to 10-25
- **Many zones**: Increase `DNS_PER_ZONE_RATE_LIMIT` (be careful of DNSBL blocks)
- **Timeout issues**: Increase `DNS_TIMEOUT_MS` to 5000-10000

### Cache Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `CACHE_TTL_MINUTES` | 60 | Cache time-to-live in minutes (30-240) |
| `CACHE_MAX_SIZE` | 10000 | Maximum number of cached entries (1000-100000) |

**Cache Memory Usage:**
Approximately 1KB per cached entry.

- 10,000 entries = ~10MB
- 50,000 entries = ~50MB

**Recommendation:**
- Small deployment: `CACHE_TTL_MINUTES=30`, `CACHE_MAX_SIZE=5000`
- Large deployment: `CACHE_TTL_MINUTES=120`, `CACHE_MAX_SIZE=50000`

### Rate Limiting Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `RATE_LIMIT_PER_MINUTE` | 60 | API rate limit per client (10-1000) |
| `RATE_LIMIT_BURST` | 10 | Rate limit burst size (1-50) |

**Rate Limiting protects:**
- API endpoint abuse
- DNS server overload
- System resource exhaustion

**Recommendation:**
- Public API: `RATE_LIMIT_PER_MINUTE=30`
- Internal API: `RATE_LIMIT_PER_MINUTE=300`

### Scheduler Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `SCHEDULER_ENABLED` | true | Enable/disable background scheduler |
| `SCHEDULER_INTERVAL_MINUTES` | 30 | Monitoring run interval (5-120) |

**Scheduler Considerations:**
- **Frequent checks (5-15 min)**: More up-to-date, higher DNSBL usage
- **Moderate checks (30-60 min)**: Balanced, recommended for most
- **Infrequent checks (2-4 hours)**: Lower DNSBL usage, less timely

**Important**: Always respect DNSBL usage policies. More frequent checks may get you blocked.

### Alert Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `ALERT_WEBHOOK_URL` | (empty) | Webhook URL for alert notifications |
| `ALERT_WEBHOOK_TIMEOUT_SEC` | 10 | Webhook timeout in seconds |

**Webhook Payload Example:**

```json
{
  "run_id": 123,
  "triggered_by": "scheduler",
  "started_at": "2024-01-01T00:00:00",
  "summary": {
    "listed_count": 5,
    "blocked_count": 0,
    "error_count": 2
  },
  "alerts": [
    {
      "type": "newly_listed",
      "target": "1.2.3.4",
      "zone": "zen.spamhaus.org",
      "old_status": "not_listed",
      "new_status": "listed",
      "message": "Target 1.2.3.4 is now listed on zen.spamhaus.org",
      "created_at": "2024-01-01T00:00:00"
    }
  ]
}
```

**Webhook Integration Examples:**

- **Slack**: Use Slack Incoming Webhook URL
- **Microsoft Teams**: Use Teams Incoming Webhook URL
- **Custom**: Implement your own webhook handler

### Report Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `REPORTS_DIR` | ./reports | Directory for report files |
| `REPORT_RETENTION_DAYS` | 30 | Report file retention in days |
| `REPORT_MAX_ROWS` | 50000 | Maximum rows per report |

**Report Types:**
- CSV: Lightweight, easy to parse
- XLSX: Multiple sheets, formatted tables
- PDF: Human-readable, printable

### CORS Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `CORS_ORIGINS` | * | Allowed origins for CORS (comma-separated) |

**Examples:**
```
CORS_ORIGINS=*                                  # Allow all
CORS_ORIGINS=http://localhost:3000              # Single origin
CORS_ORIGINS=http://localhost:3000,https://example.com  # Multiple origins
```

**Security Note:** Don't use `*` in production. Specify exact origins.

### Logging Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | INFO | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `LOG_FORMAT` | json | Log format (json or text) |

**Log Levels:**
- **DEBUG**: Detailed diagnostic information
- **INFO**: General informational messages (recommended for production)
- **WARNING**: Warning messages for potentially harmful situations
- **ERROR**: Error messages for serious problems
- **CRITICAL**: Critical error messages

**Log Formats:**
- **JSON**: Structured logs for log aggregation systems (ELK, Splunk)
- **Text**: Human-readable logs for development/small deployments

## Configuration Examples

### Development Configuration

```env
DEBUG=true
LOG_LEVEL=DEBUG
LOG_FORMAT=text
DATABASE_URL=sqlite:///./data/ip_reputation.db
SCHEDULER_ENABLED=false
```

### Production Configuration (Small)

```env
DEBUG=false
LOG_LEVEL=INFO
LOG_FORMAT=json
DATABASE_URL=postgresql://user:pass@db:5432/iprep
DNS_CONCURRENCY=50
CACHE_TTL_MINUTES=60
SCHEDULER_ENABLED=true
SCHEDULER_INTERVAL_MINUTES=30
RATE_LIMIT_PER_MINUTE=60
CORS_ORIGINS=https://example.com
```

### Production Configuration (Large)

```env
DEBUG=false
LOG_LEVEL=INFO
LOG_FORMAT=json
DATABASE_URL=postgresql://user:pass@db:5432/iprep
DNS_CONCURRENCY=200
DNS_PER_ZONE_RATE_LIMIT=15
CACHE_TTL_MINUTES=120
CACHE_MAX_SIZE=50000
SCHEDULER_ENABLED=true
SCHEDULER_INTERVAL_MINUTES=60
RATE_LIMIT_PER_MINUTE=300
CORS_ORIGINS=https://example.com,https://api.example.com
ALERT_WEBHOOK_URL=https://hooks.slack.com/services/XXX/YYY/ZZZ
REPORT_RETENTION_DAYS=7
```

## DNSBL Zone Configuration

### Default Zones

The system includes 50+ default DNSBL zones (see `app/core/config.py`).

### Adding Custom Zones

1. **Via API**:
```bash
curl -X POST http://localhost:8000/api/zones \
  -H "Content-Type: application/json" \
  -d '{
    "zone": "custom.dnsbl.example.org",
    "description": "Custom DNSBL",
    "enabled": true
  }'
```

2. **Via Web UI**: Navigate to Zones page and add zone

3. **Via Configuration**: Edit `app/core/config.py` and add to `DEFAULT_ZONES`

### Spamhaus Special Zones

The system automatically handles Spamhaus special return codes:

- `127.0.0.x` - LISTED (IP is actually on the blacklist)
- `127.255.255.x` - BLOCKED (query rate limited, not actually listed)

**Special zones:**
- zen.spamhaus.org
- sbl.spamhaus.org
- xbl.spamhaus.org
- pbl.spamhaus.org

## Performance Tuning

### High Throughput (10,000+ targets)

```env
DNS_CONCURRENCY=200
DNS_PER_ZONE_RATE_LIMIT=20
CACHE_TTL_MINUTES=120
CACHE_MAX_SIZE=100000
WORKERS=8
```

### Low Latency (Fast response)

```env
DNS_TIMEOUT_MS=1000
DNS_CONCURRENCY=100
CACHE_TTL_MINUTES=30
```

### Conservative (Avoid DNSBL blocks)

```env
DNS_CONCURRENCY=25
DNS_PER_ZONE_RATE_LIMIT=5
CACHE_TTL_MINUTES=120
SCHEDULER_INTERVAL_MINUTES=60
```

## Monitoring Recommendations

### Prometheus Metrics

Available at `/api/metrics`:

- `dnsbl_check_requests_total` - Total check requests
- `dnsbl_checks_completed_total` - Completed checks
- `dnsbl_checks_listed_total` - Listed results
- `dnsbl_checks_blocked_total` - Blocked results
- `dnsbl_checks_error_total` - Error results
- `dnsbl_monitor_runs_total` - Monitor runs by type/status
- `dnsbl_monitor_run_duration_seconds` - Run duration histogram
- `dnsbl_current_targets` - Target counts by type/status
- `dnsbl_current_zones` - Zone counts by status
- `dnsbl_cache_size` - Current cache size
- `dnsbl_alerts_total` - Alert counts by type

### Key Metrics to Monitor

1. **High blocked counts**: May indicate DNSBL rate limiting
2. **High error rates**: Network/DNS issues
3. **Cache hit ratio**: Should be > 80% after initial warmup
4. **Run duration**: Should be relatively stable
5. **Alert volume**: Unexpected increases may indicate issues

### Alert Thresholds (Example)

- **Blocked rate > 10%**: Increase cache TTL, reduce concurrency
- **Error rate > 5%**: Check network connectivity
- **Run duration > 2x normal**: Check DNS server performance
- **Alerts per hour > 50**: Major reputation issue

## Troubleshooting

### DNS Timeout Issues

**Symptom**: Many checks timeout

**Solutions**:
1. Increase `DNS_TIMEOUT_MS` to 5000-10000
2. Reduce `DNS_CONCURRENCY`
3. Check network connectivity to DNS servers
4. Try alternative DNS servers

### High Blocked Counts

**Symptom**: Many Spamhaus BLOCKED results

**Solutions**:
1. Reduce `DNS_PER_ZONE_RATE_LIMIT` to 5-10
2. Increase `CACHE_TTL_MINUTES` to 120-240
3. Increase `SCHEDULER_INTERVAL_MINUTES` to 60-120
4. Consider disabling some Spamhaus zones temporarily

### Memory Issues

**Symptom**: High memory usage

**Solutions**:
1. Reduce `CACHE_MAX_SIZE`
2. Reduce `DNS_CONCURRENCY`
3. Use PostgreSQL instead of SQLite for large deployments

### Slow Performance

**Symptom**: Slow check responses

**Solutions**:
1. Increase `DNS_CONCURRENCY`
2. Enable or increase cache
3. Use faster DNS servers
4. Check for network bottlenecks
5. Use PostgreSQL for database

## Security Considerations

### Production Checklist

- [ ] Set `DEBUG=false`
- [ ] Use strong database password
- [ ] Set specific `CORS_ORIGINS` (not `*`)
- [ ] Use HTTPS/TLS in production
- [ ] Set appropriate `RATE_LIMIT_PER_MINUTE`
- [ ] Configure firewall rules
- [ ] Enable log aggregation
- [ ] Monitor metrics
- [ ] Set up alerting
- [ ] Regular backups of database

### API Security

1. **Rate Limiting**: Protects against API abuse
2. **CORS**: Restrict to known origins
3. **Input Validation**: All inputs validated
4. **SQL Injection**: Uses SQLAlchemy ORM (protected)
5. **XSS**: Templates auto-escape (protected)

## Best Practices

1. **Start Conservative**: Use default settings, adjust based on results
2. **Monitor Closely**: Watch metrics and logs initially
3. **Respect DNSBL Policies**: Throttle queries, use caching
4. **Test in Staging**: Test configuration changes before production
5. **Backup Data**: Regular database backups
6. **Document Changes**: Keep track of configuration changes
7. **Plan Scaling**: Architecture should support growth

## Getting Help

1. Check logs for detailed error messages
2. Review metrics for performance indicators
3. Consult API documentation at `/docs`
4. Review configuration examples above
5. Check DNSBL-specific documentation for zone details
