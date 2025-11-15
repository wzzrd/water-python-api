# CLAUDE.md - Water Python API Project Guide

## Project Overview

This is a **Water Meter Data Collection System** that monitors water usage through API polling and stores time-series data in TimescaleDB. The system consists of:

1. A daemon that continuously collects water meter readings
2. A CLI tool for logging maintenance activities (salt replacements, filter changes, etc.)
3. Containerized deployment using Podman/Red Hat UBI

**Primary Purpose**: Real-time water consumption monitoring and maintenance tracking for home/facility water systems.

## Codebase Structure

```
water-python-api/
├── water-python-api.py       # Main daemon - polls water meter API and stores data
├── maintenance-logger.py      # CLI tool for logging maintenance activities
├── Containerfile              # Red Hat UBI container definition
├── buildrun.sh                # Podman build script
└── .gitignore                 # Python-specific gitignore
```

### Core Components

#### 1. `water-python-api.py` (Main Daemon)

**Location**: `/home/user/water-python-api/water-python-api.py`

**Purpose**: Long-running daemon that:
- Polls water meter API at configurable intervals
- Stores readings in TimescaleDB
- Handles database creation and schema setup automatically
- Implements health checks and graceful shutdown
- Manages connection failures with retry logic

**Key Classes**:
- `WaterMeterDaemon` (line 29): Main daemon class with methods:
  - `_connect_database()` (line 67): Database connection with auto-create
  - `_setup_schema()` (line 125): Creates tables and hypertables
  - `_read_meter()` (line 223): Polls water meter API
  - `_store_reading()` (line 248): Inserts readings into database
  - `run()` (line 292): Main event loop

**Database Tables Created**:
- `water_readings`: Time-series water consumption data
- `maintenance_log`: Maintenance activity tracking

#### 2. `maintenance-logger.py` (Maintenance CLI)

**Location**: `/home/user/water-python-api/maintenance-logger.py`

**Purpose**: Command-line tool for logging and viewing maintenance activities.

**Key Classes**:
- `MaintenanceLogger` (line 15): Handles maintenance operations

**Available Commands**:
- `salt`: Log salt block replacement
- `log`: Log general maintenance (filters, repairs, inspections)
- `list`: View recent maintenance activities
- `last-salt`: Show last salt replacement date

**Usage Examples**:
```bash
# Log salt replacement
./maintenance-logger.py salt --quantity 25 --cost 15.99 --brand "AquaPure"

# Log filter change
./maintenance-logger.py log filter_change --description "Main filter" --cost 45.00

# List last 60 days of maintenance
./maintenance-logger.py list --days 60

# Check last salt replacement
./maintenance-logger.py last-salt
```

#### 3. `Containerfile` (Container Definition)

**Base Image**: Red Hat UBI 10 (`registry.redhat.io/ubi10/ubi:latest`)

**Features**:
- Non-root user execution (user ID 1001)
- Python 3 with psycopg2 and requests
- Health check for meter API connectivity
- Follows Red Hat container best practices

#### 4. `buildrun.sh` (Build Script)

**Purpose**: Builds container image using Podman

**Image Registry**: `quay.thuisnet.com/apps/water-python-api`

**Note**: The run commands are currently disabled (line 20: `exit 0`)

## Database Schema

### TimescaleDB Configuration

The system uses **PostgreSQL with TimescaleDB extension** for time-series data storage.

### Table: `water_readings`

**Purpose**: Stores water meter readings over time

**Schema** (created at water-python-api.py:138-149):
```sql
CREATE TABLE water_readings (
    time TIMESTAMPTZ NOT NULL,              -- Timestamp of reading
    meter_id TEXT NOT NULL,                 -- Identifier for the meter
    total_liter_m3 NUMERIC(12,3) NOT NULL, -- Total consumption in m³
    active_liter_lpm NUMERIC(8,3) NOT NULL,-- Current flow rate in L/min
    wifi_strength INTEGER NOT NULL,         -- WiFi signal strength
    wifi_ssid TEXT,                         -- WiFi network name
    total_liter_offset_m3 NUMERIC(12,3),   -- Offset for calibration
    PRIMARY KEY (time, meter_id)
);
```

**Hypertable**: Converted to TimescaleDB hypertable for efficient time-series queries (line 180)

**Indexes**:
- `idx_water_readings_meter_time`: On `(meter_id, time DESC)` for efficient queries

### Table: `maintenance_log`

**Purpose**: Tracks maintenance activities (salt replacements, filter changes, repairs, etc.)

**Schema** (created at water-python-api.py:153-167):
```sql
CREATE TABLE maintenance_log (
    id SERIAL,                          -- Auto-increment ID
    time TIMESTAMPTZ NOT NULL,          -- Timestamp of maintenance
    meter_id TEXT NOT NULL,             -- Meter identifier
    maintenance_type TEXT NOT NULL,     -- Type (salt_replacement, filter_change, etc.)
    description TEXT,                   -- Detailed description
    quantity NUMERIC(10,3),             -- Amount (e.g., kg of salt)
    unit TEXT,                          -- Unit of measurement
    cost NUMERIC(10,2),                 -- Cost in currency
    notes TEXT,                         -- Additional notes
    created_by TEXT DEFAULT 'system',   -- Who logged it
    PRIMARY KEY (time, id)
);
```

**Hypertable**: Converted to TimescaleDB hypertable (line 192)

**Indexes**:
- `idx_maintenance_log_meter_time`: On `(meter_id, time DESC)`
- `idx_maintenance_log_type`: On `(meter_id, maintenance_type, time DESC)`

## Configuration

All configuration is managed through **environment variables**.

### Required Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DB_USER` | Database username | Yes |
| `DB_PASSWORD` | Database password | Yes |

### Optional Variables (with defaults)

| Variable | Default | Description |
|----------|---------|-------------|
| `METER_API_URL` | `http://192.168.1.100/api/data` | Water meter API endpoint |
| `METER_API_TIMEOUT` | `10` | API request timeout (seconds) |
| `COLLECTION_INTERVAL` | `300` | Polling interval (seconds, default 5 min) |
| `METER_ID` | `default_meter` | Identifier for this meter |
| `DB_HOST` | `localhost` | Database host |
| `DB_PORT` | `5432` | Database port |
| `DB_NAME` | `watermeter` | Database name |

### Example Configuration

```bash
export METER_API_URL="http://watermeter.thuisnet.com/api/v1/data"
export METER_ID="meterkast"
export COLLECTION_INTERVAL="300"
export DB_HOST="localhost"
export DB_NAME="water"
export DB_USER="postgres"
export DB_PASSWORD="your_secure_password"
```

## Development Workflows

### Local Development

**Prerequisites**:
- Python 3.x
- PostgreSQL with TimescaleDB extension
- Python packages: `psycopg2`, `requests`

**Install Dependencies** (Red Hat/Fedora):
```bash
sudo dnf install python3-psycopg2 python3-requests
```

**Run Daemon Locally**:
```bash
# Set environment variables
export DB_USER="postgres"
export DB_PASSWORD="your_password"
export METER_API_URL="http://your-meter-api/data"

# Run daemon
./water-python-api.py
```

**Run Maintenance Logger**:
```bash
# Same environment variables as daemon
./maintenance-logger.py salt --quantity 25 --cost 15.99
```

### Container Development

**Build Image**:
```bash
./buildrun.sh
# Or manually:
podman build -f Containerfile -t quay.thuisnet.com/apps/water-python-api:latest .
```

**Run Container**:
```bash
podman run -d \
    --name water-python-api \
    --restart unless-stopped \
    -e METER_API_URL="http://watermeter.thuisnet.com/api/v1/data" \
    -e METER_ID="meterkast" \
    -e COLLECTION_INTERVAL="300" \
    -e DB_HOST="your-db-host" \
    -e DB_NAME="water" \
    -e DB_USER="postgres" \
    -e DB_PASSWORD="your_password" \
    quay.thuisnet.com/apps/water-python-api:latest
```

**View Logs**:
```bash
podman logs -f water-python-api
```

### Git Workflow

**Current Branch**: `claude/claude-md-mi03jisxphsinf8u-01WqGs9EAEjYEdSwnHJofT2f`

**Commit History**:
```
3145056 - add gitignore
675b996 - add maintenance table creation
6bcad57 - add maintenance script
305588f - add maintenance table
e11b387 - initial commit
```

**Git Operations**:
- Always develop on Claude-specific branches (`claude/*`)
- Use descriptive commit messages
- Push with: `git push -u origin <branch-name>`

## Key Conventions for AI Assistants

### Code Style

1. **Python Standards**:
   - PEP 8 compliant
   - Type hints in function signatures (see `typing` imports)
   - Docstrings for classes and functions
   - Snake_case for variables and functions
   - PascalCase for class names

2. **Logging**:
   - Use Python's `logging` module (not print statements in daemon)
   - Log levels: INFO for normal operations, ERROR for failures, DEBUG for detailed info
   - Format: `"%(asctime)s - %(name)s - %(levelname)s - %(message)s"`

3. **Error Handling**:
   - Specific exception catching (`psycopg2.Error`, `requests.RequestException`)
   - Graceful degradation with retry logic
   - Health checks with consecutive failure tracking (max 5 failures)

### Database Conventions

1. **Table Naming**: Lowercase with underscores (e.g., `water_readings`, `maintenance_log`)
2. **Column Naming**: Lowercase with underscores
3. **Time Columns**: Always use `TIMESTAMPTZ` (timezone-aware)
4. **Primary Keys**: Composite keys with `(time, <id>)` for time-series tables
5. **Hypertables**: All time-series tables should be TimescaleDB hypertables
6. **Indexes**: Create indexes on frequently queried columns (meter_id, time, type)

### API Expectations

The water meter API is expected to return JSON with these fields:

**Required Fields**:
- `total_liter_m3` (float): Total consumption in cubic meters
- `active_liter_lpm` (float): Current flow rate in liters per minute
- `wifi_strength` (int): WiFi signal strength

**Optional Fields**:
- `wifi_ssid` (string): WiFi network name
- `total_liter_offset_m3` (float): Calibration offset

### Maintenance Types

Common maintenance type strings (used in `maintenance_log.maintenance_type`):
- `salt_replacement`: Water softener salt block replacement
- `filter_change`: Water filter replacement
- `inspection`: System inspection
- `repair`: Equipment repair
- `cleaning`: System cleaning
- `calibration`: Meter calibration

### Security Considerations

1. **No Hardcoded Credentials**: All sensitive data via environment variables
2. **Non-Root Container**: Container runs as UID 1001
3. **Database Auto-Commit**: Enabled to prevent transaction issues
4. **SQL Injection Prevention**: All queries use parameterized statements (`%s` placeholders)
5. **Secrets Management**: Never commit `.env` files (see .gitignore:177-178)

## Common AI Assistant Tasks

### Task 1: Adding New Meter Data Fields

**When**: New sensor data becomes available from the meter API

**Steps**:
1. Modify `water_readings` table schema in `_setup_schema()` (water-python-api.py:138)
2. Add field validation in `_read_meter()` (water-python-api.py:233)
3. Update INSERT statement in `_store_reading()` (water-python-api.py:252)
4. Update Containerfile HEALTHCHECK if field is critical (Containerfile:40)

**Example**: Adding temperature monitoring
```python
# In _setup_schema():
CREATE TABLE IF NOT EXISTS water_readings (
    ...
    temperature_celsius NUMERIC(5,2),  # Add this
    ...
);

# In _read_meter():
optional_fields = ["wifi_ssid", "temperature_celsius"]  # Add to validation

# In _store_reading():
cursor.execute(insert_sql, (
    ...
    float(reading_data.get("temperature_celsius", 0)),
    ...
))
```

### Task 2: Adding New Maintenance Types

**When**: New maintenance activities need to be tracked

**Steps**:
1. Add new subparser to `maintenance-logger.py` argparse setup (line 159)
2. Add handler in main() function (line 194)
3. Document the new type in this CLAUDE.md

**Example**: Adding "pump_service"
```python
# In argparse section:
pump_parser = subparsers.add_parser('pump', help='Log pump service')
pump_parser.add_argument('--hours', type=float, help='Service hours')
pump_parser.add_argument('--cost', type=float, help='Service cost')

# In main():
elif args.command == 'pump':
    logger.log_maintenance(
        maintenance_type='pump_service',
        description='Pump maintenance',
        quantity=args.hours,
        unit='hours',
        cost=args.cost
    )
```

### Task 3: Modifying Collection Interval Logic

**When**: Need dynamic polling or rate limiting

**Location**: `water-python-api.py:336` (main loop sleep)

**Considerations**:
- Ensure health checks still run periodically
- Update container environment variable defaults
- Consider peak/off-peak scheduling

### Task 4: Adding Data Export/Analysis Features

**Recommendations**:
1. Create new Python script (e.g., `data-export.py`)
2. Reuse database connection pattern from `MaintenanceLogger`
3. Use TimescaleDB time-bucket functions for aggregation
4. Export to CSV, JSON, or generate reports

**Example Query Pattern**:
```python
# Daily consumption summary
cursor.execute("""
    SELECT
        time_bucket('1 day', time) AS day,
        meter_id,
        MAX(total_liter_m3) - MIN(total_liter_m3) AS daily_consumption
    FROM water_readings
    WHERE meter_id = %s
    GROUP BY day, meter_id
    ORDER BY day DESC
""", (meter_id,))
```

### Task 5: Implementing Alerts/Notifications

**Recommendations**:
1. Add alert threshold checking in `_store_reading()`
2. Implement notification service (email, webhook, etc.)
3. Add new table `alerts` to track notification history
4. Consider using TimescaleDB continuous aggregates for threshold detection

**Example**:
```python
# In _store_reading():
if reading_data["active_liter_lpm"] > threshold:
    logger.warning(f"High flow rate detected: {reading_data['active_liter_lpm']} L/min")
    self._send_alert("high_flow", reading_data)
```

## Testing Considerations

### Manual Testing

**Test Database Connection**:
```python
python3 -c "
import psycopg2
conn = psycopg2.connect(host='localhost', database='watermeter', user='postgres', password='pwd')
print('Connected successfully')
"
```

**Test Meter API**:
```bash
curl http://watermeter.thuisnet.com/api/v1/data
```

**Test Container Health**:
```bash
podman healthcheck run water-python-api
```

### Areas to Test When Making Changes

1. **Database Operations**:
   - Table creation on first run
   - Data insertion with various field combinations
   - Query performance with large datasets
   - Hypertable creation

2. **API Polling**:
   - Successful reads
   - Timeout handling
   - Invalid JSON responses
   - Network failures

3. **Daemon Lifecycle**:
   - Startup and initialization
   - Graceful shutdown (SIGTERM, SIGINT)
   - Recovery from database disconnections
   - Consecutive failure handling

4. **Maintenance Logging**:
   - All command variations
   - Missing optional fields
   - Date calculations (days_ago)
   - List filtering

## Troubleshooting Guide

### Common Issues

**Issue**: "DB_USER and DB_PASSWORD environment variables are required"
- **Solution**: Set both environment variables before running

**Issue**: Database connection fails
- **Solution**: Check PostgreSQL is running, credentials are correct, and host is reachable

**Issue**: "TimescaleDB extension not found"
- **Solution**: Install TimescaleDB extension: `CREATE EXTENSION timescaledb;`

**Issue**: Meter API timeout
- **Solution**: Check `METER_API_URL` is correct, network connectivity, and increase `METER_API_TIMEOUT`

**Issue**: "Too many consecutive failures, exiting"
- **Solution**: Check logs for underlying issue (database, API, network). Fix root cause and restart daemon.

**Issue**: Container health check failing
- **Solution**: Verify `METER_API_URL` environment variable is set correctly in container

## Dependencies

### Runtime Dependencies

**Python Version**: Python 3.x (compatible with Red Hat UBI 10)

**Python Packages**:
- `psycopg2`: PostgreSQL database adapter (with RealDictCursor support)
- `requests`: HTTP library for API calls

**System Dependencies**:
- PostgreSQL 12+ with TimescaleDB extension
- Network access to water meter API

### Development Dependencies

**Tools**:
- Podman (container runtime)
- Git (version control)
- Text editor with Python support

**Optional**:
- pgAdmin or psql for database management
- curl for API testing

## Project Metadata

**Version**: 1.0 (from Containerfile:6)
**Container Registry**: quay.thuisnet.com/apps/water-python-api
**Maintainer**: Update in Containerfile:8
**License**: Not specified (consider adding LICENSE file)

## Future Enhancements (Ideas for AI Assistants)

1. **Data Visualization**: Add Grafana dashboard integration
2. **Predictive Analytics**: ML models for leak detection or consumption forecasting
3. **Multi-Meter Support**: Handle multiple meters in single deployment
4. **REST API**: Add Flask/FastAPI server for data queries
5. **Backup/Export**: Automated data backup and archival
6. **Web UI**: Simple web interface for viewing data and maintenance logs
7. **Alerts**: Email/SMS notifications for anomalies
8. **Configuration File**: Support YAML/JSON config files in addition to env vars
9. **Unit Tests**: Add pytest test suite
10. **Documentation**: Auto-generate API docs from code

## Related Documentation

**TimescaleDB Docs**: https://docs.timescale.com/
**psycopg2 Docs**: https://www.psycopg.org/docs/
**Red Hat UBI**: https://developers.redhat.com/products/rhel/ubi

---

**Last Updated**: 2025-11-15
**Document Version**: 1.0
**Repository**: /home/user/water-python-api
