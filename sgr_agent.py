#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SGR Research Agent - Clean Architecture
Двухфазный исследовательский агент:
1. Reasoning Phase: Анализ ситуации через Structured Output
2. Action Phase: Выполнение действий через Function Calls
"""

import json
import yaml
import asyncio
from typing import Any, Dict, List
from pydantic import ValidationError

from openai import OpenAI
from tavily import TavilyClient
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule

# Локальные модули
from models import (
    ReasoningStep,
    ClarificationStep,
    WebSearchStep,
    CreateReportStep,
    ReportCompletionStep,
    ReadLocalFileStep,
    CreateLocalFileStep,
    UpdateLocalFileStep,
    ListDirectoryStep,
    CreateDirectoryStep,
    SimpleAnswerStep,
    GetCurrentDatetimeStep,
)
from tool_schemas import get_all_tools, make_tool_choice_generate_reasoning
from settings import CONFIG as SETTINGS_CONFIG
from executors import get_executors


# =============================================================================
# CONFIGURATION
# =============================================================================


def load_config() -> Dict[str, Any]:
    """Legacy shim: return dict view of Pydantic settings."""
    return SETTINGS_CONFIG


def load_prompts() -> Dict[str, Any]:
    """Load system prompts from prompts.yaml."""
    try:
        with open("prompts.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        raise RuntimeError(f"Could not load prompts.yaml: {e}")


# =============================================================================
# INITIALIZATION
# =============================================================================

console = Console()
print = console.print

CONFIG = load_config()
PROMPTS = load_prompts()

# Validate required config
if not CONFIG["openai_api_key"]:
    print("[red]ERROR: OPENAI_API_KEY is required[/red]")
    raise SystemExit(1)
if not CONFIG["tavily_api_key"]:
    print("[red]ERROR: TAVILY_API_KEY is required[/red]")
    raise SystemExit(1)

# Initialize clients
openai_kwargs = {"api_key": CONFIG["openai_api_key"]}
if CONFIG["openai_base_url"]:
    openai_kwargs["base_url"] = CONFIG["openai_base_url"]

# Add proxy support if configured
if "openai_proxy" in CONFIG and CONFIG["openai_proxy"]:
    import httpx

    openai_kwargs["http_client"] = httpx.Client(
        follow_redirects=True,
        limits=httpx.Limits(max_connections=10),
        proxy=CONFIG["openai_proxy"],
    )

client = OpenAI(**openai_kwargs)
tavily = TavilyClient(CONFIG["tavily_api_key"])
executors = get_executors()


# =============================================================================
# CONTEXT MANAGEMENT
# =============================================================================


def create_fresh_context() -> Dict[str, Any]:
    """Create fresh research context."""
    return {
        "searches": [],
        "sources": {},  # url -> {"number": int, "title": str, "url": str}
        "citation_counter": 0,
        "clarification_used": False,
        "searches_total": 0,
        "report_created": False,
        "simple_answer_given": False,
        "file_created": False,
        "created_files": [],  # Список созданных файлов для истории
        "knowledge_files": [],  # Список файлов знаний
        "dialog_history": [],  # История диалога между задачами
        "task_summaries": [],  # Краткие сводки выполненных задач
    }


def create_task_context(global_context: Dict[str, Any]) -> Dict[str, Any]:
    """Create context for new task, preserving some global data."""
    return {
        # Сбрасываем состояние задачи
        "searches": [],
        "sources": {},
        "citation_counter": global_context.get(
            "citation_counter", 0
        ),  # Сохраняем счетчик
        "clarification_used": False,
        "searches_total": 0,
        "report_created": False,
        "simple_answer_given": False,
        "file_created": False,
        # Сохраняем глобальные данные
        "created_files": global_context.get("created_files", []),
        "knowledge_files": global_context.get("knowledge_files", []),
        "dialog_history": global_context.get("dialog_history", []),  # История диалога
        "task_summaries": global_context.get("task_summaries", []),  # Сводки задач
    }


def update_global_context(
    global_context: Dict[str, Any],
    task_context: Dict[str, Any],
    messages: List[Dict[str, Any]] = None,
) -> None:
    """Update global context with data from completed task."""
    # Обновляем счетчики
    global_context["citation_counter"] = task_context.get("citation_counter", 0)

    # Добавляем созданные файлы
    if task_context.get("file_created", False) and task_context.get(
        "created_file_path"
    ):
        file_path = task_context["created_file_path"]
        if file_path not in global_context.get("created_files", []):
            global_context.setdefault("created_files", []).append(file_path)

        # Если это файл знаний, добавляем в специальный список
        if "knowledge" in file_path.lower() or file_path.endswith("knowledge_today.md"):
            if file_path not in global_context.get("knowledge_files", []):
                global_context.setdefault("knowledge_files", []).append(file_path)

    # Создаем краткую сводку выполненной задачи для истории
    if messages:
        # Находим user запросы и assistant ответы
        user_requests = [
            msg["content"] for msg in messages if msg.get("role") == "user"
        ]

        # assistant_responses = [
        #     msg["content"]
        #     for msg in messages
        #     if msg.get("role") == "assistant" and msg.get("content")
        # ]

        # Создаем сводку задачи (для user запросов)
        if user_requests:
            task_summary = {
                "user_request": user_requests[-1],  # Последний запрос пользователя
                "actions_performed": [],
                "files_created": (
                    [task_context.get("created_file_path")]
                    if task_context.get("created_file_path")
                    else []
                ),
                "searches_done": task_context.get("searches_total", 0),
            }

            # Создаем сводку выполненной задачи

            # Определяем выполненные действия по tool calls
            tool_calls_count = 0
            for msg in messages:
                if msg.get("tool_calls"):
                    tool_calls_count += len(msg.get("tool_calls", []))
                    for tc in msg.get("tool_calls", []):
                        tool_name = tc.get("function", {}).get("name", "")

                        if tool_name == "web_search":
                            task_summary["actions_performed"].append(
                                "поиск в интернете"
                            )
                        elif tool_name == "create_local_file":
                            task_summary["actions_performed"].append("создание файла")
                        elif tool_name == "read_local_file":
                            task_summary["actions_performed"].append("чтение файла")
                        elif tool_name == "simple_answer":
                            task_summary["actions_performed"].append(
                                "предоставление ответа"
                            )

            global_context.setdefault("task_summaries", []).append(task_summary)
        else:
            # Нет данных для создания сводки
            pass


# =============================================================================
# VALIDATION
# =============================================================================


def validate_reasoning_step(rs: ReasoningStep, context: Dict[str, Any]) -> List[str]:
    """Validate reasoning step against context."""
    errors: List[str] = []

    # Anti-cycling checks - только если clarification была успешно завершена
    if (
        context.get("clarification_used", False)
        and context.get("clarification_completed", False)
        and rs.next_action == "clarify"
    ):
        errors.append(
            "ANTI-CYCLING: Clarification already completed; repetition is forbidden."
        )

    # Убираем ограничение - теперь можно создавать несколько отчетов
    # if context.get("report_created", False) and rs.next_action == "report":
    #     errors.append(
    #         "ANTI-CYCLING: Report already created; repeated creation is forbidden."
    #     )

    # Simple answer completion check
    if context.get("simple_answer_given", False):
        if rs.next_action != "complete":
            errors.append(
                "TASK COMPLETION: Simple answer already provided; task should be completed."
            )

    # File creation completion check
    if context.get("file_created", False):
        if rs.next_action not in ["complete", "simple_answer"]:
            errors.append(
                "TASK COMPLETION: File already created; task should be completed or provide simple answer."
            )

    # Search limits
    if rs.next_action == "search":
        if context.get("searches_total", 0) >= CONFIG["max_searches_total"]:
            errors.append(
                f"Search limit exceeded: already {context.get('searches_total',0)}, limit {CONFIG['max_searches_total']}."
            )

    return errors


# =============================================================================
# UI HELPERS
# =============================================================================


def pretty_print_reasoning(rs: ReasoningStep) -> None:
    """Display reasoning analysis in formatted table."""
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Field")
    table.add_column("Value", overflow="fold")

    table.add_row("Current", rs.current_situation)
    table.add_row("Plan status", rs.plan_status)
    table.add_row("Reasoning steps", " • ".join(rs.reasoning_steps))
    table.add_row("Next action", f"[bold cyan]{rs.next_action}[/bold cyan]")
    table.add_row("Action reasoning", rs.action_reasoning)
    table.add_row("Next steps", " → ".join(rs.next_steps))
    table.add_row("Searches done", str(rs.searches_done))
    table.add_row("Enough data", str(rs.enough_data))
    table.add_row("Task completed", str(rs.task_completed))

    print(Panel(table, title="🧠 Reasoning Analysis", border_style="magenta"))


def build_dialog_snapshot(messages: List[Dict[str, Any]], limit: int = 30) -> str:
    """Build compact dialog summary for context."""
    tail = messages[-limit:]
    lines = []

    for m in tail:
        role = m.get("role", "")
        content = m.get("content", "")
        tool_calls = m.get("tool_calls", [])

        # Truncate long content
        if isinstance(content, str) and len(content) > 4000:
            content = content[:4000] + " …[truncated]"

        msg_parts = [f"{role.upper()}: {content}"]
        if tool_calls:
            tool_info = [
                tc.get("function", {}).get("name", "unknown") for tc in tool_calls
            ]
            msg_parts.append(f" [tools: {', '.join(tool_info)}]")

        lines.append("".join(msg_parts))

    return "\n".join(lines)


# =============================================================================
# CORE PHASES
# =============================================================================


def exec_reasoning_phase(
    messages: List[Dict[str, Any]], task: str, context: Dict[str, Any]
) -> ReasoningStep:
    """Phase 1: Get reasoning analysis from model via Structured Output"""
    print("[blue]Phase 1: Analyzing situation...[/blue]")

    # Force reasoning call
    completion = client.chat.completions.create(
        model=CONFIG["openai_model"],
        temperature=CONFIG["temperature"],
        max_tokens=CONFIG["max_tokens"],
        tools=get_all_tools(),
        tool_choice=make_tool_choice_generate_reasoning(),
        messages=messages,
    )
    msg = completion.choices[0].message

    # Validate reasoning call
    if (
        not getattr(msg, "tool_calls", None)
        or len(msg.tool_calls) != 1
        or msg.tool_calls[0].function.name != "generate_reasoning"
    ):
        raise RuntimeError("Expected exactly one 'generate_reasoning' call.")

    # Add reasoning to message log
    reasoning_call_id = msg.tool_calls[0].id
    messages.append(
        {
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [
                {
                    "id": reasoning_call_id,
                    "type": "function",
                    "function": {"name": "generate_reasoning", "arguments": "{}"},
                }
            ],
        }
    )

    # Execute reasoning via SO call
    reasoning_result = exec_structured_output_reasoning(messages, task, context)

    # Add reasoning result to log
    messages.append(
        {
            "role": "tool",
            "tool_call_id": reasoning_call_id,
            "content": json.dumps(reasoning_result, ensure_ascii=False),
        }
    )

    if "error" in reasoning_result:
        raise RuntimeError(f"Reasoning validation failed: {reasoning_result['error']}")

    reasoning = ReasoningStep.model_validate(reasoning_result["reasoning"])
    pretty_print_reasoning(reasoning)

    return reasoning


def exec_structured_output_reasoning(
    messages: List[Dict[str, Any]], task: str, context: Dict[str, Any]
) -> Dict[str, Any]:
    """Internal SO call for reasoning analysis."""
    schema = ReasoningStep.model_json_schema()

    # Очищаем схему от лишних полей которые могут путать модель
    if "$defs" in schema:
        del schema["$defs"]
    if "title" in schema:
        del schema["title"]
    if "description" in schema:
        del schema["description"]

    dialog_snapshot = build_dialog_snapshot(messages, limit=30)

    # Добавляем историю предыдущих действий если есть в messages
    for msg in messages:
        content = msg.get("content") or ""
        if msg.get("role") == "assistant" and content.startswith(
            "Предыдущие действия в сессии:"
        ):
            dialog_snapshot = content + "\n\n" + dialog_snapshot
            break

    # Находим последний user request из messages
    last_user_message = ""
    for msg in reversed(messages):
        if msg.get("role") == "user" and msg.get("content"):
            last_user_message = msg.get("content")
            break

    # Если не нашли user message, используем task как fallback
    user_request = last_user_message if last_user_message else task

    so_messages = [
        {
            "role": "system",
            "content": PROMPTS["structured_output_reasoning"]["template"],
        },
        {"role": "user", "content": f"Current user request: {user_request}"},
        {
            "role": "user",
            "content": "Dialog history (for reasoning context):\n" + dialog_snapshot,
        },
        {
            "role": "user",
            "content": (
                f"Current state:\n"
                f"- searches_total: {context.get('searches_total', 0)}\n"
                f"- clarification_used: {context.get('clarification_used', False)}\n"
                f"- report_created: {context.get('report_created', False)}\n"
                f"- simple_answer_given: {context.get('simple_answer_given', False)}\n"
                f"- file_created: {context.get('file_created', False)}\n"
                f"- known_sources: {len(context.get('sources', {}))}\n"
                f"- last_queries: {[s.get('query') for s in context.get('searches', [])[-3:]]}\n"
                f"\nSession history context:\n"
                f"- created_files: {context.get('created_files', [])}\n"
                f"- knowledge_files: {context.get('knowledge_files', [])}\n"
                f"- previous_searches_count: {len(context.get('created_files', []))}\n"
                f"- recent_search_queries: {[s.get('query') for s in context.get('searches', [])[-2:]]}\n"
                f"- available_sources_count: {len(context.get('sources', {}))}\n"
                "\nReturn ReasoningStep object - analyze situation and decide next action."
            ),
        },
    ]

    completion = client.chat.completions.create(
        model=CONFIG["openai_model"],
        temperature=CONFIG["so_temperature"],
        max_tokens=CONFIG["max_tokens"],
        messages=so_messages,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "ReasoningStep",
                "schema": schema,
            },
        },
    )

    content = completion.choices[0].message.content or "{}"

    try:
        rs = ReasoningStep.model_validate_json(content)
    except ValidationError as ve:
        print(
            Panel(
                str(ve),
                title="❌ SO: Валидация ReasoningStep не прошла",
                border_style="red",
            )
        )
        return {"error": "validation_error", "details": json.loads(ve.json())}

    errors = validate_reasoning_step(rs, context)
    if errors:
        print(f"❌ Reasoning validation failed: {len(errors)} errors")
        return {"error": "reasoning_validation_failed", "errors": errors}

    return {"reasoning": json.loads(rs.model_dump_json())}


def build_context_info(context: Dict[str, Any], reasoning: ReasoningStep) -> str:
    """Build context information for action execution."""
    info_parts = []

    # Последние результаты поиска
    if context.get("searches") and len(context["searches"]) > 0:
        last_search = context["searches"][-1]
        info_parts.append("LAST SEARCH RESULTS:")
        info_parts.append(f"Query: {last_search.get('query', 'N/A')}")

        if "results" in last_search:
            info_parts.append("Found sources:")
            for i, result in enumerate(last_search["results"][:5], 1):
                title = result.get("title", "No title")[:100]
                url = result.get("url", "No URL")
                content = result.get("content", "No content")[:200]
                info_parts.append(f"{i}. {title} - {url}")
                info_parts.append(f"   Content: {content}...")

    # История созданных файлов
    if context.get("created_files"):
        info_parts.append("\nCREATED FILES IN SESSION:")
        for file_path in context["created_files"]:
            info_parts.append(f"- {file_path}")

    # Доступные источники
    if context.get("sources"):
        info_parts.append(f"\nAVAILABLE SOURCES ({len(context['sources'])}):")
        for url, source_info in list(context["sources"].items())[:3]:
            info_parts.append(
                f"[{source_info['number']}] {source_info['title']} - {url}"
            )

    # Текущая задача
    info_parts.append(f"\nCURRENT ACTION: {reasoning.next_action}")
    info_parts.append(f"REASONING: {reasoning.action_reasoning}")

    return "\n".join(info_parts)


def exec_action_phase(
    messages: List[Dict[str, Any]], reasoning: ReasoningStep, context: Dict[str, Any]
) -> None:
    """Phase 2: Let model execute appropriate tools based on reasoning"""
    print(f"[cyan]Phase 2: Executing action '{reasoning.next_action}'...[/cyan]")

    # Добавляем контекстную информацию для модели
    context_info = build_context_info(context, reasoning)
    action_messages = messages + [
        {
            "role": "user",
            "content": f"CONTEXT FOR ACTION:\n{context_info}\n\nExecute the planned action: {reasoning.next_action}",
        }
    ]

    # Model decides what tools to call
    completion = client.chat.completions.create(
        model=CONFIG["openai_model"],
        temperature=CONFIG["temperature"],
        max_tokens=CONFIG["max_tokens"],
        tools=get_all_tools(),
        tool_choice="auto",  # Let model decide!
        messages=action_messages,
    )
    msg = completion.choices[0].message

    # Process tool calls or text response
    if getattr(msg, "tool_calls", None):
        # Model called tools
        tc_dump = [
            {
                "id": tc.id,
                "type": tc.type,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in msg.tool_calls
        ]

        messages.append(
            {
                "role": "assistant",
                "content": msg.content,
                "tool_calls": tc_dump,
            }
        )

        # Execute each tool call
        for tc in msg.tool_calls:
            result = execute_tool_call(tc, context)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )
    else:
        # Model didn't call tools - just text response
        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "No action taken",
            }
        )


def execute_tool_call(tool_call, context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a single tool call."""
    tool_name = tool_call.function.name

    try:
        tool_args = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError:
        tool_args = {}

    # Execute tool locally
    if tool_name in executors:
        # Convert args to appropriate model and execute
        if tool_name == "clarification":
            step = ClarificationStep(tool="clarification", **tool_args)
            return executors[tool_name](step, context)
        elif tool_name == "web_search":
            step = WebSearchStep(tool="web_search", **tool_args)
            return executors[tool_name](step, context, tavily)
        elif tool_name == "create_report":
            step = CreateReportStep(tool="create_report", **tool_args)
            return executors[tool_name](step, context, CONFIG)
        elif tool_name == "report_completion":
            step = ReportCompletionStep(tool="report_completion", **tool_args)
            return executors[tool_name](step, context)
        elif tool_name == "read_local_file":
            step = ReadLocalFileStep(tool="read_local_file", **tool_args)
            return executors[tool_name](step, context)
        elif tool_name == "create_local_file":
            step = CreateLocalFileStep(tool="create_local_file", **tool_args)
            return executors[tool_name](step, context)
        elif tool_name == "update_local_file":
            step = UpdateLocalFileStep(tool="update_local_file", **tool_args)
            return executors[tool_name](step, context)
        elif tool_name == "list_directory":
            step = ListDirectoryStep(tool="list_directory", **tool_args)
            return executors[tool_name](step, context)
        elif tool_name == "create_directory":
            step = CreateDirectoryStep(tool="create_directory", **tool_args)
            return executors[tool_name](step, context)
        elif tool_name == "simple_answer":
            step = SimpleAnswerStep(tool="simple_answer", **tool_args)
            return executors[tool_name](step, context)
        elif tool_name == "get_current_datetime":
            step = GetCurrentDatetimeStep(tool="get_current_datetime", **tool_args)
            return executors[tool_name](step, context)
        else:
            return {"error": f"Unknown tool: {tool_name}"}
    else:
        return {"error": f"No executor for tool: {tool_name}"}


# =============================================================================
# MAIN RESEARCH ORCHESTRATION
# =============================================================================


async def run_research(task: str, global_context: Dict[str, Any]) -> None:
    """Main research orchestration - two-phase approach"""
    print(Panel(task, title="🔍 Research Task", title_align="left"))
    print(
        f"[green]🚀 Launch[/green]  model={CONFIG['openai_model']}  base_url={openai_kwargs.get('base_url','default')}"
    )

    # Initialize conversation with previous dialog history
    messages: List[Dict[str, Any]] = [
        {
            "role": "system",
            "content": PROMPTS["outer_system"]["template"].format(user_request=task),
        }
    ]

    # Добавляем сводку предыдущих задач как контекст
    task_summaries = global_context.get("task_summaries", [])

    if task_summaries:
        # Создаем сводное сообщение о предыдущих действиях
        previous_actions = []
        for summary in task_summaries[-5:]:  # Последние 5 задач
            actions = ", ".join(summary.get("actions_performed", []))
            files = ", ".join(summary.get("files_created", []))
            summary_text = (
                f"Запрос: '{summary.get('user_request', '')}' -> Действия: {actions}"
            )
            if files:
                summary_text += f" -> Созданы файлы: {files}"
            previous_actions.append(summary_text)

        if previous_actions:
            context_message = {
                "role": "assistant",
                "content": "Предыдущие действия в сессии:\n"
                + "\n".join(previous_actions),
            }
            messages.append(context_message)
            pass

    # Добавляем текущий запрос пользователя
    messages.append({"role": "user", "content": task})

    # Создаем контекст для текущей задачи, сохраняя некоторые данные из глобального
    context = create_task_context(global_context)

    # Main research loop
    rounds = 0
    while rounds < CONFIG["max_rounds"]:
        rounds += 1
        print(Rule(f"[bold]Round {rounds} — Reasoning + Action[/bold]"))

        try:
            # Phase 1: Reasoning Analysis
            reasoning = exec_reasoning_phase(messages, task, context)

            # Check completion
            if reasoning.task_completed:
                print(
                    Panel(
                        "Task marked as completed by reasoning.",
                        title="🏁 Completion",
                        border_style="green",
                    )
                )
                # Сохраняем данные в глобальный контекст
                update_global_context(global_context, context, messages)

                break

            # Phase 2: Execute Actions
            exec_action_phase(messages, reasoning, context)

        except Exception as e:
            print(
                Panel(
                    f"Error in round {rounds}: {e}",
                    title="❌ Error",
                    border_style="red",
                )
            )
            continue

    # Final statistics
    print(Rule("[dim]Session statistics[/dim]"))
    print(
        f"🔎 Searches: {context['searches_total']} | Sources: {len(context['sources'])}"
    )
    print(f"📁 Reports: ./{CONFIG['reports_directory']}/")


# =============================================================================
# CLI
# =============================================================================


def main():
    """Main CLI entry point."""
    print("[bold]🧠 SGR Research Agent — Two-Phase Architecture[/bold]\n")

    # Создаем глобальный контекст для сохранения между задачами
    global_context = create_fresh_context()

    try:
        while True:
            task = input("🔍 Enter research task (or 'quit'): ").strip()
            if task.lower() in ("quit", "exit"):
                print("👋 Exit.")
                break
            if not task:
                print("⚠️ Empty input, try again.")
                continue

            asyncio.run(run_research(task, global_context))

    except KeyboardInterrupt:
        print("\n👋 Interrupted by user.")


if __name__ == "__main__":
    main()
