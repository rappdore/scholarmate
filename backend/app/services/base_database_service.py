"""
Base Database Service Module

This module provides shared database utilities and connection management
for all specialized database services in the application.
"""

import logging
import os
import sqlite3
from datetime import datetime
from typing import Any, Optional

# Configure logger for this module
logger = logging.getLogger(__name__)


class BaseDatabaseService:
    """
    Base class providing shared database utilities and connection management.

    This class handles common database operations like connection management,
    directory creation, and provides utility methods that can be used by
    specialized service classes.
    """

    def __init__(self, db_path: str = "data/reading_progress.db"):
        """
        Initialize the base database service.

        Args:
            db_path (str): Path to the SQLite database file. Defaults to "data/reading_progress.db"
                          The directory will be created if it doesn't exist.
        """
        self.db_path = db_path
        self._ensure_data_dir()

    def _ensure_data_dir(self):
        """
        Ensure the data directory exists for the database file.

        Creates the directory structure if it doesn't exist. This prevents
        database connection errors when the data directory is missing.
        """
        data_dir = os.path.dirname(self.db_path)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir)

    def get_connection(self) -> sqlite3.Connection:
        """
        Get a database connection.

        Returns:
            sqlite3.Connection: Database connection object
        """
        return sqlite3.connect(self.db_path)

    def execute_query(
        self,
        query: str,
        params: tuple = (),
        fetch_one: bool = False,
        fetch_all: bool = False,
    ) -> Any:
        """
        Execute a database query with error handling.

        Args:
            query (str): SQL query to execute
            params (tuple): Query parameters
            fetch_one (bool): Whether to fetch one result
            fetch_all (bool): Whether to fetch all results

        Returns:
            Any: Query result or None if error occurred
        """
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(query, params)

                if fetch_one:
                    return cursor.fetchone()
                elif fetch_all:
                    return cursor.fetchall()
                else:
                    conn.commit()
                    return cursor.lastrowid
        except Exception as e:
            logger.error(f"Database query error: {e}")
            return None

    def execute_insert(self, query: str, params: tuple) -> Optional[int]:
        """
        Execute an INSERT query and return the last row ID.

        Args:
            query (str): INSERT SQL query
            params (tuple): Query parameters

        Returns:
            Optional[int]: Last row ID or None if failed
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(query, params)
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Database insert error: {e}")
            return None

    def execute_update_delete(self, query: str, params: tuple) -> bool:
        """
        Execute an UPDATE or DELETE query.

        Args:
            query (str): UPDATE or DELETE SQL query
            params (tuple): Query parameters

        Returns:
            bool: True if rows were affected, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(query, params)
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Database update/delete error: {e}")
            return False

    def get_current_timestamp(self) -> str:
        """
        Get current timestamp for database operations.

        Returns:
            str: Current timestamp in SQLite format
        """
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def format_timestamp_iso(self, timestamp_str: str) -> str:
        """
        Convert SQLite timestamp string to ISO 8601 format with UTC indicator.

        SQLite stores timestamps as local time strings (YYYY-MM-DD HH:MM:SS).
        This method converts them to ISO 8601 format with 'Z' suffix to indicate UTC.

        Args:
            timestamp_str (str): SQLite timestamp string (e.g., "2025-12-11 11:08:40")

        Returns:
            str: ISO 8601 timestamp with UTC indicator (e.g., "2025-12-11T11:08:40Z")
        """
        if not timestamp_str:
            return timestamp_str

        # Replace space with 'T' and append 'Z' for UTC
        # "2025-12-11 11:08:40" -> "2025-12-11T11:08:40Z"
        return timestamp_str.replace(" ", "T") + "Z"
