#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Centralized application settings using Pydantic Settings (v2).

Loads configuration in the following precedence (highest first):
1) Environment variables
2) .env file (if present)
3) config.yaml (if present)
4) Defaults in the model

Exports:
- settings: AppSettings instance
- CONFIG: dict view of settings for legacy access (CONFIG["key"]).
"""

from __future__ import annotations

from typing import Any, Dict
import os

import yaml
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
    PydanticBaseSettingsSource,
)


class YamlConfigSettingsSource(PydanticBaseSettingsSource):
    """Custom settings source that reads from config.yaml file."""

    def get_field_value(self, field_info, field_name: str):
        # Not used in this implementation
        return None

    def prepare_field_value(self, field_name: str, value, value_is_complex: bool):
        return value

    def __call__(self) -> Dict[str, Any]:
        """Read config from config.yaml if it exists and map to flat settings
        keys."""
        path = os.path.join(os.getcwd(), "config.yaml")
        if not os.path.exists(path):
            return {}

        try:
            with open(path, "r", encoding="utf-8") as f:
                y = yaml.safe_load(f) or {}
        except Exception:
            return {}

        result: Dict[str, Any] = {}

        # OpenAI block
        if isinstance(y.get("openai"), dict):
            o = y["openai"]
            if "api_key" in o:
                result["openai_api_key"] = o.get("api_key")
            if "base_url" in o:
                result["openai_base_url"] = o.get("base_url", "")
            if "model" in o:
                result["openai_model"] = o.get("model", "gpt-4o-mini")
            if "proxy" in o:
                result["openai_proxy"] = o.get("proxy", "")
            if "max_tokens" in o:
                result["max_tokens"] = int(o.get("max_tokens", 6000))
            if "temperature" in o:
                result["temperature"] = float(o.get("temperature", 0.3))

        # Tavily block
        if isinstance(y.get("tavily"), dict):
            t = y["tavily"]
            if "api_key" in t:
                result["tavily_api_key"] = t.get("api_key")

        # Search block
        if isinstance(y.get("search"), dict):
            s = y["search"]
            if "max_results" in s:
                result["max_search_results"] = int(s.get("max_results", 10))

        # Execution block
        if isinstance(y.get("execution"), dict):
            ex = y["execution"]
            if "max_rounds" in ex:
                result["max_rounds"] = int(ex.get("max_rounds", 8))
            if "reports_dir" in ex:
                result["reports_directory"] = ex.get("reports_dir", "reports")
            if "max_searches_total" in ex:
                result["max_searches_total"] = int(ex.get("max_searches_total", 6))

        # Note: so_temperature is controlled via env (SO_TEMPERATURE) or default below
        return result


class AppSettings(BaseSettings):
    # OpenAI
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_proxy: str = ""
    max_tokens: int = 6000
    temperature: float = 0.3

    # Tavily
    tavily_api_key: str = ""

    # Search/Execution
    max_search_results: int = 10
    max_rounds: int = 8
    reports_directory: str = "reports"
    max_searches_total: int = 6
    so_temperature: float = 0.1

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        extra="ignore",
        # Allow env vars to match our uppercase names exactly
        env_parse_none_str="",  # treat empty strings as valid empty values
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        # Order: env > dotenv > yaml > init > file secrets
        return (
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls),
            init_settings,
            file_secret_settings,
        )


# Instantiate settings and a legacy dict view for minimal code changes
settings = AppSettings()
CONFIG: Dict[str, Any] = settings.model_dump()
