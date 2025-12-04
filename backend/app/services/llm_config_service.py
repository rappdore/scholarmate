"""
LLM Configuration Service Module

This module provides a service for managing multiple LLM endpoint configurations.
Supports CRUD operations and ensures only one configuration is active at a time.
"""

import logging
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

# Configure logger for this module
logger = logging.getLogger(__name__)


class LLMConfigService:
    """
    Service class for managing LLM configurations in the database.

    This service handles:
    - Creating, reading, updating, and deleting LLM configurations
    - Activating/deactivating configurations (only one can be active)
    - Retrieving the active configuration
    - Masking API keys for safe display
    """

    def __init__(self, db_path: str = "data/reading_progress.db"):
        """
        Initialize the LLM configuration service.

        Args:
            db_path (str): Path to the SQLite database file
        """
        self.db_path = db_path

    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections.
        Ensures proper connection handling and cleanup.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
        finally:
            conn.close()

    def mask_api_key(self, api_key: str) -> str:
        """
        Mask API key for safe display.
        Shows first 8 and last 4 characters.

        Args:
            api_key (str): Full API key

        Returns:
            str: Masked API key (e.g., "sk-or-v1-***74af")
        """
        if not api_key or len(api_key) <= 12:
            return "***"
        return f"{api_key[:8]}***{api_key[-4:]}"

    def _row_to_dict(self, row: sqlite3.Row, mask_key: bool = True) -> Dict[str, Any]:
        """
        Convert a database row to a dictionary.

        Args:
            row: SQLite row object
            mask_key: Whether to mask the API key

        Returns:
            Dict with configuration data
        """
        config = dict(row)
        if mask_key and "api_key" in config:
            config["api_key_preview"] = self.mask_api_key(config["api_key"])
            del config["api_key"]  # Remove full key from response
        return config

    def get_all_configurations(self) -> List[Dict[str, Any]]:
        """
        Retrieve all LLM configurations with masked API keys.

        Returns:
            List of configuration dictionaries
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT id, name, description, base_url, api_key, model_name,
                           is_active, created_at, updated_at
                    FROM llm_configurations
                    ORDER BY is_active DESC, name ASC
                """)
                rows = cursor.fetchall()
                return [self._row_to_dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error fetching all configurations: {e}")
            raise

    def get_active_configuration(self) -> Optional[Dict[str, Any]]:
        """
        Get the currently active LLM configuration with full API key.

        Returns:
            Configuration dictionary with full API key, or None if no active config
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT id, name, description, base_url, api_key, model_name,
                           is_active, created_at, updated_at
                    FROM llm_configurations
                    WHERE is_active = 1
                    LIMIT 1
                """)
                row = cursor.fetchone()
                if row:
                    return self._row_to_dict(row, mask_key=False)
                return None
        except Exception as e:
            logger.error(f"Error fetching active configuration: {e}")
            raise

    def get_configuration_by_id(self, config_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a specific configuration by ID with masked API key.

        Args:
            config_id: Configuration ID

        Returns:
            Configuration dictionary or None if not found
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT id, name, description, base_url, api_key, model_name,
                           is_active, created_at, updated_at
                    FROM llm_configurations
                    WHERE id = ?
                """,
                    (config_id,),
                )
                row = cursor.fetchone()
                if row:
                    return self._row_to_dict(row)
                return None
        except Exception as e:
            logger.error(f"Error fetching configuration {config_id}: {e}")
            raise

    def create_configuration(
        self,
        name: str,
        base_url: str,
        api_key: str,
        model_name: str,
        description: str = None,
        is_active: bool = False,
    ) -> Dict[str, Any]:
        """
        Create a new LLM configuration.

        Args:
            name: User-friendly name for the configuration
            base_url: API endpoint URL
            api_key: Authentication key
            model_name: Model identifier
            description: Optional description
            is_active: Whether to set as active (deactivates others)

        Returns:
            Created configuration dictionary

        Raises:
            ValueError: If name already exists
        """
        try:
            with self.get_connection() as conn:
                # Check if name already exists
                cursor = conn.execute(
                    "SELECT COUNT(*) as count FROM llm_configurations WHERE name = ?",
                    (name,),
                )
                if cursor.fetchone()["count"] > 0:
                    raise ValueError(f"Configuration with name '{name}' already exists")

                # If setting as active, deactivate all others first
                if is_active:
                    conn.execute("UPDATE llm_configurations SET is_active = 0")

                # Insert new configuration
                cursor = conn.execute(
                    """
                    INSERT INTO llm_configurations
                    (name, description, base_url, api_key, model_name, is_active)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (name, description, base_url, api_key, model_name, is_active),
                )

                config_id = cursor.lastrowid
                conn.commit()

                logger.info(f"Created LLM configuration: {name} (ID: {config_id})")

                # Return the created configuration
                return self.get_configuration_by_id(config_id)
        except Exception as e:
            logger.error(f"Error creating configuration: {e}")
            raise

    def update_configuration(
        self,
        config_id: int,
        name: str = None,
        description: str = None,
        base_url: str = None,
        api_key: str = None,
        model_name: str = None,
    ) -> Dict[str, Any]:
        """
        Update an existing LLM configuration.
        Cannot update is_active flag (use activate_configuration instead).

        Args:
            config_id: Configuration ID to update
            name: New name (optional)
            description: New description (optional)
            base_url: New base URL (optional)
            api_key: New API key (optional)
            model_name: New model name (optional)

        Returns:
            Updated configuration dictionary

        Raises:
            ValueError: If configuration not found or validation fails
        """
        try:
            with self.get_connection() as conn:
                # Check if configuration exists
                cursor = conn.execute(
                    "SELECT COUNT(*) as count FROM llm_configurations WHERE id = ?",
                    (config_id,),
                )
                if cursor.fetchone()["count"] == 0:
                    raise ValueError(f"Configuration with ID {config_id} not found")

                # Build dynamic UPDATE query for provided fields
                updates = []
                params = []

                if name is not None:
                    # Check if new name conflicts with existing
                    cursor = conn.execute(
                        "SELECT COUNT(*) as count FROM llm_configurations WHERE name = ? AND id != ?",
                        (name, config_id),
                    )
                    if cursor.fetchone()["count"] > 0:
                        raise ValueError(
                            f"Configuration with name '{name}' already exists"
                        )
                    updates.append("name = ?")
                    params.append(name)

                if description is not None:
                    updates.append("description = ?")
                    params.append(description)

                if base_url is not None:
                    updates.append("base_url = ?")
                    params.append(base_url)

                if api_key is not None:
                    updates.append("api_key = ?")
                    params.append(api_key)

                if model_name is not None:
                    updates.append("model_name = ?")
                    params.append(model_name)

                if not updates:
                    # No updates provided, just return current config
                    return self.get_configuration_by_id(config_id)

                # Add updated_at timestamp
                updates.append("updated_at = CURRENT_TIMESTAMP")
                params.append(config_id)

                # Execute update
                query = (
                    f"UPDATE llm_configurations SET {', '.join(updates)} WHERE id = ?"
                )
                conn.execute(query, params)
                conn.commit()

                logger.info(f"Updated LLM configuration ID: {config_id}")

                return self.get_configuration_by_id(config_id)
        except Exception as e:
            logger.error(f"Error updating configuration {config_id}: {e}")
            raise

    def activate_configuration(self, config_id: int) -> Dict[str, Any]:
        """
        Set a configuration as active (deactivates all others).

        Args:
            config_id: Configuration ID to activate

        Returns:
            Dictionary with activation result and configuration details

        Raises:
            ValueError: If configuration not found
        """
        try:
            with self.get_connection() as conn:
                # Check if configuration exists
                cursor = conn.execute(
                    "SELECT id, is_active FROM llm_configurations WHERE id = ?",
                    (config_id,),
                )
                row = cursor.fetchone()
                if not row:
                    raise ValueError(f"Configuration with ID {config_id} not found")

                if row["is_active"]:
                    # Already active, return success
                    return {
                        "message": "Configuration already active",
                        "configuration": self.get_configuration_by_id(config_id),
                    }

                # Get previous active configuration ID
                cursor = conn.execute(
                    "SELECT id FROM llm_configurations WHERE is_active = 1"
                )
                prev_row = cursor.fetchone()
                previous_active_id = prev_row["id"] if prev_row else None

                # Activate the configuration (trigger will deactivate others)
                conn.execute(
                    "UPDATE llm_configurations SET is_active = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (config_id,),
                )
                conn.commit()

                logger.info(f"Activated LLM configuration ID: {config_id}")

                return {
                    "message": "Configuration activated successfully",
                    "previous_active_id": previous_active_id,
                    "new_active_id": config_id,
                    "configuration": self.get_configuration_by_id(config_id),
                }
        except Exception as e:
            logger.error(f"Error activating configuration {config_id}: {e}")
            raise

    def delete_configuration(self, config_id: int) -> bool:
        """
        Delete a configuration.
        Cannot delete the active configuration.

        Args:
            config_id: Configuration ID to delete

        Returns:
            True if deleted successfully

        Raises:
            ValueError: If configuration not found or is active
        """
        try:
            with self.get_connection() as conn:
                # Check if configuration exists and is not active
                cursor = conn.execute(
                    "SELECT is_active FROM llm_configurations WHERE id = ?",
                    (config_id,),
                )
                row = cursor.fetchone()
                if not row:
                    raise ValueError(f"Configuration with ID {config_id} not found")

                if row["is_active"]:
                    raise ValueError(
                        "Cannot delete the active configuration. Please activate another configuration first."
                    )

                # Delete the configuration
                conn.execute(
                    "DELETE FROM llm_configurations WHERE id = ?", (config_id,)
                )
                conn.commit()

                logger.info(f"Deleted LLM configuration ID: {config_id}")
                return True
        except Exception as e:
            logger.error(f"Error deleting configuration {config_id}: {e}")
            raise

    def get_configuration_count(self) -> int:
        """
        Get the total number of configurations.

        Returns:
            Count of configurations
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT COUNT(*) as count FROM llm_configurations"
                )
                return cursor.fetchone()["count"]
        except Exception as e:
            logger.error(f"Error counting configurations: {e}")
            raise
