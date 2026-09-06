"""Validate Telegram credentials without network access or embedded defaults."""

import os
import re


class ConfigurationError(RuntimeError):
    """A required runtime setting is absent or invalid."""


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise ConfigurationError(f"Required environment variable is missing: {name}")
    return value


def load_telegram_credentials():
    raw_id = required_env("API_ID")
    try:
        api_id = int(raw_id)
    except ValueError:
        raise ConfigurationError("API_ID must be a positive integer") from None
    if api_id <= 0:
        raise ConfigurationError("API_ID must be a positive integer")
    api_hash = required_env("API_HASH").strip()
    if not re.fullmatch(r"[0-9a-fA-F]{32}", api_hash):
        raise ConfigurationError("API_HASH must contain 32 hexadecimal characters")
    return api_id, api_hash
