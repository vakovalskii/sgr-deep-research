#!/usr/bin/env python3
"""
Интерактивная оболочка (REPL) для SGRResearchAgent.
Поддерживает многоязычность и интерактивные уточнения.
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

# Добавляем src в путь для импорта
sys.path.insert(0, str(Path(__file__).parent))

from core.agent import SGRResearchAgent
from settings import get_config


class SGRShell:
    """Интерактивная оболочка для SGR агента."""
    
    def __init__(self):
        self.config = get_config(argv=[]).app_config
        self.agent: Optional[SGRResearchAgent] = None
        self.current_task = None
        
    def print_banner(self):
        """Выводит баннер приветствия."""
        print("=" * 60)
        print("🧠 SGR Deep Research - Interactive Shell")
        print("=" * 60)
        print("Доступные команды:")
        print("  /help     - Показать справку")
        print("  /status   - Показать статус текущего агента")
        print("  /sources  - Показать найденные источники")
        print("  /clear    - Очистить текущую задачу")
        print("  /quit     - Выйти из оболочки")
        print("  /exit     - Выйти из оболочки")
        print()
        print("Для начала исследования просто напишите ваш запрос!")
        print("Примеры:")
        print("  • Исследовать тренды ИИ в 2024 году")
        print("  • Research BMW X6 2025 prices in Russia")
        print("  • Analyser les tendances du marché crypto en 2024")
        print("=" * 60)
        print()

    def print_help(self):
        """Выводит справку по командам."""
        print("\n📚 Справка по командам:")
        print("=" * 40)
        print("/help     - Показать эту справку")
        print("/status   - Показать статус текущего агента")
        print("/sources  - Показать все найденные источники")
        print("/clear    - Очистить текущую задачу и начать заново")
        print("/quit     - Выйти из оболочки")
        print("/exit     - Выйти из оболочки")
        print()
        print("💡 Совет: Просто напишите ваш запрос для начала исследования!")
        print("Система автоматически определит язык и будет отвечать на том же языке.")
        print()

    def print_status(self):
        """Выводит статус текущего агента."""
        if not self.agent:
            print("❌ Нет активного агента. Начните новое исследование!")
            return
            
        print(f"\n🤖 Статус агента: {self.agent.id}")
        print(f"📋 Задача: {self.agent.task}")
        print(f"📊 Состояние: {self.agent.state.value}")
        print(f"🔍 Поисков выполнено: {self.agent._context.searches_used}")
        print(f"❓ Уточнений запрошено: {self.agent._context.clarifications_used}")
        print(f"📚 Источников найдено: {len(self.agent._context.sources)}")
        print()

    def print_sources(self):
        """Выводит найденные источники."""
        if not self.agent or not self.agent._context.sources:
            print("❌ Нет найденных источников.")
            return
            
        print(f"\n📚 Найденные источники ({len(self.agent._context.sources)}):")
        print("=" * 50)
        for source in self.agent._context.sources.values():
            print(f"  • {source}")
        print()

    def clear_agent(self):
        """Очищает текущего агента."""
        if self.agent:
            print(f"🧹 Очистка агента {self.agent.id}...")
            self.agent = None
            self.current_task = None
            print("✅ Готов к новой задаче!")
        else:
            print("❌ Нет активного агента для очистки.")

    async def handle_clarification(self):
        """Обрабатывает запрос уточнений от агента."""
        if not self.agent or not self.agent._context.current_state:
            return
            
        current_state = self.agent._context.current_state
        if not hasattr(current_state.function, 'questions'):
            return
            
        print("\n" + "=" * 60)
        print("❓ АГЕНТ ЗАПРАШИВАЕТ УТОЧНЕНИЯ")
        print("=" * 60)
        
        # Показываем вопросы
        print("\n📝 Вопросы:")
        for i, question in enumerate(current_state.function.questions, 1):
            print(f"  {i}. {question}")
        
        # Показываем неясные термины
        if hasattr(current_state.function, 'unclear_terms') and current_state.function.unclear_terms:
            print(f"\n❓ Неясные термины: {', '.join(current_state.function.unclear_terms)}")
        
        # Показываем предположения
        if hasattr(current_state.function, 'assumptions') and current_state.function.assumptions:
            print(f"\n💭 Возможные интерпретации:")
            for assumption in current_state.function.assumptions:
                print(f"  • {assumption}")
        
        print("\n" + "-" * 40)
        print("💡 Пожалуйста, предоставьте уточнения:")
        
        # Получаем уточнения от пользователя
        clarification = input("> ").strip()
        
        if clarification:
            print(f"\n✅ Предоставляем уточнения: {clarification}")
            await self.agent.provide_clarification(clarification)
        else:
            print("\n⚠️  Уточнения не предоставлены, продолжаем с текущим контекстом...")
            await self.agent.provide_clarification("Никаких дополнительных уточнений не требуется")

    async def execute_research(self, query: str):
        """Выполняет исследование с заданным запросом."""
        print(f"\n🔍 Начинаем исследование: {query}")
        print("=" * 60)
        
        # Создаем нового агента
        self.agent = SGRResearchAgent(task=query, config=self.config)
        self.current_task = query
        
        print(f"🤖 Создан агент: {self.agent.id}")
        print(f"📊 Максимум шагов: {self.config.execution.max_steps}")
        print(f"🔍 Максимум поисков: {self.agent.max_searches}")
        print(f"❓ Максимум уточнений: {self.agent.max_clarifications}")
        print()
        
        # Запускаем выполнение в фоне
        task = asyncio.create_task(self.agent.execute())
        
        # Мониторим состояние агента
        while not task.done():
            await asyncio.sleep(0.1)
            
            # Проверяем, нужны ли уточнения
            if self.agent.state.value == "waiting_for_clarification":
                await self.handle_clarification()
        
        # Ждем завершения
        try:
            await task
        except Exception as e:
            print(f"\n❌ Ошибка при выполнении исследования: {e}")
            return
        
        print("\n" + "=" * 60)
        print("✅ Исследование завершено!")
        print(f"📊 Источников найдено: {len(self.agent._context.sources)}")
        print(f"🔍 Поисков выполнено: {self.agent._context.searches_used}")
        print(f"❓ Уточнений использовано: {self.agent._context.clarifications_used}")
        print(f"📝 Финальное состояние: {self.agent.state.value}")
        
        # Показываем найденные источники
        if self.agent._context.sources:
            print(f"\n📚 Найдено источников: {len(self.agent._context.sources)}")
            for source in list(self.agent._context.sources.values())[:3]:  # Показываем первые 3
                print(f"  • {source}")
            if len(self.agent._context.sources) > 3:
                print(f"  ... и еще {len(self.agent._context.sources) - 3} источников")
        
        print("\n💡 Используйте /sources для просмотра всех источников")
        print("💡 Используйте /status для просмотра статуса агента")
        print("💡 Начните новое исследование, написав новый запрос")
        print("=" * 60)

    async def process_command(self, line: str) -> bool:
        """Обрабатывает команды оболочки. Возвращает True если нужно продолжить."""
        line = line.strip()
        
        if not line:
            return True
            
        if line.startswith('/'):
            cmd = line[1:].lower()
            
            if cmd in ['quit', 'exit']:
                print("\n👋 До свидания!")
                return False
            elif cmd == 'help':
                self.print_help()
            elif cmd == 'status':
                self.print_status()
            elif cmd == 'sources':
                self.print_sources()
            elif cmd == 'clear':
                self.clear_agent()
            else:
                print(f"❌ Неизвестная команда: {cmd}")
                print("💡 Используйте /help для просмотра доступных команд")
        else:
            # Это исследовательский запрос
            await self.execute_research(line)
        
        return True

    async def run(self):
        """Запускает интерактивную оболочку."""
        self.print_banner()
        
        try:
            while True:
                try:
                    # Получаем ввод от пользователя
                    line = input("🔍 sgr> ").strip()
                    
                    if not await self.process_command(line):
                        break
                        
                except KeyboardInterrupt:
                    print("\n\n⏹️  Использование Ctrl+C для выхода. Используйте /quit для корректного завершения.")
                    continue
                except EOFError:
                    print("\n\n👋 До свидания!")
                    break
                    
        except Exception as e:
            print(f"\n❌ Неожиданная ошибка: {e}")
            import traceback
            traceback.print_exc()


def main():
    """Главная функция."""
    if len(sys.argv) > 1:
        # Если переданы аргументы, используем их как запрос
        query = " ".join(sys.argv[1:])
        shell = SGRShell()
        asyncio.run(shell.execute_research(query))
    else:
        # Запускаем интерактивную оболочку
        shell = SGRShell()
        asyncio.run(shell.run())


if __name__ == "__main__":
    main()
