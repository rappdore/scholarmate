"""
LLM Configuration Router

Provides API endpoints for managing LLM configurations:
- List all configurations
- Get active configuration
- Create new configuration
- Update existing configuration
- Activate configuration
- Delete configuration
- Test connection
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.models.llm_types import LLMConfiguration, LLMConfigurationMasked
from app.services.llm_config_service import LLMConfigService

# Configure logger
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/llm-config", tags=["LLM Configuration"])

# Initialize service
llm_config_service = LLMConfigService()


# Pydantic models for request/response validation
class LLMConfigCreate(BaseModel):
    """Request model for creating a new LLM configuration"""

    name: str = Field(
        ..., min_length=1, max_length=100, description="User-friendly name"
    )
    description: Optional[str] = Field(
        None, max_length=500, description="Optional description"
    )
    base_url: str = Field(..., min_length=1, description="API endpoint URL")
    api_key: str = Field(
        ..., min_length=1, max_length=500, description="Authentication key"
    )
    model_name: str = Field(
        ..., min_length=1, max_length=200, description="Model identifier"
    )
    is_active: bool = Field(False, description="Whether to set as active configuration")
    always_starts_with_thinking: bool = Field(
        False, description="Whether model always starts responses with thinking block"
    )


class LLMConfigUpdate(BaseModel):
    """Request model for updating an existing LLM configuration"""

    name: Optional[str] = Field(
        None, min_length=1, max_length=100, description="User-friendly name"
    )
    description: Optional[str] = Field(
        None, max_length=500, description="Optional description"
    )
    base_url: Optional[str] = Field(None, min_length=1, description="API endpoint URL")
    api_key: Optional[str] = Field(
        None, min_length=1, max_length=500, description="Authentication key"
    )
    model_name: Optional[str] = Field(
        None, min_length=1, max_length=200, description="Model identifier"
    )
    always_starts_with_thinking: Optional[bool] = Field(
        None, description="Whether model always starts responses with thinking block"
    )


@router.get("/list")
async def list_configurations():
    """
    List all LLM configurations with masked API keys.

    Returns:
        Dictionary with list of configurations
    """
    try:
        configurations: List[LLMConfigurationMasked] = (
            llm_config_service.get_all_configurations()
        )
        return {"configurations": configurations}
    except Exception as e:
        logger.error(f"Error listing configurations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/active")
async def get_active_configuration():
    """
    Get the currently active LLM configuration.

    Returns:
        Active configuration with masked API key

    Raises:
        404: No active configuration found
    """
    try:
        config: Optional[LLMConfiguration] = (
            llm_config_service.get_active_configuration()
        )
        if not config:
            raise HTTPException(
                status_code=404, detail="No active LLM configuration found"
            )

        # Convert to masked version for response
        masked_config = LLMConfigurationMasked(
            id=config.id,
            name=config.name,
            description=config.description,
            base_url=config.base_url,
            api_key_preview=llm_config_service.mask_api_key(config.api_key),
            model_name=config.model_name,
            is_active=config.is_active,
            always_starts_with_thinking=config.always_starts_with_thinking,
            created_at=config.created_at,
            updated_at=config.updated_at,
        )

        return masked_config
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting active configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{config_id}")
async def get_configuration(config_id: int):
    """
    Get a specific LLM configuration by ID.

    Args:
        config_id: Configuration ID

    Returns:
        Configuration with masked API key

    Raises:
        404: Configuration not found
    """
    try:
        config: Optional[LLMConfigurationMasked] = (
            llm_config_service.get_configuration_by_id(config_id)
        )
        if not config:
            raise HTTPException(
                status_code=404, detail=f"Configuration with ID {config_id} not found"
            )
        return config
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting configuration {config_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def create_configuration(config: LLMConfigCreate):
    """
    Create a new LLM configuration.

    Args:
        config: Configuration data

    Returns:
        Created configuration with masked API key

    Raises:
        400: Invalid configuration data
        409: Configuration name already exists
    """
    try:
        created: LLMConfigurationMasked = llm_config_service.create_configuration(
            name=config.name,
            base_url=config.base_url,
            api_key=config.api_key,
            model_name=config.model_name,
            description=config.description,
            is_active=config.is_active,
            always_starts_with_thinking=config.always_starts_with_thinking,
        )
        return created
    except ValueError as e:
        # Name already exists
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating configuration: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{config_id}")
async def update_configuration(config_id: int, updates: LLMConfigUpdate):
    """
    Update an existing LLM configuration.

    Args:
        config_id: Configuration ID
        updates: Fields to update

    Returns:
        Updated configuration with masked API key

    Raises:
        404: Configuration not found
        409: Updated name already exists
    """
    try:
        updated: LLMConfigurationMasked = llm_config_service.update_configuration(
            config_id=config_id,
            name=updates.name,
            description=updates.description,
            base_url=updates.base_url,
            api_key=updates.api_key,
            model_name=updates.model_name,
            always_starts_with_thinking=updates.always_starts_with_thinking,
        )
        return updated
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating configuration {config_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{config_id}/activate")
async def activate_configuration(config_id: int):
    """
    Activate a configuration (deactivates all others).
    This will reload the OllamaService configuration.

    Args:
        config_id: Configuration ID to activate

    Returns:
        Activation result with configuration details

    Raises:
        404: Configuration not found
    """
    try:
        logger.info(f"🔄 [ACTIVATION] Activating LLM configuration ID: {config_id}")
        result = llm_config_service.activate_configuration(config_id)
        logger.info(
            f"✅ [ACTIVATION] Database updated. New active config: {result.get('new_active_id')}"
        )

        # Trigger OllamaService to reload configuration
        # This will be implemented when we modify OllamaService
        try:
            from app.services.ollama_service import ollama_service

            logger.info(
                "🔄 [ACTIVATION] Calling ollama_service.reload_configuration()..."
            )
            ollama_service.reload_configuration()
            logger.info(
                "✅ [ACTIVATION] OllamaService configuration reloaded successfully!"
            )
        except Exception as reload_error:
            logger.warning(
                f"⚠️ [ACTIVATION] Failed to reload OllamaService: {reload_error}"
            )
            # Don't fail the activation if reload fails

        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ [ACTIVATION] Error activating configuration {config_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{config_id}")
async def delete_configuration(config_id: int):
    """
    Delete a configuration.
    Cannot delete the active configuration.

    Args:
        config_id: Configuration ID to delete

    Returns:
        Success message

    Raises:
        404: Configuration not found
        400: Cannot delete active configuration
    """
    try:
        llm_config_service.delete_configuration(config_id)
        return {"message": "Configuration deleted successfully", "id": config_id}
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting configuration {config_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{config_id}/test")
async def test_configuration(config_id: int):
    """
    Test connection to LLM with a specific configuration.
    Sends a simple test message and measures response time.

    Args:
        config_id: Configuration ID to test

    Returns:
        Test result with success status and response details
    """
    import time

    try:
        # Get the configuration (with full API key for testing)
        with llm_config_service.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT base_url, api_key, model_name
                FROM llm_configurations
                WHERE id = ?
            """,
                (config_id,),
            )
            row = cursor.fetchone()

            if not row:
                raise HTTPException(
                    status_code=404,
                    detail=f"Configuration with ID {config_id} not found",
                )

        base_url = row["base_url"]
        api_key = row["api_key"]
        model_name = row["model_name"]

        # Create temporary client
        client = AsyncOpenAI(base_url=base_url, api_key=api_key)

        # Send test message and measure time
        start_time = time.time()

        try:
            response = await client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "user",
                        "content": "Hello, respond with just 'OK' if you're working.",
                    }
                ],
                max_tokens=50,
            )

            latency_ms = int((time.time() - start_time) * 1000)

            content = response.choices[0].message.content or ""
            return {
                "success": True,
                "message": "Connection successful",
                "model_name": model_name,
                "test_response": content.strip(),
                "latency_ms": latency_ms,
            }

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)

            return {
                "success": False,
                "message": "Connection failed",
                "error": str(e),
                "error_type": type(e).__name__,
                "latency_ms": latency_ms,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing configuration {config_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
