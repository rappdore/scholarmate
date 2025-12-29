"""
Database Migration Service

This module provides functionality to safely apply database schema changes
through migration files. It tracks which migrations have been applied and
ensures they are only run once.
"""

import logging
import sqlite3
from pathlib import Path

# Configure logger for this module
logger = logging.getLogger(__name__)


class MigrationService:
    """
    Service for managing database migrations.

    This service handles applying SQL migration files in order and tracks
    which migrations have been applied to prevent duplicate execution.
    """

    def __init__(self, db_path: str = "data/reading_progress.db"):
        """
        Initialize the migration service.

        Args:
            db_path (str): Path to the SQLite database file
        """
        self.db_path = db_path
        self.migrations_dir = Path(__file__).parent.parent.parent / "migrations"
        self._ensure_migrations_table()

    def _ensure_migrations_table(self):
        """
        Ensure the migrations tracking table exists.

        Creates a table to track which migrations have been applied.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    migration_name TEXT UNIQUE NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def _get_applied_migrations(self) -> set[str]:
        """
        Get the set of migrations that have already been applied.

        Returns:
            set[str]: Set of migration names that have been applied
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT migration_name FROM schema_migrations")
            return {row[0] for row in cursor.fetchall()}

    def _mark_migration_applied(self, migration_name: str):
        """
        Mark a migration as applied in the database.

        Args:
            migration_name (str): Name of the migration to mark as applied
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO schema_migrations (migration_name) VALUES (?)",
                (migration_name,),
            )
            conn.commit()

    def _get_pending_migrations(self) -> list[str]:
        """
        Get list of migration files that haven't been applied yet.

        Returns:
            list[str]: Sorted list of pending migration file names
        """
        if not self.migrations_dir.exists():
            logger.warning(f"Migrations directory not found: {self.migrations_dir}")
            return []

        # Get all .sql files in migrations directory
        migration_files = [
            f.name for f in self.migrations_dir.glob("*.sql") if f.is_file()
        ]

        # Sort migrations by name (assuming naming convention like 001_name.sql)
        migration_files.sort()

        # Filter out already applied migrations
        applied_migrations = self._get_applied_migrations()
        pending_migrations = [
            migration
            for migration in migration_files
            if migration not in applied_migrations
        ]

        return pending_migrations

    def _execute_migration(self, migration_file: str) -> bool:
        """
        Execute a single migration file.

        Args:
            migration_file (str): Name of the migration file to execute

        Returns:
            bool: True if migration was successful, False otherwise
        """
        migration_path = self.migrations_dir / migration_file

        try:
            with open(migration_path, "r") as f:
                migration_sql = f.read()

            # Split on semicolons and execute each statement
            raw_statements = [
                stmt.strip() for stmt in migration_sql.split(";") if stmt.strip()
            ]

            with sqlite3.connect(self.db_path) as conn:
                for raw_statement in raw_statements:
                    # Remove comment lines from the statement
                    statement_lines = []
                    for line in raw_statement.split("\n"):
                        line = line.strip()
                        # Skip comment lines and empty lines
                        if not line or line.startswith("--"):
                            continue
                        statement_lines.append(line)

                    # Join the non-comment lines back together
                    clean_statement = " ".join(statement_lines).strip()

                    # Skip if there's no actual SQL content after removing comments
                    if not clean_statement:
                        continue

                    logger.info(f"Executing: {clean_statement[:100]}...")
                    conn.execute(clean_statement)

                conn.commit()

            logger.info(f"Successfully applied migration: {migration_file}")
            return True

        except Exception as e:
            logger.error(f"Error applying migration {migration_file}: {e}")
            return False

    def apply_migrations(self) -> bool:
        """
        Apply all pending migrations in order.

        Returns:
            bool: True if all migrations were applied successfully, False otherwise
        """
        pending_migrations = self._get_pending_migrations()

        if not pending_migrations:
            logger.info("No pending migrations to apply")
            return True

        logger.info(f"Found {len(pending_migrations)} pending migrations to apply")

        for migration_file in pending_migrations:
            logger.info(f"Applying migration: {migration_file}")

            if self._execute_migration(migration_file):
                self._mark_migration_applied(migration_file)
                logger.info(f"Migration {migration_file} applied successfully")
            else:
                logger.error(f"Failed to apply migration: {migration_file}")
                return False

        logger.info("All migrations applied successfully")
        return True

    def get_migration_status(self) -> dict:
        """
        Get the current migration status.

        Returns:
            dict: Dictionary containing migration status information
        """
        applied_migrations = self._get_applied_migrations()
        pending_migrations = self._get_pending_migrations()

        return {
            "applied_count": len(applied_migrations),
            "pending_count": len(pending_migrations),
            "applied_migrations": sorted(list(applied_migrations)),
            "pending_migrations": pending_migrations,
        }
