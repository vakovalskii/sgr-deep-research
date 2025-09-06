#!/usr/bin/env python3
"""
Демонстрация интерактивной оболочки SGR с симуляцией пользовательского ввода.
"""

import asyncio
import sys
from pathlib import Path

# Добавляем src в путь для импорта
sys.path.insert(0, str(Path(__file__).parent))

from cli import SGRShell


async def demo_interactive():
    """Демонстрирует интерактивную оболочку с предустановленными командами."""
    shell = SGRShell()
    
    print("🎬 ДЕМОНСТРАЦИЯ ИНТЕРАКТИВНОЙ ОБОЛОЧКИ SGR")
    print("=" * 60)
    print()
    
    # Симулируем команды
    commands = [
        "/help",
        "Исследовать тренды ИИ в 2024 году",
        "/status",
        "/sources",
        "/clear",
        "Research BMW X6 2025 prices in Russia",
        "/quit"
    ]
    
    for cmd in commands:
        print(f"🔍 sgr> {cmd}")
        if not await shell.process_command(cmd):
            break
        print()


if __name__ == "__main__":
    asyncio.run(demo_interactive())
