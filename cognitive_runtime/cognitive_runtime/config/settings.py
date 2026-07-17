"""
Configuration loading for the Cognitive Runtime.

This module provides a strongly-typed, environment-aware configuration
using Pydantic v2 BaseSettings.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LoggingSettings(BaseSettings):
    """Configuration for logging subsystem."""

    level: str = Field(default="INFO", description="Global logging level.")
    format: str = Field(default="json", description="Log format (json or console).")


class StorageSettings(BaseSettings):
    """Configuration for storage subsystem (memory, rules, facts)."""

    db_path: str = Field(
        default="sqlite:///memory.db",
        description="Path to the primary SQLite database.",
    )


class CognitiveSettings(BaseSettings):
    """
    Root configuration object for Cognitive Runtime.
    Loads settings from environment variables or a .env file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    environment: str = Field(
        default="production",
        description="Runtime environment (development, testing, production).",
    )
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)


def load_settings(env_file: str | None = None) -> CognitiveSettings:
    """
    Initialize and return the global settings object.

    Args:
        env_file: Optional path to a .env file to load overriding default config.

    Returns:
        CognitiveSettings: The loaded settings instance.
    """
    if env_file:
        return CognitiveSettings(_env_file=env_file)
    return CognitiveSettings()
