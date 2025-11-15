"""
Unit tests for water-python-api.py (WaterMeterDaemon)
Uses mocking to avoid dependencies on actual database and meter API
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timezone
import psycopg2
import sys
import os
import importlib.util

# Import water-python-api.py module despite the hyphenated name
module_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "water-python-api.py")
spec = importlib.util.spec_from_file_location("water_python_api", module_path)
water_python_api = importlib.util.module_from_spec(spec)
sys.modules['water_python_api'] = water_python_api

# Set minimal environment variables to allow module loading
os.environ.setdefault("DB_USER", "test_user")
os.environ.setdefault("DB_PASSWORD", "test_password")

# Load the module initially
with patch('signal.signal'):
    spec.loader.exec_module(water_python_api)


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    """Set up environment variables for all tests"""
    monkeypatch.setenv("DB_USER", "test_user")
    monkeypatch.setenv("DB_PASSWORD", "test_password")
    monkeypatch.setenv("DB_HOST", "test_host")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "test_db")
    monkeypatch.setenv("METER_API_URL", "http://test-meter/api/data")
    monkeypatch.setenv("METER_API_TIMEOUT", "10")
    monkeypatch.setenv("COLLECTION_INTERVAL", "60")
    monkeypatch.setenv("METER_ID", "test_meter")


@pytest.fixture
def daemon():
    """Create a WaterMeterDaemon instance"""
    with patch('signal.signal'):
        return water_python_api.WaterMeterDaemon()


@pytest.mark.unit
class TestWaterMeterDaemonInit:
    """Test daemon initialization"""

    def test_init_with_env_vars(self, daemon):
        """Test initialization with environment variables"""
        assert daemon.db_user == "test_user"
        assert daemon.db_password == "test_password"
        assert daemon.db_host == "test_host"
        assert daemon.db_port == 5432
        assert daemon.db_name == "test_db"
        assert daemon.meter_api_url == "http://test-meter/api/data"
        assert daemon.meter_api_timeout == 10
        assert daemon.collection_interval == 60
        assert daemon.meter_id == "test_meter"
        assert daemon.running is False
        assert daemon.db_conn is None

    def test_init_defaults(self, monkeypatch):
        """Test initialization with default values"""
        monkeypatch.setenv("DB_USER", "user")
        monkeypatch.setenv("DB_PASSWORD", "pass")
        # Don't set optional env vars
        monkeypatch.delenv("METER_API_URL", raising=False)
        monkeypatch.delenv("COLLECTION_INTERVAL", raising=False)

        with patch('signal.signal'):
            spec.loader.exec_module(water_python_api)
            daemon = water_python_api.WaterMeterDaemon()

            assert daemon.meter_api_url == "http://192.168.1.100/api/data"
            assert daemon.collection_interval == 300


@pytest.mark.unit
class TestSignalHandler:
    """Test signal handling"""

    def test_signal_handler_stops_daemon(self, daemon):
        """Test that signal handler sets running to False"""
        daemon.running = True
        daemon._signal_handler(15, None)
        assert daemon.running is False


@pytest.mark.unit
class TestDatabaseConnection:
    """Test database connection methods"""

    @patch('psycopg2.connect')
    def test_connect_database_success(self, mock_connect, daemon):
        """Test successful database connection"""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        result = daemon._connect_database()

        assert result is True
        assert daemon.db_conn == mock_conn
        assert mock_conn.autocommit is True

    @patch('psycopg2.connect')
    def test_connect_database_creates_db_if_not_exists(self, mock_connect, daemon):
        """Test database creation when it doesn't exist"""
        mock_admin_conn = MagicMock()
        mock_target_conn = MagicMock()

        call_count = [0]

        def connect_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise psycopg2.OperationalError('database "test_db" does not exist')
            elif kwargs.get('database') == 'postgres':
                return mock_admin_conn
            else:
                return mock_target_conn

        mock_connect.side_effect = connect_side_effect

        result = daemon._connect_database()

        assert result is True
        assert daemon.db_conn == mock_target_conn
        assert mock_admin_conn.close.called

    @patch('psycopg2.connect')
    def test_connect_database_failure(self, mock_connect, daemon):
        """Test database connection failure"""
        mock_connect.side_effect = psycopg2.Error("Connection failed")

        result = daemon._connect_database()

        assert result is False


@pytest.mark.unit
class TestSchemaSetup:
    """Test database schema setup"""

    def test_setup_schema_success(self, daemon):
        """Test successful schema setup"""
        mock_cursor = MagicMock()
        daemon.db_conn = MagicMock()
        daemon.db_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Mock checks for extension and hypertables
        mock_cursor.fetchone.side_effect = [
            {'extname': 'timescaledb'},  # Extension exists
            None,  # water_readings hypertable doesn't exist
            None,  # maintenance_log hypertable doesn't exist
        ]

        result = daemon._setup_schema()

        assert result is True
        assert mock_cursor.execute.call_count >= 7

    def test_setup_schema_failure(self, daemon):
        """Test schema setup failure"""
        daemon.db_conn = MagicMock()
        daemon.db_conn.cursor.return_value.__enter__.return_value.execute.side_effect = \
            psycopg2.Error("Schema creation failed")

        result = daemon._setup_schema()

        assert result is False


@pytest.mark.unit
class TestMeterReading:
    """Test meter reading from API"""

    @patch('requests.get')
    def test_read_meter_success(self, mock_get, daemon):
        """Test successful meter reading"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "total_liter_m3": 123.456,
            "active_liter_lpm": 2.5,
            "wifi_strength": -45,
            "wifi_ssid": "TestNetwork"
        }
        mock_get.return_value = mock_response

        result = daemon._read_meter()

        assert result is not None
        assert result["total_liter_m3"] == 123.456
        assert result["active_liter_lpm"] == 2.5
        assert result["wifi_strength"] == -45

    @patch('requests.get')
    def test_read_meter_missing_required_field(self, mock_get, daemon):
        """Test meter reading with missing required field"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "total_liter_m3": 123.456
            # Missing required fields
        }
        mock_get.return_value = mock_response

        result = daemon._read_meter()

        assert result is None

    @patch('requests.get')
    def test_read_meter_network_error(self, mock_get, daemon):
        """Test meter reading with network error"""
        import requests
        mock_get.side_effect = requests.RequestException("Network error")

        result = daemon._read_meter()

        assert result is None

    @patch('requests.get')
    def test_read_meter_invalid_json(self, mock_get, daemon):
        """Test meter reading with invalid JSON"""
        import json
        mock_response = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)
        mock_get.return_value = mock_response

        result = daemon._read_meter()

        assert result is None


@pytest.mark.unit
class TestSafeFloat:
    """Test safe float conversion"""

    def test_safe_float_valid_number(self, daemon):
        """Test conversion of valid number"""
        assert daemon._safe_float(123.456) == 123.456
        assert daemon._safe_float("123.456") == 123.456

    def test_safe_float_none(self, daemon):
        """Test conversion of None"""
        assert daemon._safe_float(None) == 0.0
        assert daemon._safe_float(None, default=5.0) == 5.0

    def test_safe_float_empty_string(self, daemon):
        """Test conversion of empty string"""
        assert daemon._safe_float("") == 0.0

    def test_safe_float_invalid_value(self, daemon):
        """Test conversion of invalid value"""
        assert daemon._safe_float("invalid") == 0.0


@pytest.mark.unit
class TestStoreReading:
    """Test storing readings in database"""

    def test_store_reading_success(self, daemon):
        """Test successful reading storage"""
        mock_cursor = MagicMock()
        daemon.db_conn = MagicMock()
        daemon.db_conn.cursor.return_value.__enter__.return_value = mock_cursor

        reading_data = {
            "total_liter_m3": 123.456,
            "active_liter_lpm": 2.5,
            "wifi_strength": -45,
            "wifi_ssid": "TestNetwork",
            "total_liter_offset_m3": 1.0
        }

        result = daemon._store_reading(reading_data)

        assert result is True
        mock_cursor.execute.assert_called_once()

    def test_store_reading_minimal_fields(self, daemon):
        """Test storing reading with only required fields"""
        mock_cursor = MagicMock()
        daemon.db_conn = MagicMock()
        daemon.db_conn.cursor.return_value.__enter__.return_value = mock_cursor

        reading_data = {
            "total_liter_m3": 123.456,
            "active_liter_lpm": 2.5,
            "wifi_strength": -45
        }

        result = daemon._store_reading(reading_data)

        assert result is True

    def test_store_reading_database_error(self, daemon):
        """Test storage failure"""
        daemon.db_conn = MagicMock()
        daemon.db_conn.cursor.return_value.__enter__.return_value.execute.side_effect = \
            psycopg2.Error("Insert failed")

        reading_data = {
            "total_liter_m3": 123.456,
            "active_liter_lpm": 2.5,
            "wifi_strength": -45
        }

        result = daemon._store_reading(reading_data)

        assert result is False


@pytest.mark.unit
class TestHealthCheck:
    """Test health check functionality"""

    def test_health_check_success(self, daemon):
        """Test successful health check"""
        mock_cursor = MagicMock()
        daemon.db_conn = MagicMock()
        daemon.db_conn.cursor.return_value.__enter__.return_value = mock_cursor

        result = daemon._health_check()

        assert result is True
        mock_cursor.execute.assert_called_once_with("SELECT 1")

    def test_health_check_reconnects_on_failure(self, daemon):
        """Test that health check attempts reconnection on failure"""
        daemon.db_conn = MagicMock()
        daemon.db_conn.cursor.return_value.__enter__.return_value.execute.side_effect = \
            psycopg2.Error("Connection lost")

        with patch.object(daemon, '_connect_database', return_value=True) as mock_connect:
            result = daemon._health_check()
            mock_connect.assert_called_once()


@pytest.mark.unit
class TestMainLoop:
    """Test main daemon loop"""

    @patch('time.sleep')
    def test_run_exits_on_connection_failure(self, mock_sleep, daemon):
        """Test that run exits when initial connection fails"""
        with patch.object(daemon, '_connect_database', return_value=False):
            with pytest.raises(SystemExit):
                daemon.run()

    @patch('time.sleep')
    def test_run_exits_on_schema_failure(self, mock_sleep, daemon):
        """Test that run exits when schema setup fails"""
        with patch.object(daemon, '_connect_database', return_value=True), \
             patch.object(daemon, '_setup_schema', return_value=False):
            with pytest.raises(SystemExit):
                daemon.run()

    @patch('time.sleep')
    def test_run_single_iteration(self, mock_sleep, daemon):
        """Test single iteration of the main loop"""

        def stop_after_one(*args):
            daemon.running = False

        mock_sleep.side_effect = stop_after_one

        reading_data = {
            "total_liter_m3": 123.456,
            "active_liter_lpm": 2.5,
            "wifi_strength": -45
        }

        with patch.object(daemon, '_connect_database', return_value=True), \
             patch.object(daemon, '_setup_schema', return_value=True), \
             patch.object(daemon, '_health_check', return_value=True), \
             patch.object(daemon, '_read_meter', return_value=reading_data), \
             patch.object(daemon, '_store_reading', return_value=True):

            daemon.run()

            # Verify cleanup
            assert daemon.db_conn is None or not daemon.running

    @patch('time.sleep')
    def test_run_handles_consecutive_failures(self, mock_sleep, daemon):
        """Test that daemon exits after too many consecutive failures"""

        with patch.object(daemon, '_connect_database', return_value=True), \
             patch.object(daemon, '_setup_schema', return_value=True), \
             patch.object(daemon, '_health_check', return_value=True), \
             patch.object(daemon, '_read_meter', return_value=None):

            daemon.run()

            # Daemon should have exited the loop (db_conn is closed)
            # The running flag may still be True but loop has exited
            assert daemon.db_conn is None
