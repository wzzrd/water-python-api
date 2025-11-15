# Water Python API - TODO List

This document tracks planned improvements, optimizations, and feature additions for the water meter monitoring system.

## Security Issues (Critical - Must Fix)

### SQL Injection Vulnerabilities

- [x] **Fix SQL injection in water-python-api.py:100** ✅
  - Issue: Database name is constructed with f-string in `CREATE DATABASE` statement
  - Fix: Use `sql.Identifier()` from `psycopg2.sql` or validate database name against allowlist
  - Location: `water-python-api.py:100`
  - Severity: High
  - **Status**: Fixed in commit 763f22e

- [x] **Fix SQL injection in maintenance-logger.py:97** ✅
  - Issue: Days parameter is interpolated into SQL `INTERVAL` clause using string formatting
  - Fix: Use parameterized interval construction: `INTERVAL '1 day' * %s`
  - Location: `maintenance-logger.py:97`
  - Severity: High
  - **Status**: Fixed in commit 9349800

### Timezone Handling

- [ ] **Fix timezone-aware datetime usage in water-python-api.py:264**
  - Issue: Using naive `datetime.now()` instead of timezone-aware timestamps
  - Fix: Use `datetime.now(timezone.utc)` or configure PostgreSQL timezone handling
  - Location: `water-python-api.py:264`
  - Impact: Could cause data integrity issues across timezones

- [ ] **Fix naive datetime comparison in maintenance-logger.py:142**
  - Issue: Strips timezone info with `.replace(tzinfo=None)` for days_ago calculation
  - Fix: Keep timezone-aware datetimes throughout, use proper timezone conversions
  - Location: `maintenance-logger.py:142`
  - Impact: Incorrect "days ago" calculations near DST changes

## Code Quality Improvements

### Input Validation

- [ ] **Add input validation for total_liter_offset_m3**
  - Issue: Empty strings from API could cause conversion errors
  - Fix: Add try/except or default value handling for optional float conversions
  - Location: `water-python-api.py:270`

### Code Cleanup

- [ ] **Remove unused threading import**
  - Location: `water-python-api.py:18`
  - Impact: Minor - code cleanliness

- [ ] **Add database connection cleanup to maintenance-logger.py**
  - Issue: No `db_conn.close()` in main() function
  - Fix: Add try/finally block or context manager for connection lifecycle
  - Impact: Resource leaks in long-running scripts or automated calls

- [ ] **Replace print statements with logging module in maintenance-logger.py**
  - Issue: Inconsistent with daemon's use of logging module
  - Fix: Configure logging and use `logger.info()`, `logger.error()`, etc.
  - Impact: Better log management, filtering, and integration with systemd

## Feature Additions

### CLI Enhancements

- [ ] **Add 'last-change' command to maintenance-logger.py**
  - Feature: Show the most recent maintenance activity of any type with "X days ago"
  - Implementation: Query `maintenance_log` ordered by time DESC LIMIT 1
  - User requirement: "a way to make the CLI output the moment of the last 'block change', including a '17 days ago' bit"
  - Example output: `Last maintenance: filter_change on 2025-10-29 (17 days ago)`

### REST API Service (New Component)

- [ ] **Create REST API service (api-server.py)**
  - Framework: FastAPI recommended (auto docs, type safety, async support) or Flask
  - Port: 8080 (configurable via environment variable)
  - Database: Reuse connection pattern from existing code
  - Features: CORS support, health check endpoint, error handling

- [ ] **Add raw metrics API endpoint**
  - Endpoint: `GET /api/metrics/raw?period=(day|week|month)`
  - Returns: Time-series water readings for the specified period
  - Query: `SELECT time, total_liter_m3, active_liter_lpm FROM water_readings WHERE time >= NOW() - INTERVAL ...`
  - Response format: JSON array of readings

- [ ] **Add aggregated metrics API endpoint**
  - Endpoint: `GET /api/metrics/aggregated?period=(day|week|month)&interval=(15min|1hour|1day)`
  - Returns: Time-bucketed aggregated readings using TimescaleDB's `time_bucket()`
  - Query: Use `time_bucket('15 minutes', time)`, aggregate with AVG/MAX/MIN
  - Response format: JSON array of bucketed readings

- [ ] **Add averages calculation API endpoint**
  - Endpoint: `GET /api/metrics/averages?period=(day|week|month)`
  - Returns: Average consumption per time-of-day or per day for comparison overlay
  - Implementation: Calculate historical averages for same time periods
  - Use case: "show average usage over that same period (so I can see how water usage was today at 7pm compared to average usage)"

- [ ] **Add maintenance history API endpoint**
  - Endpoint: `GET /api/maintenance?days=N`
  - Returns: Maintenance log entries for the last N days
  - Reuse logic from `maintenance-logger.py:list_recent_maintenance()`

### Web Frontend (New Component)

- [ ] **Create web frontend structure**
  - Framework: Static HTML/CSS/JavaScript (vanilla or lightweight framework)
  - Deployment: Served by API server or separate static file server
  - Structure: `static/index.html`, `static/css/`, `static/js/`
  - Responsive design for desktop and mobile

- [ ] **Add charting library**
  - Library: Chart.js recommended (lightweight, excellent time-series support)
  - Alternative: Plotly.js for more interactive features
  - Configuration: Time-series charts with zoom, pan, tooltips

- [ ] **Implement last-day raw usage graph**
  - Feature: Plot actual meter readings from last 24 hours
  - Data source: `/api/metrics/raw?period=day`
  - Chart type: Line chart with time on X-axis, consumption on Y-axis
  - Metrics: Both total consumption and flow rate

- [ ] **Implement last-day aggregated usage graphs**
  - Feature: Toggle between 15min/1hour/1day aggregation intervals
  - Data source: `/api/metrics/aggregated?period=day&interval=...`
  - UI: Buttons or dropdown to switch between aggregation levels
  - Chart: Update same graph with different granularity

- [ ] **Add average usage overlay to graphs**
  - Feature: Show comparative average line on usage graphs
  - Data source: `/api/metrics/averages?period=day`
  - Implementation: Add second dataset to Chart.js as dashed line
  - Label: "Average usage" with different color
  - User requirement: "shows a line on the graphs above that indicates average usage over that same period"

- [ ] **Add week and month graph views**
  - Feature: Extend time range visualization beyond last day
  - Implementation: Duplicate graph components with period parameter
  - Tabs or navigation: "Last Day", "Last Week", "Last Month"
  - Aggregation: Automatic based on time range (week=1hour, month=1day)

### Deployment & Containerization

- [ ] **Create Containerfile for API server**
  - Base: Same Red Hat UBI 10 as daemon
  - Dependencies: python3-fastapi (or flask), python3-uvicorn, python3-psycopg2
  - Health check: `curl localhost:8080/health`
  - Non-root user: UID 1001
  - Expose port: 8080

- [ ] **Create Quadlet configuration for API server**
  - File: `water-api-server.container`
  - Environment variables: Same DB_* vars as daemon, plus API_PORT
  - Network: Publish port 8080:8080
  - Dependency: Optional systemd dependency on water-python-api.service

- [ ] **Update README.md with API server documentation**
  - Section: API Server deployment instructions
  - Document: All API endpoints with examples
  - Document: Web frontend access (http://server:8080/)
  - Document: Environment variables for API server
  - Example: cURL commands for each endpoint

## Implementation Notes

### TimescaleDB Optimization

- Use `time_bucket()` for all aggregation queries - much faster than GROUP BY on time ranges
- Consider continuous aggregates for frequently accessed metrics (daily/hourly summaries)
- Use `first()` and `last()` functions for bucket aggregations instead of MIN/MAX when appropriate

### API Design

- RESTful endpoints with consistent naming
- Proper HTTP status codes (200, 400, 404, 500)
- Error responses in JSON format with `{"error": "message"}`
- API versioning: Consider `/api/v1/` prefix for future compatibility
- Rate limiting: Add in production to prevent abuse
- Authentication: Consider API keys or JWT for production deployments

### Frontend Architecture

- Keep it simple: No build process needed if using vanilla JS
- Progressive enhancement: Works without JavaScript for basic info
- Cache API responses in browser (Cache-Control headers)
- Error handling: Display user-friendly messages when API unavailable
- Loading states: Show spinners while fetching data

### Security Considerations

- API CORS configuration: Restrict to specific origins in production
- Input sanitization: Validate all API query parameters
- SQL injection: All queries must use parameterized statements
- Secrets: Never log DB_PASSWORD or expose in API responses
- Container security: Run as non-root, minimal attack surface

## Testing Checklist

Before marking items complete, ensure:

- [ ] Manual testing with real data
- [ ] Error scenarios tested (API down, DB connection lost, invalid input)
- [ ] Container builds successfully
- [ ] Quadlet service starts and restarts on failure
- [ ] Logs are informative and don't contain sensitive data
- [ ] Performance is acceptable with large datasets (1M+ readings)
- [ ] Documentation is updated

## Future Enhancements (Low Priority)

- [ ] Add Grafana dashboard support with TimescaleDB datasource
- [ ] Implement ML-based leak detection
- [ ] Multi-meter support in single deployment
- [ ] Automated data backup and archival
- [ ] Email/SMS alerting for anomalies
- [ ] Mobile app or PWA for frontend
- [ ] Unit tests with pytest
- [ ] CI/CD pipeline for automated builds

---

**Last Updated**: 2025-11-15
**Priority**: Security fixes first, then CLI enhancement, then API/frontend features
