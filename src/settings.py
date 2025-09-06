"""
Модуль настроек приложения с использованием Pydantic и EnvYAML.
Загружает конфигурацию из YAML файла с поддержкой переменных окружения.
"""

import argparse
import os
from functools import cache

from envyaml import EnvYAML
from pydantic import BaseModel, Field


class OpenAIConfig(BaseModel):
    """Настройки OpenAI API."""

    api_key: str = Field(description="API ключ")
    base_url: str = Field(default="https://api.openai.com/v1", description="Базовый URL")
    model: str = Field(default="gpt-4o-mini", description="Модель для использования")
    max_tokens: int = Field(default=8000, description="Максимальное количество токенов")
    temperature: float = Field(default=0.4, ge=0.0, le=1.0, description="Температура генерации")
    proxy: str = Field(default="", description="Proxy URL (e.g., socks5://127.0.0.1:1081 or http://127.0.0.1:8080)")


class TavilyConfig(BaseModel):
    """Настройки Tavily Search API."""

    api_key: str = Field(description="Tavily API ключ")


class SearchConfig(BaseModel):
    """Настройки поиска."""

    max_results: int = Field(default=10, ge=1, description="Максимальное количество результатов поиска")


class ScrapingConfig(BaseModel):
    """Настройки скрепинга веб-страниц."""

    enabled: bool = Field(default=False, description="Включить скрепинг полного текста")
    max_pages: int = Field(default=5, gt=0, description="Максимум страниц для скрепинга")
    content_limit: int = Field(default=1500, gt=0, description="Лимит символов контента на источник")


class PromptsConfig(BaseModel):
    """Настройки промптов."""

    prompts_dir: str = Field(default="prompts", description="Директория с промптами")
    tool_function_prompt_file: str = Field(
        default="tool_function_prompt.txt", description="Файл промпта для функций инструментов"
    )
    system_prompt_file: str = Field(default="system_prompt.txt", description="Файл системного промпта")


class ExecutionConfig(BaseModel):
    """Настройки выполнения приложения."""

    max_steps: int = Field(default=6, gt=0, description="Максимальное количество шагов выполнения")
    reports_dir: str = Field(default="reports", description="Директория для сохранения отчетов")


class AppConfig(BaseModel):
    """Главная конфигурация приложения."""

    openai: OpenAIConfig = Field(description="Настройки OpenAI")
    tavily: TavilyConfig = Field(description="Настройки Tavily")
    search: SearchConfig = Field(default_factory=SearchConfig, description="Настройки поиска")
    scraping: ScrapingConfig = Field(default_factory=ScrapingConfig, description="Настройки скрепинга")
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig, description="Настройки выполнения")
    prompts: PromptsConfig = Field(default_factory=PromptsConfig, description="Настройки промптов")


class ServerConfig(BaseModel):
    """Конфигурация сервера."""

    host: str = Field(default="0.0.0.0", description="Хост для прослушивания")
    port: int = Field(default=8010, gt=0, le=65535, description="Порт для прослушивания")
    app_config: AppConfig = Field(description="Конфигурация приложения")


def get_config(argv=None) -> ServerConfig:
    parser = argparse.ArgumentParser(description="SGR Deep Research Server")
    parser.add_argument(
        "--host", type=str, dest="host", default=os.environ.get("HOST", "0.0.0.0"), help="Хост для прослушивания"
    )
    parser.add_argument(
        "--port", type=int, dest="port", default=int(os.environ.get("PORT", 8010)), help="Порт для прослушивания"
    )
    parser.add_argument(
        "--app_config",
        dest="app_config_path",
        required=False,
        type=str,
        default=os.environ.get("APP_CONFIG", "config.yaml"),
        help="Путь к файлу конфигурации YAML",
    )

    args = parser.parse_args(argv)

    return ServerConfig(
        host=args.host, port=args.port, app_config=AppConfig.model_validate(dict(EnvYAML(args.app_config_path)))
    )
