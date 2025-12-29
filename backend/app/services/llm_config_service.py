"""
LLM Configuration Service Module

This module provides a service for managing multiple LLM endpoint configurations.
Supports CRUD operations and ensures only one configuration is active at a time.
"""

import logging
import sqlite3
from contextlib import contextmanager
from typing import Any

from app.models.llm_types import (
    LLMConfiguration,
    LLMConfigurationMasked,
)

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

    def _row_to_dict_full(self, row: sqlite3.Row) -> LLMConfiguration:
        """
        Convert a database row to a typed configuration dict with full API key.

        Args:
            row: SQLite row object

        Returns:
            LLMConfiguration with full API key
        """
        return LLMConfiguration(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            base_url=row["base_url"],
            api_key=row["api_key"],
            model_name=row["model_name"],
            is_active=bool(row["is_active"]),
            always_starts_with_thinking=bool(row["always_starts_with_thinking"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_dict_masked(self, row: sqlite3.Row) -> LLMConfigurationMasked:
        """
        Convert a database row to a typed configuration dict with masked API key.

        Args:
            row: SQLite row object

        Returns:
            LLMConfigurationMasked with masked API key preview
        """
        return LLMConfigurationMasked(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            base_url=row["base_url"],
            api_key_preview=self.mask_api_key(row["api_key"]),
            model_name=row["model_name"],
            is_active=bool(row["is_active"]),
            always_starts_with_thinking=bool(row["always_starts_with_thinking"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def get_all_configurations(self) -> list[LLMConfigurationMasked]:
        """
        Retrieve all LLM configurations with masked API keys.

        Returns:
            list of LLMConfigurationMasked dictionaries
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT id, name, description, base_url, api_key, model_name,
                           is_active, always_starts_with_thinking, created_at, updated_at
                    FROM llm_configurations
                    ORDER BY is_active DESC, name ASC
                """)
                rows = cursor.fetchall()
                return [self._row_to_dict_masked(row) for row in rows]
        except Exception as e:
            logger.error(f"Error fetching all configurations: {e}")
            raise

    def get_active_configuration(self) -> LLMConfiguration | None:
        """
        Get the currently active LLM configuration with full API key.

        Returns:
            LLMConfiguration with full API key, or None if no active config
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT id, name, description, base_url, api_key, model_name,
                           is_active, always_starts_with_thinking, created_at, updated_at
                    FROM llm_configurations
                    WHERE is_active = 1
                    LIMIT 1
                """)
                row = cursor.fetchone()
                if row:
                    return self._row_to_dict_full(row)
                return None
        except Exception as e:
            logger.error(f"Error fetching active configuration: {e}")
            raise

    def get_configuration_by_id(self, config_id: int) -> LLMConfigurationMasked | None:
        """
        Get a specific configuration by ID with masked API key.

        Args:
            config_id: Configuration ID

        Returns:
            LLMConfigurationMasked or None if not found
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT id, name, description, base_url, api_key, model_name,
                           is_active, always_starts_with_thinking, created_at, updated_at
                    FROM llm_configurations
                    WHERE id = ?
                """,
                    (config_id,),
                )
                row = cursor.fetchone()
                if row:
                    return self._row_to_dict_masked(row)
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
        description: str | None = None,
        is_active: bool = False,
        always_starts_with_thinking: bool = False,
    ) -> LLMConfigurationMasked:
        """
        Create a new LLM configuration.

        Args:
            name: User-friendly name for the configuration
            base_url: API endpoint URL
            api_key: Authentication key
            model_name: Model identifier
            description: Optional description
            is_active: Whether to set as active (deactivates others)
            always_starts_with_thinking: Whether model always starts with thinking block

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
                    (name, description, base_url, api_key, model_name, is_active, always_starts_with_thinking)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        name,
                        description,
                        base_url,
                        api_key,
                        model_name,
                        is_active,
                        always_starts_with_thinking,
                    ),
                )

                config_id = cursor.lastrowid
                conn.commit()

                logger.info(f"Created LLM configuration: {name} (ID: {config_id})")

                # Return the created configuration
                created_config = self.get_configuration_by_id(config_id)
                if not created_config:
                    raise ValueError(
                        f"Failed to retrieve created configuration {config_id}"
                    )
                return created_config
        except Exception as e:
            logger.error(f"Error creating configuration: {e}")
            raise

    def update_configuration(
        self,
        config_id: int,
        name: str | None = None,
        description: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        model_name: str | None = None,
        always_starts_with_thinking: bool | None = None,
    ) -> LLMConfigurationMasked:
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
            always_starts_with_thinking: Whether model always starts with thinking block (optional)

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
                updates: list[str] = []
                params: list[Any] = []

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

                if always_starts_with_thinking is not None:
                    updates.append("always_starts_with_thinking = ?")
                    params.append(always_starts_with_thinking)

                if not updates:
                    # No updates provided, just return current config
                    current_config = self.get_configuration_by_id(config_id)
                    if not current_config:
                        raise ValueError(f"Configuration with ID {config_id} not found")
                    return current_config

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

                updated_config = self.get_configuration_by_id(config_id)
                if not updated_config:
                    raise ValueError(
                        f"Failed to retrieve updated configuration {config_id}"
                    )
                return updated_config
        except Exception as e:
            logger.error(f"Error updating configuration {config_id}: {e}")
            raise

    def activate_configuration(self, config_id: int) -> dict[str, Any]:
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
