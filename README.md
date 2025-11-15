# Water Python API

A containerized water meter monitoring system that continuously collects water consumption data via API polling and stores it in TimescaleDB for time-series analysis.

## Overview

This system provides:

- **Continuous monitoring**: Daemon polls your water meter API at configurable intervals
- **Time-series storage**: Efficient data storage using PostgreSQL with TimescaleDB extension
- **Maintenance tracking**: CLI tool for logging salt replacements, filter changes, and other maintenance activities
- **Containerized deployment**: Built on Red Hat Universal Base Image (UBI) 10 for reliable, production-ready deployment

## Prerequisites

- **Podman** (or Docker) for container builds and deployment
- **PostgreSQL 12+** with **TimescaleDB extension** installed
- **Water meter** with accessible HTTP API endpoint

## Quick Start

### 1. Build the Container

The container build is tested against **UBI 10**. Currently, you need to build the image yourself (no pre-built images are available).

```bash
# Build using the included script
./buildrun.sh

# Or build manually with Podman
podman build -f Containerfile -t water-python-api:latest .
```

### 2. Configure Environment Variables

The following environment variables are **required**:

| Variable | Description | Example |
|----------|-------------|---------|
| `DB_USER` | PostgreSQL username | `postgres` |
| `DB_PASSWORD` | PostgreSQL password | `your_secure_password` |
| `DB_HOST` | PostgreSQL server hostname/IP | `192.168.1.10` or `db.example.com` |
| `DB_PORT` | PostgreSQL port | `5432` |
| `METER_API_URL` | Full URL to your water meter API endpoint | `http://192.168.1.100/api/v1/data` |

**Important**: The `METER_API_URL` must include:
- Protocol (`http://` or `https://`)
- IP address or hostname of your water meter
- Full path ending in `/api/v1/data`

### 3. Run the Container

```bash
podman run -d \
    --name water-python-api \
    --restart unless-stopped \
    -e DB_HOST="192.168.1.10" \
    -e DB_PORT="5432" \
    -e DB_USER="postgres" \
    -e DB_PASSWORD="your_password" \
    -e METER_API_URL="http://192.168.1.100/api/v1/data" \
    water-python-api:latest
```

## Configuration

### Required Environment Variables

```bash
export DB_USER="postgres"
export DB_PASSWORD="your_secure_password"
export DB_HOST="192.168.1.10"
export DB_PORT="5432"
export METER_API_URL="http://192.168.1.100/api/v1/data"
```

### Optional Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `METER_API_TIMEOUT` | `10` | API request timeout in seconds |
| `COLLECTION_INTERVAL` | `300` | Polling interval in seconds (default: 5 minutes) |
| `METER_ID` | `default_meter` | Identifier for this specific meter |
| `DB_NAME` | `watermeter` | PostgreSQL database name |

### Example: Custom Configuration

```bash
podman run -d \
    --name water-python-api \
    --restart unless-stopped \
    -e DB_HOST="db.mynetwork.local" \
    -e DB_PORT="5432" \
    -e DB_NAME="water" \
    -e DB_USER="wateruser" \
    -e DB_PASSWORD="secure_pass_123" \
    -e METER_API_URL="http://watermeter.mynetwork.local/api/v1/data" \
    -e METER_ID="basement_meter" \
    -e COLLECTION_INTERVAL="60" \
    -e METER_API_TIMEOUT="15" \
    water-python-api:latest
```

## Database Setup

### Install TimescaleDB Extension

Before running the container, ensure TimescaleDB is installed on your PostgreSQL server:

```sql
-- Connect to your database
psql -U postgres -d watermeter

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;
```

### Automatic Schema Creation

The daemon automatically creates the required tables and hypertables on first run:

- `water_readings`: Time-series water consumption data
- `maintenance_log`: Maintenance activity tracking

No manual schema setup is required.

## Maintenance Logger

The `maintenance-logger.py` tool allows you to track maintenance activities.

### Log Salt Replacement

```bash
./maintenance-logger.py salt --quantity 25 --cost 15.99 --brand "AquaPure"
```

### Log General Maintenance

```bash
# Filter change
./maintenance-logger.py log filter_change --description "Main sediment filter" --cost 45.00

# System repair
./maintenance-logger.py log repair --description "Fixed leak in main valve" --cost 120.50

# Inspection
./maintenance-logger.py log inspection --description "Annual system check"
```

### View Maintenance History

```bash
# Last 30 days (default)
./maintenance-logger.py list

# Last 90 days
./maintenance-logger.py list --days 90

# Check last salt replacement
./maintenance-logger.py last-salt
```

**Note**: The maintenance logger requires the same database environment variables as the main daemon.

## Monitoring

### View Container Logs

```bash
# Follow logs in real-time
podman logs -f water-python-api

# View last 100 lines
podman logs --tail 100 water-python-api
```

### Check Container Health

```bash
podman healthcheck run water-python-api
```

The health check verifies connectivity to the water meter API.

### Check Container Status

```bash
podman ps -a | grep water-python-api
```

## Data Storage

### Database Tables

**water_readings** - Time-series water consumption:
- `time`: Timestamp of reading
- `meter_id`: Meter identifier
- `total_liter_m3`: Total consumption in cubic meters
- `active_liter_lpm`: Current flow rate in liters per minute
- `wifi_strength`: WiFi signal strength
- `wifi_ssid`: WiFi network name
- `total_liter_offset_m3`: Calibration offset

**maintenance_log** - Maintenance activities:
- `time`: Timestamp of maintenance
- `meter_id`: Meter identifier
- `maintenance_type`: Type of maintenance (salt_replacement, filter_change, etc.)
- `description`: Detailed description
- `quantity`: Amount (e.g., kg of salt)
- `unit`: Unit of measurement
- `cost`: Cost in currency
- `notes`: Additional notes

### Query Examples

```sql
-- Daily water consumption
SELECT
    time_bucket('1 day', time) AS day,
    MAX(total_liter_m3) - MIN(total_liter_m3) AS consumption_m3
FROM water_readings
WHERE meter_id = 'default_meter'
GROUP BY day
ORDER BY day DESC
LIMIT 30;

-- Recent maintenance activities
SELECT * FROM maintenance_log
ORDER BY time DESC
LIMIT 10;
```

## Troubleshooting

### Container Won't Start

**Check environment variables**:
```bash
podman inspect water-python-api | grep -A 20 Env
```

**Verify database connectivity**:
```bash
# From the container
podman exec -it water-python-api python3 -c "
import psycopg2
conn = psycopg2.connect(
    host='$DB_HOST',
    port='$DB_PORT',
    database='watermeter',
    user='$DB_USER',
    password='$DB_PASSWORD'
)
print('Database connection successful')
"
```

### No Data Being Collected

1. **Check meter API is accessible**:
   ```bash
   curl http://192.168.1.100/api/v1/data
   ```

2. **Verify METER_API_URL format**:
   - Must include protocol (`http://` or `https://`)
   - Must end with `/api/v1/data`
   - Example: `http://192.168.1.100/api/v1/data`

3. **Check container logs for errors**:
   ```bash
   podman logs water-python-api | grep ERROR
   ```

### Health Check Failing

The health check tests connectivity to the water meter API. If failing:

1. Verify `METER_API_URL` environment variable is set correctly
2. Check network connectivity from container to meter
3. Ensure meter is powered on and responding

### Database Connection Issues

- Verify PostgreSQL is running and accessible from the container
- Check credentials (`DB_USER`, `DB_PASSWORD`)
- Ensure `DB_HOST` and `DB_PORT` are correct
- Verify TimescaleDB extension is installed

## Development

### Local Development (Without Container)

**Install dependencies** (Red Hat/Fedora):
```bash
sudo dnf install python3-psycopg2 python3-requests
```

**Run daemon locally**:
```bash
export DB_USER="postgres"
export DB_PASSWORD="your_password"
export DB_HOST="localhost"
export METER_API_URL="http://192.168.1.100/api/v1/data"

./water-python-api.py
```

### Container Registry

If you wish to push to your own container registry:

```bash
# Tag the image
podman tag water-python-api:latest your-registry.com/apps/water-python-api:latest

# Push to registry
podman push your-registry.com/apps/water-python-api:latest
```

## Security Considerations

- Never commit `.env` files or hardcode credentials
- Use strong passwords for `DB_PASSWORD`
- Container runs as non-root user (UID 1001)
- All database queries use parameterized statements to prevent SQL injection
- Consider using secrets management for production deployments

## Support

For issues or questions:
1. Check the logs: `podman logs water-python-api`
2. Verify environment variables are set correctly
3. Test database and API connectivity manually
4. Review the `CLAUDE.md` file for detailed technical documentation

## License

[Add your license here]

## Changelog

### Version 1.0
- Initial release
- Water meter API polling and storage
- TimescaleDB integration
- Maintenance logging CLI
- Red Hat UBI 10 containerization
