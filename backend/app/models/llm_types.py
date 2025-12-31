"""
LLM Configuration Type Definitions

This module defines Pydantic models for LLM configuration objects
to provide type safety and validation throughout the codebase.
"""

from pydantic import BaseModel


class LLMConfiguration(BaseModel):
    """
    Complete LLM configuration as stored in database.
    All fields are required unless marked Optional.
    """

    id: int
    name: str
    description: str | None
    base_url: str
    api_key: str
    model_name: str
    is_active: bool
    always_starts_with_thinking: bool
    created_at: str
    updated_at: str


class LLMConfigurationMasked(BaseModel):
    """
    LLM configuration with masked API key for external use.
    Used when returning configs to frontend or logging.
    """

    id: int
    name: str
    description: str | None
    base_url: str
    api_key_preview: str  # Masked version
    model_name: str
    is_active: bool
    always_starts_with_thinking: bool
    created_at: str
    updated_at: str


class LLMConfigurationPartial(BaseModel):
    """
    Partial LLM configuration for updates.
    All fields are optional.
    """

    name: str | None = None
    description: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    model_name: str | None = None
    always_starts_with_thinking: bool | None = None
