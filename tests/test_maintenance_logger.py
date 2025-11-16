"""
Unit tests for maintenance-logger.py (MaintenanceLogger)
Uses mocking to avoid dependencies on actual database
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
import psycopg2
import sys
import os
import importlib.util

# Import maintenance-logger.py module despite the hyphenated name
module_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "maintenance-logger.py")
spec = importlib.util.spec_from_file_location("maintenance_logger", module_path)
maintenance_logger = importlib.util.module_from_spec(spec)
sys.modules['maintenance_logger'] = maintenance_logger

# Set minimal environment variables to allow module loading
os.environ.setdefault("DB_USER", "test_user")
os.environ.setdefault("DB_PASSWORD", "test_password")

# Load the module initially
spec.loader.exec_module(maintenance_logger)


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    """Set up environment variables for all tests"""
    monkeypatch.setenv("DB_USER", "test_user")
    monkeypatch.setenv("DB_PASSWORD", "test_password")
    monkeypatch.setenv("DB_HOST", "test_host")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "test_db")
    monkeypatch.setenv("METER_ID", "test_meter")


@pytest.fixture
def logger():
    """Create a MaintenanceLogger instance"""
    return maintenance_logger.MaintenanceLogger()


@pytest.mark.unit
class TestMaintenanceLoggerInit:
    """Test logger initialization"""

    def test_init_with_env_vars(self, logger):
        """Test initialization with environment variables"""
        assert logger.db_user == "test_user"
        assert logger.db_password == "test_password"
        assert logger.db_host == "test_host"
        assert logger.db_port == 5432
        assert logger.db_name == "test_db"
        assert logger.meter_id == "test_meter"

    def test_init_defaults(self, monkeypatch):
        """Test initialization with default values"""
        monkeypatch.setenv("DB_USER", "user")
        monkeypatch.setenv("DB_PASSWORD", "pass")
        monkeypatch.delenv("DB_HOST", raising=False)
        monkeypatch.delenv("METER_ID", raising=False)

        spec.loader.exec_module(maintenance_logger)
        logger = maintenance_logger.MaintenanceLogger()

        assert logger.db_host == "localhost"
        assert logger.meter_id == "default_meter"

    def test_init_without_credentials_exits(self, monkeypatch):
        """Test that initialization fails without credentials"""
        monkeypatch.delenv("DB_USER", raising=False)
        monkeypatch.delenv("DB_PASSWORD", raising=False)

        spec.loader.exec_module(maintenance_logger)
        with pytest.raises(SystemExit):
            maintenance_logger.MaintenanceLogger()


@pytest.mark.unit
class TestDatabaseConnection:
    """Test database connection"""

    @patch('psycopg2.connect')
    def test_connect_database_success(self, mock_connect, logger):
        """Test successful database connection"""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        result = logger.connect_database()

        assert result is True
        assert logger.db_conn == mock_conn
        assert mock_conn.autocommit is True
        mock_connect.assert_called_once_with(
            host=logger.db_host,
            port=logger.db_port,
            database=logger.db_name,
            user=logger.db_user,
            password=logger.db_password,
            cursor_factory=psycopg2.extras.RealDictCursor
        )

    @patch('psycopg2.connect')
    def test_connect_database_failure(self, mock_connect, logger):
        """Test database connection failure"""
        mock_connect.side_effect = psycopg2.Error("Connection failed")

        result = logger.connect_database()

        assert result is False


@pytest.mark.unit
class TestLogMaintenance:
    """Test logging maintenance activities"""

    def test_log_maintenance_success(self, logger):
        """Test successful maintenance logging"""
        mock_cursor = MagicMock()
        logger.db_conn = MagicMock()
        logger.db_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Mock the fetchone return value
        mock_cursor.fetchone.return_value = {
            'id': 1,
            'time': datetime(2025, 11, 15, 12, 0, 0, tzinfo=timezone.utc)
        }

        result = logger.log_maintenance(
            maintenance_type='salt_replacement',
            description='Test salt replacement',
            quantity=25.0,
            unit='kg',
            cost=15.99,
            notes='Test notes'
        )

        assert result is True
        mock_cursor.execute.assert_called_once()

    def test_log_maintenance_minimal_fields(self, logger):
        """Test logging with only required fields"""
        mock_cursor = MagicMock()
        logger.db_conn = MagicMock()
        logger.db_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_cursor.fetchone.return_value = {
            'id': 2,
            'time': datetime(2025, 11, 15, 12, 0, 0, tzinfo=timezone.utc)
        }

        result = logger.log_maintenance(
            maintenance_type='inspection'
        )

        assert result is True

    def test_log_maintenance_database_error(self, logger):
        """Test logging failure due to database error"""
        logger.db_conn = MagicMock()
        logger.db_conn.cursor.return_value.__enter__.return_value.execute.side_effect = \
            psycopg2.Error("Insert failed")

        result = logger.log_maintenance(
            maintenance_type='filter_change'
        )

        assert result is False


@pytest.mark.unit
class TestListRecentMaintenance:
    """Test listing recent maintenance"""

    def test_list_recent_maintenance_with_results(self, logger):
        """Test listing maintenance when results exist"""
        mock_cursor = MagicMock()
        logger.db_conn = MagicMock()
        logger.db_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Mock maintenance entries
        mock_cursor.fetchall.return_value = [
            {
                'time': datetime(2025, 11, 15, 12, 0, 0, tzinfo=timezone.utc),
                'maintenance_type': 'salt_replacement',
                'description': 'Salt block replacement',
                'quantity': 25.0,
                'unit': 'kg',
                'cost': 15.99,
                'notes': 'Test notes',
                'created_by': 'manual'
            },
            {
                'time': datetime(2025, 11, 10, 10, 0, 0, tzinfo=timezone.utc),
                'maintenance_type': 'filter_change',
                'description': 'Main filter',
                'quantity': None,
                'unit': None,
                'cost': 45.00,
                'notes': None,
                'created_by': 'manual'
            }
        ]

        logger.list_recent_maintenance(days=30)

        mock_cursor.execute.assert_called_once()
        # Verify the SQL uses parameterized query
        call_args = mock_cursor.execute.call_args
        assert 'INTERVAL' in call_args[0][0]
        assert call_args[0][1] == (logger.meter_id, 30)

    def test_list_recent_maintenance_no_results(self, logger):
        """Test listing when no maintenance found"""
        mock_cursor = MagicMock()
        logger.db_conn = MagicMock()
        logger.db_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_cursor.fetchall.return_value = []

        logger.list_recent_maintenance(days=7)

        mock_cursor.execute.assert_called_once()

    def test_list_recent_maintenance_database_error(self, logger):
        """Test listing with database error"""
        logger.db_conn = MagicMock()
        logger.db_conn.cursor.return_value.__enter__.return_value.execute.side_effect = \
            psycopg2.Error("Query failed")

        # Should not raise exception, just log error
        logger.list_recent_maintenance(days=30)


@pytest.mark.unit
class TestGetLastSaltReplacement:
    """Test getting last salt replacement"""

    def test_get_last_salt_replacement_exists(self, logger):
        """Test when salt replacement exists"""
        mock_cursor = MagicMock()
        logger.db_conn = MagicMock()
        logger.db_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Mock salt replacement 15 days ago
        past_time = datetime(2025, 10, 31, 9, 50, 0, tzinfo=timezone.utc)
        mock_cursor.fetchone.return_value = {
            'time': past_time,
            'description': 'Salt block replacement',
            'quantity': 25.0,
            'unit': 'kg',
            'notes': 'Test notes'
        }

        logger.get_last_salt_replacement()

        mock_cursor.execute.assert_called_once()
        # Verify query filters by salt_replacement
        call_args = mock_cursor.execute.call_args
        assert 'salt_replacement' in call_args[0][0]

    def test_get_last_salt_replacement_not_found(self, logger):
        """Test when no salt replacement found"""
        mock_cursor = MagicMock()
        logger.db_conn = MagicMock()
        logger.db_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_cursor.fetchone.return_value = None

        logger.get_last_salt_replacement()

        mock_cursor.execute.assert_called_once()

    def test_get_last_salt_replacement_database_error(self, logger):
        """Test with database error"""
        logger.db_conn = MagicMock()
        logger.db_conn.cursor.return_value.__enter__.return_value.execute.side_effect = \
            psycopg2.Error("Query failed")

        # Should not raise exception
        logger.get_last_salt_replacement()


@pytest.mark.unit
class TestGetLastChange:
    """Test getting last maintenance change of any type"""

    def test_get_last_change_exists(self, logger):
        """Test when maintenance exists"""
        mock_cursor = MagicMock()
        logger.db_conn = MagicMock()
        logger.db_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Mock recent maintenance
        recent_time = datetime(2025, 11, 15, 16, 31, 0, tzinfo=timezone.utc)
        mock_cursor.fetchone.return_value = {
            'time': recent_time,
            'maintenance_type': 'inspection',
            'description': 'Test CLI enhancements',
            'quantity': None,
            'unit': None,
            'cost': None,
            'notes': 'Verifying logging module integration'
        }

        logger.get_last_change()

        mock_cursor.execute.assert_called_once()
        # Verify query doesn't filter by type
        call_args = mock_cursor.execute.call_args
        assert 'ORDER BY time DESC' in call_args[0][0]
        assert 'LIMIT 1' in call_args[0][0]

    def test_get_last_change_not_found(self, logger):
        """Test when no maintenance found"""
        mock_cursor = MagicMock()
        logger.db_conn = MagicMock()
        logger.db_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_cursor.fetchone.return_value = None

        logger.get_last_change()

        mock_cursor.execute.assert_called_once()

    def test_get_last_change_with_all_fields(self, logger):
        """Test with maintenance containing all optional fields"""
        mock_cursor = MagicMock()
        logger.db_conn = MagicMock()
        logger.db_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_cursor.fetchone.return_value = {
            'time': datetime(2025, 11, 15, 12, 0, 0, tzinfo=timezone.utc),
            'maintenance_type': 'filter_change',
            'description': 'Main filter replacement',
            'quantity': 1.0,
            'unit': 'piece',
            'cost': 45.00,
            'notes': 'Complete replacement'
        }

        logger.get_last_change()

        mock_cursor.execute.assert_called_once()

    def test_get_last_change_database_error(self, logger):
        """Test with database error"""
        logger.db_conn = MagicMock()
        logger.db_conn.cursor.return_value.__enter__.return_value.execute.side_effect = \
            psycopg2.Error("Query failed")

        # Should not raise exception
        logger.get_last_change()


@pytest.mark.unit
class TestMainFunction:
    """Test main function and CLI argument parsing"""

    @patch('sys.argv', ['maintenance-logger.py', '--help'])
    def test_main_help(self):
        """Test help argument"""
        with pytest.raises(SystemExit) as exc_info:
            maintenance_logger.main()
        # Help should exit with code 0
        assert exc_info.value.code == 0

    @patch('sys.argv', ['maintenance-logger.py'])
    def test_main_no_command(self):
        """Test running without command"""
        # Should print help and return without error
        maintenance_logger.main()

    @patch('sys.argv', ['maintenance-logger.py', 'salt', '--quantity', '25', '--cost', '15.99'])
    @patch('psycopg2.connect')
    def test_main_salt_command(self, mock_connect):
        """Test salt command execution"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {'id': 1, 'time': datetime(2025, 11, 15, 12, 0, 0, tzinfo=timezone.utc)}

        maintenance_logger.main()

        # Verify database operations occurred
        assert mock_connect.called

    @patch('sys.argv', ['maintenance-logger.py', 'log', 'inspection', '--description', 'Test'])
    @patch('psycopg2.connect')
    def test_main_log_command(self, mock_connect):
        """Test log command execution"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {'id': 1, 'time': datetime(2025, 11, 15, 12, 0, 0, tzinfo=timezone.utc)}

        maintenance_logger.main()

        assert mock_connect.called

    @patch('sys.argv', ['maintenance-logger.py', 'list', '--days', '60'])
    @patch('psycopg2.connect')
    def test_main_list_command(self, mock_connect):
        """Test list command execution"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        maintenance_logger.main()

        assert mock_connect.called

    @patch('sys.argv', ['maintenance-logger.py', 'last-salt'])
    @patch('psycopg2.connect')
    def test_main_last_salt_command(self, mock_connect):
        """Test last-salt command execution"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        maintenance_logger.main()

        assert mock_connect.called

    @patch('sys.argv', ['maintenance-logger.py', 'last-change'])
    @patch('psycopg2.connect')
    def test_main_last_change_command(self, mock_connect):
        """Test last-change command execution"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        maintenance_logger.main()

        assert mock_connect.called

    @patch('sys.argv', ['maintenance-logger.py', 'list'])
    @patch('psycopg2.connect')
    def test_main_connection_failure_exits(self, mock_connect):
        """Test that connection failure causes exit"""
        mock_connect.side_effect = psycopg2.Error("Connection failed")

        with pytest.raises(SystemExit) as exc_info:
            maintenance_logger.main()

        assert exc_info.value.code == 1

    @patch('sys.argv', ['maintenance-logger.py', 'list'])
    @patch('psycopg2.connect')
    def test_main_closes_connection_in_finally(self, mock_connect):
        """Test that database connection is closed in finally block"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        maintenance_logger.main()

        # Verify connection was closed
        assert mock_conn.close.called
