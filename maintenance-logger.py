#!/usr/bin/env python3
"""
Water System Maintenance Logger
Log maintenance activities like salt block replacement, filter changes, etc.
"""

import os
import sys
import argparse
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

class MaintenanceLogger:
    def __init__(self):
        # Database configuration from environment variables
        self.db_host = os.getenv('DB_HOST', 'localhost')
        self.db_port = int(os.getenv('DB_PORT', '5432'))
        self.db_name = os.getenv('DB_NAME', 'watermeter')
        self.db_user = os.getenv('DB_USER')
        self.db_password = os.getenv('DB_PASSWORD')
        self.meter_id = os.getenv('METER_ID', 'default_meter')

        if not self.db_user or not self.db_password:
            logger.error("DB_USER and DB_PASSWORD environment variables are required")
            sys.exit(1)

    def connect_database(self):
        """Connect to the database"""
        try:
            self.db_conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user,
                password=self.db_password,
                cursor_factory=RealDictCursor
            )
            self.db_conn.autocommit = True
            logger.info(f"Connected to database {self.db_name} on {self.db_host}")
            return True
        except psycopg2.Error as e:
            logger.error(f"Database connection failed: {e}")
            return False

    def log_maintenance(self, maintenance_type: str, description: str = None,
                       quantity: float = None, unit: str = None,
                       cost: float = None, notes: str = None,
                       created_by: str = 'manual'):
        """Log a maintenance activity"""
        try:
            with self.db_conn.cursor() as cursor:
                insert_sql = """
                INSERT INTO maintenance_log (
                    time, meter_id, maintenance_type, description,
                    quantity, unit, cost, notes, created_by
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) RETURNING id, time
                """

                cursor.execute(insert_sql, (
                    datetime.now(timezone.utc),
                    self.meter_id,
                    maintenance_type,
                    description,
                    quantity,
                    unit,
                    cost,
                    notes,
                    created_by
                ))

                result = cursor.fetchone()
                logger.info("✅ Maintenance logged successfully!")
                logger.info(f"   ID: {result['id']}")
                logger.info(f"   Time: {result['time']}")
                logger.info(f"   Type: {maintenance_type}")
                if description:
                    logger.info(f"   Description: {description}")

                return True

        except psycopg2.Error as e:
            logger.error(f"Failed to log maintenance: {e}")
            return False

    def list_recent_maintenance(self, days: int = 30):
        """List recent maintenance activities"""
        try:
            with self.db_conn.cursor() as cursor:
                cursor.execute("""
                    SELECT time, maintenance_type, description, quantity, unit,
                           cost, notes, created_by
                    FROM maintenance_log
                    WHERE meter_id = %s
                      AND time >= NOW() - INTERVAL '1 day' * %s
                    ORDER BY time DESC
                """, (self.meter_id, days))

                results = cursor.fetchall()

                if not results:
                    logger.info(f"No maintenance activities found in the last {days} days.")
                    return

                logger.info(f"\n📋 Recent maintenance activities (last {days} days):")
                logger.info("-" * 80)

                for row in results:
                    logger.info(f"🔧 {row['time'].strftime('%Y-%m-%d %H:%M')} - {row['maintenance_type']}")
                    if row['description']:
                        logger.info(f"   Description: {row['description']}")
                    if row['quantity'] and row['unit']:
                        logger.info(f"   Quantity: {row['quantity']} {row['unit']}")
                    if row['cost']:
                        logger.info(f"   Cost: €{row['cost']:.2f}")
                    if row['notes']:
                        logger.info(f"   Notes: {row['notes']}")
                    logger.info(f"   Logged by: {row['created_by']}")
                    logger.info("")

        except psycopg2.Error as e:
            logger.error(f"Failed to retrieve maintenance log: {e}")

    def get_last_salt_replacement(self):
        """Get the date of the last salt block replacement"""
        try:
            with self.db_conn.cursor() as cursor:
                cursor.execute("""
                    SELECT time, description, quantity, unit, notes
                    FROM maintenance_log
                    WHERE meter_id = %s
                      AND maintenance_type = 'salt_replacement'
                    ORDER BY time DESC
                    LIMIT 1
                """, (self.meter_id,))

                result = cursor.fetchone()

                if result:
                    days_ago = (datetime.now(timezone.utc) - result['time']).days
                    logger.info(f"🧂 Last salt replacement: {result['time'].strftime('%Y-%m-%d %H:%M')} ({days_ago} days ago)")
                    if result['description']:
                        logger.info(f"   Description: {result['description']}")
                    if result['quantity'] and result['unit']:
                        logger.info(f"   Quantity: {result['quantity']} {result['unit']}")
                    if result['notes']:
                        logger.info(f"   Notes: {result['notes']}")
                else:
                    logger.info("🧂 No salt replacements recorded yet.")

        except psycopg2.Error as e:
            logger.error(f"Failed to retrieve last salt replacement: {e}")

    def get_last_change(self):
        """Get the most recent maintenance activity of any type"""
        try:
            with self.db_conn.cursor() as cursor:
                cursor.execute("""
                    SELECT time, maintenance_type, description, quantity, unit, cost, notes
                    FROM maintenance_log
                    WHERE meter_id = %s
                    ORDER BY time DESC
                    LIMIT 1
                """, (self.meter_id,))

                result = cursor.fetchone()

                if result:
                    days_ago = (datetime.now(timezone.utc) - result['time']).days
                    logger.info(f"🔧 Last maintenance: {result['maintenance_type']} on {result['time'].strftime('%Y-%m-%d %H:%M')} ({days_ago} days ago)")
                    if result['description']:
                        logger.info(f"   Description: {result['description']}")
                    if result['quantity'] and result['unit']:
                        logger.info(f"   Quantity: {result['quantity']} {result['unit']}")
                    if result['cost']:
                        logger.info(f"   Cost: €{result['cost']:.2f}")
                    if result['notes']:
                        logger.info(f"   Notes: {result['notes']}")
                else:
                    logger.info("🔧 No maintenance activities recorded yet.")

        except psycopg2.Error as e:
            logger.error(f"Failed to retrieve last maintenance activity: {e}")

def main():
    parser = argparse.ArgumentParser(description='Log water system maintenance activities')

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Salt replacement command
    salt_parser = subparsers.add_parser('salt', help='Log salt block replacement')
    salt_parser.add_argument('--quantity', type=float, help='Quantity of salt (kg)')
    salt_parser.add_argument('--cost', type=float, help='Cost of salt blocks (€)')
    salt_parser.add_argument('--notes', help='Additional notes')
    salt_parser.add_argument('--brand', help='Brand of salt blocks')

    # Generic maintenance command
    maint_parser = subparsers.add_parser('log', help='Log general maintenance')
    maint_parser.add_argument('type', help='Maintenance type (e.g., filter_change, inspection, repair)')
    maint_parser.add_argument('--description', help='Description of maintenance')
    maint_parser.add_argument('--quantity', type=float, help='Quantity')
    maint_parser.add_argument('--unit', help='Unit of quantity')
    maint_parser.add_argument('--cost', type=float, help='Cost (€)')
    maint_parser.add_argument('--notes', help='Additional notes')

    # List maintenance command
    list_parser = subparsers.add_parser('list', help='List recent maintenance')
    list_parser.add_argument('--days', type=int, default=30, help='Number of days to look back (default: 30)')

    # Last salt command
    subparsers.add_parser('last-salt', help='Show last salt replacement')

    # Last change command
    subparsers.add_parser('last-change', help='Show most recent maintenance activity of any type')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    logger = MaintenanceLogger()
    if not logger.connect_database():
        sys.exit(1)

    try:
        if args.command == 'salt':
            description = "Salt block replacement"
            if args.brand:
                description += f" ({args.brand})"

            logger.log_maintenance(
                maintenance_type='salt_replacement',
                description=description,
                quantity=args.quantity,
                unit='kg' if args.quantity else None,
                cost=args.cost,
                notes=args.notes
            )

        elif args.command == 'log':
            logger.log_maintenance(
                maintenance_type=args.type,
                description=args.description,
                quantity=args.quantity,
                unit=args.unit,
                cost=args.cost,
                notes=args.notes
            )

        elif args.command == 'list':
            logger.list_recent_maintenance(args.days)

        elif args.command == 'last-salt':
            logger.get_last_salt_replacement()

        elif args.command == 'last-change':
            logger.get_last_change()

    finally:
        # Ensure database connection is properly closed
        if hasattr(logger, 'db_conn') and logger.db_conn:
            logger.db_conn.close()

if __name__ == "__main__":
    main()
