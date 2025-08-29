#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SGR Research Agent - Function Executors
Содержит исполнителей всех функций агента
"""

import os
from datetime import datetime
from typing import Any, Dict

from rich.console import Console

from models import (
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
)

# Инициализация консоли
console = Console()
print = console.print


# =============================================================================
# CONTEXT & SOURCES
# =============================================================================


def add_citation(context: Dict[str, Any], url: str, title: str = "") -> int:
    """Add citation and return citation number."""
    if url in context["sources"]:
        return context["sources"][url]["number"]
    context["citation_counter"] += 1
    num = context["citation_counter"]
    context["sources"][url] = {"number": num, "title": title or "", "url": url}
    return num


def format_sources_block(context: Dict[str, Any]) -> str:
    """Format sources for report footer."""
    if not context["sources"]:
        return ""
    lines = ["", "## Sources"]
    for url, data in context["sources"].items():
        t = data["title"]
        n = data["number"]
        if t:
            lines.append(f"- [{n}] {t} - {url}")
        else:
            lines.append(f"- [{n}] {url}")
    return "\n".join(lines)


def _print_tree_structure(items: list, base_path: str) -> None:
    """Print items in tree structure format."""
    # Группируем элементы по директориям
    tree_dict = {}

    for item in items:
        path_parts = item["name"].split(os.sep) if item["name"] != "." else [""]
        current_dict = tree_dict

        for i, part in enumerate(path_parts):
            if part not in current_dict:
                current_dict[part] = {"type": "directory", "children": {}, "size": None}

            if i == len(path_parts) - 1:  # Последняя часть пути
                current_dict[part]["type"] = item["type"]
                current_dict[part]["size"] = item.get("size")

            current_dict = current_dict[part]["children"]

    def _print_tree_recursive(tree_dict: dict, prefix: str = "", is_last: bool = True):
        items_list = list(tree_dict.items())
        for i, (name, data) in enumerate(items_list):
            is_last_item = i == len(items_list) - 1

            # Определяем символы для отображения
            current_prefix = "└── " if is_last_item else "├── "
            next_prefix = prefix + ("    " if is_last_item else "│   ")

            # Отображаем элемент
            if data["type"] == "directory":
                print(f"{prefix}{current_prefix}📁 {name}/")
                if data["children"]:
                    _print_tree_recursive(data["children"], next_prefix, is_last_item)
            else:
                size_str = (
                    f" ({data['size']} bytes)" if data["size"] is not None else ""
                )
                print(f"{prefix}{current_prefix}📄 {name}{size_str}")

    _print_tree_recursive(tree_dict)


# =============================================================================
# FUNCTION EXECUTORS
# =============================================================================


def exec_clarification(
    step: ClarificationStep, context: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute clarification step - ask user for clarification"""
    context["clarification_used"] = True
    print("\n[bold yellow]🤔 CLARIFYING INFORMATION NEEDED[/bold yellow]")
    print(f"💭 Reason: {step.reasoning}")

    if step.unclear_terms:
        print("❓ Unclear terms: " + ", ".join(step.unclear_terms))

    if step.questions:
        print("\n[cyan]Questions for clarification:[/cyan]")
        for i, q in enumerate(step.questions, 1):
            print(f"   {i}. {q}")

    if step.assumptions:
        print("\n[green]Possible interpretations:[/green]")
        for a in step.assumptions:
            print(f"   • {a}")

    # Check if we're in API mode (force mode)
    force_mode = context.get("api_mode", False)

    if force_mode:
        # In API mode, auto-complete with assumptions
        auto_response = "Auto-completed in API mode"
        if step.assumptions:
            auto_response = (
                step.assumptions[0] if step.assumptions else "Auto-completed"
            )

        print(f"\n[green]🔄 API Mode: Auto-completing with: {auto_response}[/green]")

        return {
            "tool": "clarification",
            "status": "auto_completed",
            "user_input": auto_response,
            "questions": step.questions,
            "assumptions_used": step.assumptions,
            "task_completed": True,
        }

    # Wait for user response (interactive mode)
    print("\n[bold cyan]Please clarify your request:[/bold cyan]")
    try:
        user_clarification = input(">>> ").strip()
        if not user_clarification or user_clarification.lower() in ["quit", "exit"]:
            return {
                "tool": "clarification",
                "status": "cancelled",
                "user_input": "User cancelled",
            }

        return {
            "tool": "clarification",
            "status": "completed",
            "user_input": user_clarification,
            "questions": step.questions,
        }
    except (KeyboardInterrupt, EOFError):
        return {
            "tool": "clarification",
            "status": "cancelled",
            "user_input": "User cancelled",
        }


def exec_web_search(
    step: WebSearchStep, context: Dict[str, Any], tavily_client
) -> Dict[str, Any]:
    """Execute web search step."""
    q = step.query
    mx = int(step.max_results or 10)
    print(f"\n[cyan]🔎 Search:[/cyan] '{q}' (max={mx})")

    try:
        resp = tavily_client.search(query=q, max_results=mx)
        cits = []
        for r in resp.get("results", []):
            url = r.get("url", "")
            title = r.get("title", "")
            if url:
                cits.append(add_citation(context, url, title))

        context["searches"].append(
            {
                "query": q,
                "timestamp": datetime.now().isoformat(),
                "results": resp.get("results", []),
                "citation_numbers": cits,
            }
        )
        context["searches_total"] += 1

        if cits:
            for i, (r, c) in enumerate(zip(resp.get("results", [])[:5], cits[:5]), 1):
                print(f"   {i}. [{c}] {r.get('title','Untitled')} — {r.get('url','')}")

        return {
            "query": q,
            "results_count": len(resp.get("results", [])),
            "citations": cits,
        }
    except Exception as e:
        print(f"[red]Search error:[/red] {e}")
        return {"error": str(e), "query": q}


def exec_create_report(
    step: CreateReportStep, context: Dict[str, Any], config: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute report creation step."""
    # Устанавливаем флаг что отчет создан
    context["report_created"] = True

    os.makedirs(config["reports_directory"], exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(c for c in step.title if c.isalnum() or c in (" ", "-", "_"))[
        :60
    ]
    filename = f"{ts}_{safe_title}.md"
    path = os.path.join(config["reports_directory"], filename)

    content = f"# {step.title}\n\n*Created: {datetime.now():%Y-%m-%d %H:%M:%S}*\n\n"
    content += step.content
    content += format_sources_block(context)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    words = len(step.content.split())
    print("\n[bold blue]📄 Report created[/bold blue]")
    print(f"💾 File: {path}")
    print(
        f"📊 Words: {words} | Sources: {len(context['sources'])} | Confidence: {step.confidence}"
    )

    return {
        "title": step.title,
        "filepath": path,
        "word_count": words,
        "confidence": step.confidence,
    }


def exec_report_completion(
    step: ReportCompletionStep, context: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute task completion step."""
    print("\n[bold green]✅ Research completed[/bold green]")
    for s in step.completed_steps:
        print(f"   • {s}")
    return {"status": step.status}


def exec_read_local_file(
    step: ReadLocalFileStep, context: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute local file reading step."""
    print(f"\n[cyan]📖 Reading file:[/cyan] {step.file_path}")
    print(f"💭 Reason: {step.reasoning}")

    try:
        # Проверяем существование файла
        if not os.path.exists(step.file_path):
            return {
                "tool": "read_local_file",
                "status": "error",
                "error": f"File not found: {step.file_path}",
                "file_path": step.file_path,
            }

        # Читаем файл
        with open(step.file_path, "r", encoding=step.encoding) as f:
            content = f.read()

        # Получаем информацию о файле
        file_size = os.path.getsize(step.file_path)
        lines_count = len(content.splitlines())

        print(f"📄 File size: {file_size} bytes, {lines_count} lines")

        # Показываем первые несколько строк для подтверждения
        preview_lines = content.splitlines()[:3]
        if preview_lines:
            print("📝 Preview:")
            for i, line in enumerate(preview_lines, 1):
                print(f"   {i}: {line[:80]}{'...' if len(line) > 80 else ''}")

        return {
            "tool": "read_local_file",
            "status": "success",
            "file_path": step.file_path,
            "content": content,
            "file_size": file_size,
            "lines_count": lines_count,
            "encoding": step.encoding,
        }

    except UnicodeDecodeError as e:
        return {
            "tool": "read_local_file",
            "status": "error",
            "error": f"Encoding error: {e}. Try different encoding.",
            "file_path": step.file_path,
        }
    except Exception as e:
        return {
            "tool": "read_local_file",
            "status": "error",
            "error": str(e),
            "file_path": step.file_path,
        }


def exec_create_local_file(
    step: CreateLocalFileStep, context: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute local file creation step."""
    print(f"\n[cyan]📝 Creating file:[/cyan] {step.file_path}")
    print(f"💭 Reason: {step.reasoning}")

    try:
        # Проверяем существование файла
        if os.path.exists(step.file_path) and not step.overwrite:
            return {
                "tool": "create_local_file",
                "status": "error",
                "error": f"File already exists: {step.file_path}. Use overwrite=true to replace.",
                "file_path": step.file_path,
            }

        # Создаем директорию если не существует
        dir_path = os.path.dirname(step.file_path)
        if dir_path:  # Проверяем, что путь не пустой
            os.makedirs(dir_path, exist_ok=True)

        # Записываем файл
        with open(step.file_path, "w", encoding=step.encoding) as f:
            f.write(step.content)

        # Получаем информацию о созданном файле
        file_size = len(step.content.encode(step.encoding))
        lines_count = len(step.content.splitlines())

        print(f"✅ File created: {file_size} bytes, {lines_count} lines")
        print(f"📁 Path: {step.file_path}")

        # Помечаем что файл создан - для простых задач создания файла это завершение
        context["file_created"] = True
        context["created_file_path"] = step.file_path

        return {
            "tool": "create_local_file",
            "status": "success",
            "file_path": step.file_path,
            "file_size": file_size,
            "lines_count": lines_count,
            "encoding": step.encoding,
            "overwritten": os.path.exists(step.file_path) and step.overwrite,
            "task_completed": True,  # Указываем что задача может быть завершена
        }

    except Exception as e:
        return {
            "tool": "create_local_file",
            "status": "error",
            "error": str(e),
            "file_path": step.file_path,
        }


def exec_update_local_file(
    step: UpdateLocalFileStep, context: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute local file update step."""
    print(f"\n[cyan]📝 Updating file:[/cyan] {step.file_path}")
    print(f"💭 Reason: {step.reasoning}")
    print(f"🔧 Operation: {step.operation}")

    try:
        # Проверяем существование файла
        if not os.path.exists(step.file_path):
            return {
                "tool": "update_local_file",
                "status": "error",
                "error": f"File not found: {step.file_path}",
                "file_path": step.file_path,
            }

        # Читаем текущий контент
        with open(step.file_path, "r", encoding=step.encoding) as f:
            current_content = f.read()

        # Выполняем операцию обновления
        if step.operation == "append":
            new_content = current_content + step.content
        elif step.operation == "prepend":
            new_content = step.content + current_content
        elif step.operation == "replace_content":
            new_content = step.content
        elif step.operation == "replace_section":
            if not step.search_text:
                return {
                    "tool": "update_local_file",
                    "status": "error",
                    "error": "search_text is required for replace_section operation",
                    "file_path": step.file_path,
                }
            if step.search_text not in current_content:
                return {
                    "tool": "update_local_file",
                    "status": "error",
                    "error": f"Search text not found in file: {step.search_text}",
                    "file_path": step.file_path,
                }
            new_content = current_content.replace(step.search_text, step.content)
        else:
            return {
                "tool": "update_local_file",
                "status": "error",
                "error": f"Unknown operation: {step.operation}",
                "file_path": step.file_path,
            }

        # Записываем обновленный контент
        with open(step.file_path, "w", encoding=step.encoding) as f:
            f.write(new_content)

        # Получаем информацию об изменениях
        old_size = len(current_content.encode(step.encoding))
        new_size = len(new_content.encode(step.encoding))
        old_lines = len(current_content.splitlines())
        new_lines = len(new_content.splitlines())

        print(
            f"✅ File updated: {old_size}→{new_size} bytes, {old_lines}→{new_lines} lines"
        )

        return {
            "tool": "update_local_file",
            "status": "success",
            "file_path": step.file_path,
            "operation": step.operation,
            "old_size": old_size,
            "new_size": new_size,
            "old_lines": old_lines,
            "new_lines": new_lines,
            "encoding": step.encoding,
        }

    except Exception as e:
        return {
            "tool": "update_local_file",
            "status": "error",
            "error": str(e),
            "file_path": step.file_path,
        }


def exec_list_directory(
    step: ListDirectoryStep, context: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute directory listing step."""
    print(f"\n[cyan]📁 Listing directory:[/cyan] {step.directory_path}")
    print(f"💭 Reason: {step.reasoning}")

    try:
        # Проверяем существование директории
        if not os.path.exists(step.directory_path):
            return {
                "tool": "list_directory",
                "status": "error",
                "error": f"Directory not found: {step.directory_path}",
                "directory_path": step.directory_path,
            }

        if not os.path.isdir(step.directory_path):
            return {
                "tool": "list_directory",
                "status": "error",
                "error": f"Path is not a directory: {step.directory_path}",
                "directory_path": step.directory_path,
            }

        # Получаем список содержимого
        items = []

        if step.recursive:
            # Рекурсивный обход
            for root, dirs, files in os.walk(step.directory_path):
                # Вычисляем глубину
                depth = root.replace(step.directory_path, "").count(os.sep)
                if depth >= step.max_depth:
                    dirs[:] = []  # Не идем глубже
                    continue

                # Фильтруем скрытые файлы и папки
                if not step.show_hidden:
                    dirs[:] = [d for d in dirs if not d.startswith(".")]
                    files = [f for f in files if not f.startswith(".")]

                # Добавляем директории
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    rel_path = os.path.relpath(dir_path, step.directory_path)
                    items.append(
                        {
                            "name": rel_path,
                            "type": "directory",
                            "size": None,
                            "depth": depth + 1,
                        }
                    )

                # Добавляем файлы
                for file_name in files:
                    file_path = os.path.join(root, file_name)
                    rel_path = os.path.relpath(file_path, step.directory_path)
                    try:
                        file_size = os.path.getsize(file_path)
                    except OSError:
                        file_size = None

                    items.append(
                        {
                            "name": rel_path,
                            "type": "file",
                            "size": file_size,
                            "depth": depth + 1,
                        }
                    )
        else:
            # Простой список содержимого
            try:
                entries = os.listdir(step.directory_path)
            except PermissionError:
                return {
                    "tool": "list_directory",
                    "status": "error",
                    "error": f"Permission denied: {step.directory_path}",
                    "directory_path": step.directory_path,
                }

            # Фильтруем скрытые файлы
            if not step.show_hidden:
                entries = [e for e in entries if not e.startswith(".")]

            for entry in sorted(entries):
                entry_path = os.path.join(step.directory_path, entry)
                try:
                    if os.path.isdir(entry_path):
                        items.append(
                            {
                                "name": entry,
                                "type": "directory",
                                "size": None,
                                "depth": 1,
                            }
                        )
                    else:
                        file_size = os.path.getsize(entry_path)
                        items.append(
                            {
                                "name": entry,
                                "type": "file",
                                "size": file_size,
                                "depth": 1,
                            }
                        )
                except OSError:
                    # Файл может быть недоступен
                    items.append(
                        {
                            "name": entry,
                            "type": "unknown",
                            "size": None,
                            "depth": 1,
                        }
                    )

        # Сортируем: сначала директории, потом файлы
        items.sort(key=lambda x: (x["type"] != "directory", x["name"]))

        # Выводим результат
        dirs_count = sum(1 for item in items if item["type"] == "directory")
        files_count = sum(1 for item in items if item["type"] == "file")

        print(f"📊 Found: {dirs_count} directories, {files_count} files")

        # Показываем элементы
        preview_items = items[:15] if not step.tree_view else items
        if preview_items:
            if step.tree_view and step.recursive:
                print("📝 Tree structure:")
                _print_tree_structure(preview_items, step.directory_path)
            else:
                print("📝 Contents:")
                for item in preview_items:
                    if step.tree_view:
                        # Простое древовидное отображение для одного уровня
                        prefix = "├── " if item != preview_items[-1] else "└── "
                    else:
                        prefix = "   "

                    indent = (
                        "  " * (item["depth"] - 1)
                        if step.recursive and not step.tree_view
                        else ""
                    )
                    if item["type"] == "directory":
                        print(f"{prefix}{indent}📁 {item['name']}/")
                    elif item["type"] == "file":
                        size_str = (
                            f" ({item['size']} bytes)"
                            if item["size"] is not None
                            else ""
                        )
                        print(f"{prefix}{indent}📄 {item['name']}{size_str}")
                    else:
                        print(f"{prefix}{indent}❓ {item['name']}")

        if len(items) > 15 and not step.tree_view:
            print(f"   ... and {len(items) - 15} more items")

        return {
            "tool": "list_directory",
            "status": "success",
            "directory_path": step.directory_path,
            "items": items,
            "total_items": len(items),
            "directories_count": dirs_count,
            "files_count": files_count,
            "show_hidden": step.show_hidden,
            "recursive": step.recursive,
        }

    except Exception as e:
        return {
            "tool": "list_directory",
            "status": "error",
            "error": str(e),
            "directory_path": step.directory_path,
        }


def exec_create_directory(
    step: CreateDirectoryStep, context: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute directory creation step with user confirmation."""
    print(f"\n[cyan]📁 Creating directory:[/cyan] {step.directory_path}")
    print(f"💭 Reason: {step.reasoning}")
    print(f"📝 Description: {step.description}")
    print(f"🔧 Create parents: {step.create_parents}")

    try:
        # Проверяем, существует ли уже директория
        if os.path.exists(step.directory_path):
            if os.path.isdir(step.directory_path):
                return {
                    "tool": "create_directory",
                    "status": "error",
                    "error": f"Directory already exists: {step.directory_path}",
                    "directory_path": step.directory_path,
                }
            else:
                return {
                    "tool": "create_directory",
                    "status": "error",
                    "error": f"Path exists but is not a directory: {step.directory_path}",
                    "directory_path": step.directory_path,
                }

        # Запрашиваем подтверждение у пользователя
        print("\n[bold yellow]🤔 DIRECTORY CREATION CONFIRMATION[/bold yellow]")
        print(f"📁 Path: {step.directory_path}")
        print(f"📝 Purpose: {step.description}")

        if step.create_parents:
            parent_dir = os.path.dirname(step.directory_path)
            if parent_dir and not os.path.exists(parent_dir):
                print(f"⚠️  Parent directories will be created: {parent_dir}")

        # Check if we're in API mode (force mode)
        force_mode = context.get("api_mode", False)

        if force_mode:
            # In API mode, auto-create directory
            print("\n[green]🔄 API Mode: Auto-creating directory[/green]")
            os.makedirs(step.directory_path, exist_ok=True)
        else:
            # Interactive mode - ask user
            print(
                "\n[bold cyan]Do you want to create this directory? (y/n):[/bold cyan]"
            )

            try:
                user_response = input(">>> ").strip().lower()
                if user_response not in ["y", "yes", "да", "д"]:
                    return {
                        "tool": "create_directory",
                        "status": "cancelled",
                        "message": "Directory creation cancelled by user",
                        "directory_path": step.directory_path,
                    }

                # Создаем директорию
                os.makedirs(step.directory_path, exist_ok=False)
            except (KeyboardInterrupt, EOFError):
                return {
                    "tool": "create_directory",
                    "status": "cancelled",
                    "message": "Directory creation cancelled by user (interrupted)",
                    "directory_path": step.directory_path,
                }

        print(f"✅ Directory created successfully: {step.directory_path}")

        # Проверяем, что директория действительно создана
        if os.path.exists(step.directory_path) and os.path.isdir(step.directory_path):
            return {
                "tool": "create_directory",
                "status": "success",
                "directory_path": step.directory_path,
                "description": step.description,
                "created_parents": step.create_parents,
                "message": f"Directory '{step.directory_path}' created successfully",
            }
        else:
            return {
                "tool": "create_directory",
                "status": "error",
                "error": "Directory creation appeared to succeed but directory not found",
                "directory_path": step.directory_path,
            }

    except PermissionError:
        return {
            "tool": "create_directory",
            "status": "error",
            "error": f"Permission denied: cannot create directory {step.directory_path}",
            "directory_path": step.directory_path,
        }
    except FileExistsError:
        return {
            "tool": "create_directory",
            "status": "error",
            "error": f"Directory already exists: {step.directory_path}",
            "directory_path": step.directory_path,
        }
    except Exception as e:
        return {
            "tool": "create_directory",
            "status": "error",
            "error": str(e),
            "directory_path": step.directory_path,
        }


def exec_simple_answer(
    step: SimpleAnswerStep, context: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute simple answer step - provide direct response"""
    print("\n[green]💬 Simple Answer:[/green]")
    print(f"💭 Reason: {step.reasoning}")

    # Отображаем основной ответ
    print("\n[bold cyan]📝 Answer:[/bold cyan]")
    print(f"{step.answer}")

    # Отображаем дополнительную информацию если есть
    if step.additional_info:
        print("\n[yellow]ℹ️  Additional Info:[/yellow]")
        print(f"{step.additional_info}")

    # Помечаем что простой ответ дан - задача завершена
    context["simple_answer_given"] = True

    return {
        "tool": "simple_answer",
        "status": "success",
        "answer": step.answer,
        "additional_info": step.additional_info,
        "reasoning": step.reasoning,
        "task_completed": True,  # Указываем что задача завершена
    }


# =============================================================================
# EXECUTOR REGISTRY
# =============================================================================


def get_executors() -> Dict[str, callable]:
    """Get all function executors."""
    return {
        "clarification": exec_clarification,
        "web_search": exec_web_search,
        "create_report": exec_create_report,
        "report_completion": exec_report_completion,
        "read_local_file": exec_read_local_file,
        "create_local_file": exec_create_local_file,
        "update_local_file": exec_update_local_file,
        "list_directory": exec_list_directory,
        "create_directory": exec_create_directory,
        "simple_answer": exec_simple_answer,
    }
