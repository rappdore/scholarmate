"""
LLM Configuration Type Definitions

This module defines TypedDict classes for LLM configuration objects
to provide type safety throughout the codebase.
"""

from typing import TypedDict


class LLMConfiguration(TypedDict):
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


class LLMConfigurationMasked(TypedDict):
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


class LLMConfigurationPartial(TypedDict, total=False):
    """
    Partial LLM configuration for updates.
    All fields are optional (total=False).
    """

    name: str
    description: str
    base_url: str
    api_key: str
    model_name: str
    always_starts_with_thinking: bool
