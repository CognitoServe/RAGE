"""
Tests for configuration settings.
"""

from cognitive_runtime.config.settings import load_settings


def test_load_default_settings():
    """Ensure settings can be loaded with default values."""
    settings = load_settings()
    assert settings.environment == "production"
    assert settings.logging.level == "INFO"
    assert settings.logging.format == "json"
    assert settings.storage.db_path == "sqlite:///memory.db"
