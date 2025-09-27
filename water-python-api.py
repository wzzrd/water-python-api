#!/usr/bin/env python3
"""
Water Meter Data Collection Daemon for TimescaleDB
Collects water meter readings and stores them in TimescaleDB
"""

import os
import sys
import time
import json
import signal
import logging
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from typing import Dict, Optional
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class WaterMeterDaemon:
    def __init__(self):
        self.running = False
        self.db_conn = None

        # Configuration from environment variables
        self.meter_api_url = os.getenv("METER_API_URL", "http://192.168.1.100/api/data")
        self.meter_api_timeout = int(os.getenv("METER_API_TIMEOUT", "10"))
        self.collection_interval = int(
            os.getenv("COLLECTION_INTERVAL", "300")
        )  # 5 minutes default
        self.meter_id = os.getenv("METER_ID", "default_meter")

        # Database configuration
        self.db_host = os.getenv("DB_HOST", "localhost")
        self.db_port = int(os.getenv("DB_PORT", "5432"))
        self.db_name = os.getenv("DB_NAME", "watermeter")
        self.db_user = os.getenv("DB_USER")
        self.db_password = os.getenv("DB_PASSWORD")

        if not self.db_user or not self.db_password:
            logger.error("DB_USER and DB_PASSWORD environment variables are required")
            sys.exit(1)

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info(f"Water Meter Daemon initialized")
        logger.info(f"Collection interval: {self.collection_interval} seconds")
        logger.info(f"Meter API URL: {self.meter_api_url}")
        logger.info(f"Database: {self.db_host}:{self.db_port}/{self.db_name}")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    def _connect_database(self) -> bool:
        """Establish database connection, creating database if it doesn't exist"""
        try:
            # First try to connect to the target database
            try:
                self.db_conn = psycopg2.connect(
                    host=self.db_host,
                    port=self.db_port,
                    database=self.db_name,
                    user=self.db_user,
                    password=self.db_password,
                    cursor_factory=RealDictCursor,
                )
                self.db_conn.autocommit = True
                logger.info(f"Connected to existing database: {self.db_name}")
                return True

            except psycopg2.OperationalError as e:
                if "database" in str(e) and "does not exist" in str(e):
                    logger.info(f"Database {self.db_name} does not exist, creating...")

                    # Connect to postgres database to create our target database
                    admin_conn = psycopg2.connect(
                        host=self.db_host,
                        port=self.db_port,
                        database="postgres",  # Connect to default postgres db
                        user=self.db_user,
                        password=self.db_password,
                    )
                    admin_conn.autocommit = True

                    with admin_conn.cursor() as cursor:
                        # Create the database
                        cursor.execute(f'CREATE DATABASE "{self.db_name}"')
                        logger.info(f"Database {self.db_name} created successfully")

                    admin_conn.close()

                    # Now connect to our newly created database
                    self.db_conn = psycopg2.connect(
                        host=self.db_host,
                        port=self.db_port,
                        database=self.db_name,
                        user=self.db_user,
                        password=self.db_password,
                        cursor_factory=RealDictCursor,
                    )
                    self.db_conn.autocommit = True
                    logger.info(f"Connected to newly created database: {self.db_name}")
                    return True
                else:
                    # Re-raise if it's a different error
                    raise e

        except psycopg2.Error as e:
            logger.error(f"Database connection failed: {e}")
            return False

    def _setup_schema(self) -> bool:
        """Create the water_readings and maintenance_log tables and hypertables if they don't exist"""
        try:
            with self.db_conn.cursor() as cursor:
                # Check if TimescaleDB extension exists
                cursor.execute(
                    "SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'"
                )
                if not cursor.fetchone():
                    logger.info("Creating TimescaleDB extension...")
                    cursor.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")

                # Create water_readings table if it doesn't exist
                create_readings_table_sql = """
                CREATE TABLE IF NOT EXISTS water_readings (
                    time TIMESTAMPTZ NOT NULL,
                    meter_id TEXT NOT NULL,
                    total_liter_m3 NUMERIC(12,3) NOT NULL,
                    active_liter_lpm NUMERIC(8,3) NOT NULL,
                    wifi_strength INTEGER NOT NULL,
                    wifi_ssid TEXT,
                    total_liter_offset_m3 NUMERIC(12,3),
                    PRIMARY KEY (time, meter_id)
                );
                """
                cursor.execute(create_readings_table_sql)

                # Create maintenance_log table if it doesn't exist
                create_maintenance_table_sql = """
                CREATE TABLE IF NOT EXISTS maintenance_log (
                    id SERIAL,
                    time TIMESTAMPTZ NOT NULL,
                    meter_id TEXT NOT NULL,
                    maintenance_type TEXT NOT NULL,
                    description TEXT,
                    quantity NUMERIC(10,3),
                    unit TEXT,
                    cost NUMERIC(10,2),
                    notes TEXT,
                    created_by TEXT DEFAULT 'system',
                    PRIMARY KEY (time, id)
                );
                """
                cursor.execute(create_maintenance_table_sql)

                # Check if water_readings hypertable already exists
                cursor.execute(
                    """
                    SELECT 1 FROM _timescaledb_catalog.hypertable
                    WHERE table_name = 'water_readings'
                """
                )

                if not cursor.fetchone():
                    logger.info("Creating water_readings hypertable...")
                    cursor.execute("SELECT create_hypertable('water_readings', 'time')")

                # Check if maintenance_log hypertable already exists
                cursor.execute(
                    """
                    SELECT 1 FROM _timescaledb_catalog.hypertable
                    WHERE table_name = 'maintenance_log'
                """
                )

                if not cursor.fetchone():
                    logger.info("Creating maintenance_log hypertable...")
                    cursor.execute("SELECT create_hypertable('maintenance_log', 'time')")

                # Create indexes for efficient queries
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_water_readings_meter_time
                    ON water_readings (meter_id, time DESC)
                """
                )

                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_maintenance_log_meter_time
                    ON maintenance_log (meter_id, time DESC)
                """
                )

                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_maintenance_log_type
                    ON maintenance_log (meter_id, maintenance_type, time DESC)
                """
                )

                logger.info("Database schema setup completed (water_readings and maintenance_log tables)")
                return True

        except psycopg2.Error as e:
            logger.error(f"Schema setup failed: {e}")
            return False

    def _read_meter(self) -> Optional[Dict]:
        """Read data from the water meter API"""
        try:
            response = requests.get(self.meter_api_url, timeout=self.meter_api_timeout)
            response.raise_for_status()

            data = response.json()
            logger.debug(f"Meter reading: {data}")

            # Validate required fields
            required_fields = ["total_liter_m3", "active_liter_lpm", "wifi_strength"]
            for field in required_fields:
                if field not in data:
                    logger.error(f"Missing required field: {field}")
                    return None

            return data

        except requests.RequestException as e:
            logger.error(f"Failed to read meter: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from meter: {e}")
            return None

    def _store_reading(self, reading_data: Dict) -> bool:
        """Store a reading in the database"""
        try:
            with self.db_conn.cursor() as cursor:
                insert_sql = """
                INSERT INTO water_readings (
                    time, meter_id, total_liter_m3, active_liter_lpm,
                    wifi_strength, wifi_ssid, total_liter_offset_m3
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s
                )
                """

                cursor.execute(
                    insert_sql,
                    (
                        datetime.now(),
                        self.meter_id,
                        float(reading_data["total_liter_m3"]),
                        float(reading_data["active_liter_lpm"]),
                        int(reading_data["wifi_strength"]),
                        reading_data.get("wifi_ssid"),
                        float(reading_data.get("total_liter_offset_m3", 0)),
                    ),
                )

                logger.info(f"Stored reading: {reading_data['total_liter_m3']} m³")
                return True

        except psycopg2.Error as e:
            logger.error(f"Failed to store reading: {e}")
            return False

    def _health_check(self) -> bool:
        """Perform basic health checks"""
        try:
            # Check database connection
            with self.db_conn.cursor() as cursor:
                cursor.execute("SELECT 1")
            return True
        except psycopg2.Error:
            logger.warning("Database health check failed, attempting reconnection...")
            return self._connect_database()

    def run(self):
        """Main daemon loop"""
        logger.info("Starting Water Meter Daemon...")

        # Initial database setup
        if not self._connect_database():
            logger.error("Initial database connection failed")
            sys.exit(1)

        if not self._setup_schema():
            logger.error("Schema setup failed")
            sys.exit(1)

        self.running = True
        consecutive_failures = 0
        max_consecutive_failures = 5

        while self.running:
            try:
                # Health check every few iterations
                if not self._health_check():
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        logger.error("Too many consecutive failures, exiting")
                        break
                    time.sleep(30)  # Wait before retry
                    continue

                # Read meter data
                reading_data = self._read_meter()
                if reading_data:
                    if self._store_reading(reading_data):
                        consecutive_failures = 0
                    else:
                        consecutive_failures += 1
                else:
                    consecutive_failures += 1

                if consecutive_failures >= max_consecutive_failures:
                    logger.error("Too many consecutive failures, exiting")
                    break

                # Wait for next collection cycle
                if self.running:
                    time.sleep(self.collection_interval)

            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}")
                consecutive_failures += 1
                time.sleep(30)

        # Cleanup
        if self.db_conn:
            self.db_conn.close()
        logger.info("Water Meter Daemon stopped")


def main():
    daemon = WaterMeterDaemon()
    daemon.run()


if __name__ == "__main__":
    main()
