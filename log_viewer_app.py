#!/usr/bin/env python3
"""
FastAPI сервер для анализа логов и отчетов Neural Deep Agent системы.

Этот сервер предоставляет веб-интерфейс для просмотра:
- Логов выполнения агентов
- Отчетов исследований
- Dashboard с общей статистикой
"""

import json
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import markdown
from pydantic import BaseModel

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создание приложения FastAPI
app = FastAPI(
    title="SGR Deep Research Demo",
    description="Live capabilities showcase for Schema-Guided Reasoning framework with multi-model analysis",
    version="1.0.0"
)

# Пути к директориям
BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
SERVICES_DIR = BASE_DIR / "services"
LOGS_DIR = SERVICES_DIR / "logs"
REPORTS_DIR = SERVICES_DIR / "reports"

# Настройка шаблонов
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Модели данных
@dataclass
class LogFileInfo:
    """Информация о файле лога агента"""
    filename: str
    agent_id: str
    task: str
    iterations: int
    modified: datetime
    size: int
    model_name: str = "unknown"

@dataclass
class ReportInfo:
    """Информация о файле отчета"""
    filename: str
    title: str
    description: str | None
    created: datetime
    size: int

class LogAnalytics(BaseModel):
    """Аналитика по логу"""
    total_steps: int
    reasoning_steps: int
    tool_executions: int
    search_operations: int
    total_duration: Optional[str] = None
    success_rate: float
    most_used_tools: List[Dict[str, Any]]
    model_name: Optional[str] = None

class ReportAnalytics(BaseModel):
    """Аналитика по отчету"""
    word_count: int
    sections: List[str]
    reading_time_minutes: int
    key_topics: List[str]


def parse_log_filename(filename: str) -> tuple[str, str, str]:
    """
    Парсит имя файла лога для извлечения информации.
    Формат: YYYYMMDD-HHMMSS-sgr_agent_UUID-log.json
    """
    try:
        # Удаляем расширение
        base_name = filename.replace('-log.json', '')
        parts = base_name.split('-')
        
        if len(parts) >= 4:
            date_str = parts[0]
            time_str = parts[1]
            agent_id = '-'.join(parts[3:])  # UUID может содержать дефисы
            
            # Форматируем дату и время
            datetime_str = f"{date_str}-{time_str}"
            return datetime_str, agent_id, agent_id
        
        return filename, filename, "Unknown agent"
    except Exception as e:
        logger.warning(f"Не удалось распарсить имя файла {filename}: {e}")
        return filename, filename, "Unknown agent"


def get_log_files() -> List[LogFileInfo]:
    """Получает список всех файлов логов"""
    log_files = []
    
    if not LOGS_DIR.exists():
        return log_files
    
    for log_file in LOGS_DIR.glob("*.json"):
        try:
            datetime_str, agent_id, _ = parse_log_filename(log_file.name)
            
            # Читаем базовую информацию из файла
            with open(log_file, 'r', encoding='utf-8') as f:
                log_data = json.load(f)
            
            task = log_data.get('task', 'Unknown task')
            iterations = len(log_data.get('log', []))
            
            # Извлекаем информацию о модели, если доступна
            model_info = log_data.get('model_info', {})
            model_name = model_info.get('model', 'gpt-4o-mini')
            
            log_info = LogFileInfo(
                filename=log_file.name,
                agent_id=agent_id,
                task=task,
                iterations=iterations,
                modified=datetime.fromtimestamp(log_file.stat().st_mtime),
                size=log_file.stat().st_size,
                model_name=model_name
            )
            log_files.append(log_info)
            
        except Exception as e:
            logger.error(f"Ошибка при обработке файла {log_file}: {e}")
    
    # Сортируем по времени модификации (новые сначала)
    log_files.sort(key=lambda x: x.modified, reverse=True)
    return log_files


def get_report_files() -> List[ReportInfo]:
    """Получает список всех файлов отчетов"""
    report_files = []
    
    if not REPORTS_DIR.exists():
        return report_files
    
    for report_file in REPORTS_DIR.glob("*.md"):
        try:
            # Читаем содержимое для получения заголовка и описания
            with open(report_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            lines = content.split('\n')
            title = report_file.stem
            description = None
            
            # Ищем заголовок и описание
            for i, line in enumerate(lines):
                if line.startswith('# '):
                    title = line[2:].strip()
                    # Пытаемся найти описание в следующих нескольких строках
                    for j in range(i + 1, min(i + 10, len(lines))):
                        next_line = lines[j].strip()
                        if next_line and not next_line.startswith('*') and not next_line.startswith('#'):
                            # Берем первое содержательное предложение как описание
                            if len(next_line) > 20:  # Минимальная длина для описания
                                description = next_line[:200] + ("..." if len(next_line) > 200 else "")
                                break
                    break
            
            report_info = ReportInfo(
                filename=report_file.name,
                title=title,
                description=description,
                created=datetime.fromtimestamp(report_file.stat().st_ctime),
                size=report_file.stat().st_size
            )
            report_files.append(report_info)
            
        except Exception as e:
            logger.error(f"Ошибка при обработке отчета {report_file}: {e}")
    
    # Сортируем по времени создания (новые сначала)
    report_files.sort(key=lambda x: x.created, reverse=True)
    return report_files


def analyze_log(log_data: Dict[str, Any]) -> LogAnalytics:
    """Анализирует лог файл и возвращает аналитику"""
    log_entries = log_data.get('log', [])
    
    total_steps = len(log_entries)
    reasoning_steps = sum(1 for entry in log_entries if entry.get('step_type') == 'reasoning')
    tool_executions = sum(1 for entry in log_entries if entry.get('step_type') == 'tool_execution')
    
    # Подсчитываем поисковые операции
    search_operations = 0
    tool_usage = {}
    
    for entry in log_entries:
        if entry.get('step_type') == 'tool_execution':
            tool_name = entry.get('tool_name', 'unknown')
            tool_usage[tool_name] = tool_usage.get(tool_name, 0) + 1
            
            if 'search' in tool_name.lower() or 'tavily' in tool_name.lower():
                search_operations += 1
    
    # Топ используемых инструментов
    most_used_tools = [
        {"name": tool, "count": count} 
        for tool, count in sorted(tool_usage.items(), key=lambda x: x[1], reverse=True)[:5]
    ]
    
    # Приблизительная оценка успешности
    task_completed = log_data.get('context', {}).get('state') == 'completed'
    success_rate = 1.0 if task_completed else 0.7  # Примерная оценка
    
    # Извлекаем информацию о модели
    model_info = log_data.get('model_info', {})
    model_name = model_info.get('model', 'unknown')
    
    return LogAnalytics(
        total_steps=total_steps,
        reasoning_steps=reasoning_steps,
        tool_executions=tool_executions,
        search_operations=search_operations,
        success_rate=success_rate,
        most_used_tools=most_used_tools,
        model_name=model_name  # Добавляем информацию о модели
    )


def analyze_report(content: str) -> ReportAnalytics:
    """Анализирует отчет и возвращает аналитику"""
    # Подсчет слов
    words = len(content.split())
    
    # Извлечение заголовков
    sections = []
    for line in content.split('\n'):
        if line.startswith('#'):
            sections.append(line.strip())
    
    # Примерное время чтения (200 слов в минуту)
    reading_time = max(1, words // 200)
    
    # Простое извлечение ключевых тем (можно улучшить с NLP)
    key_topics = []
    common_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those', 'a', 'an'}
    
    words_freq = {}
    for word in content.lower().split():
        clean_word = ''.join(c for c in word if c.isalpha())
        if len(clean_word) > 4 and clean_word not in common_words:
            words_freq[clean_word] = words_freq.get(clean_word, 0) + 1
    
    key_topics = [word for word, freq in sorted(words_freq.items(), key=lambda x: x[1], reverse=True)[:10]]
    
    return ReportAnalytics(
        word_count=words,
        sections=sections,
        reading_time_minutes=reading_time,
        key_topics=key_topics
    )


# Маршруты API
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Главная страница с dashboard"""
    logs = get_log_files()
    reports = get_report_files()
    
    # Берем только последние 5 для превью
    recent_logs = logs[:5]
    recent_reports = reports[:5]
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "logs": recent_logs,
        "reports": recent_reports
    })


@app.get("/logs", response_class=HTMLResponse)
async def logs_list(request: Request):
    """Страница со списком всех логов"""
    logs = get_log_files()
    return templates.TemplateResponse("logs_list.html", {
        "request": request,
        "logs": logs
    })


@app.get("/reports", response_class=HTMLResponse)
async def reports_list(request: Request):
    """Страница со списком всех отчетов"""
    reports = get_report_files()
    return templates.TemplateResponse("reports_list.html", {
        "request": request,
        "reports": reports
    })


@app.get("/log/{filename}", response_class=HTMLResponse)
async def view_log(request: Request, filename: str):
    """Просмотр конкретного лога"""
    log_file = LOGS_DIR / filename
    
    if not log_file.exists():
        raise HTTPException(status_code=404, detail="Лог файл не найден")
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            log_data = json.load(f)
        
        return templates.TemplateResponse("log_view.html", {
            "request": request,
            "filename": filename,
            "log_data": log_data
        })
    except Exception as e:
        logger.error(f"Ошибка при чтении лога {filename}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при чтении файла лога")


@app.get("/report/{filename}", response_class=HTMLResponse)
async def view_report(request: Request, filename: str):
    """Просмотр конкретного отчета"""
    report_file = REPORTS_DIR / filename
    
    if not report_file.exists():
        raise HTTPException(status_code=404, detail="Отчет не найден")
    
    try:
        with open(report_file, 'r', encoding='utf-8') as f:
            raw_content = f.read()
        
        # Конвертируем Markdown в HTML
        html_content = markdown.markdown(
            raw_content,
            extensions=['tables', 'codehilite', 'toc']
        )
        
        return templates.TemplateResponse("report_view.html", {
            "request": request,
            "filename": filename,
            "content": html_content,
            "raw_content": raw_content
        })
    except Exception as e:
        logger.error(f"Ошибка при чтении отчета {filename}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при чтении файла отчета")


# API эндпоинты для JSON данных
@app.get("/api/logs")
async def api_logs():
    """API для получения списка логов"""
    logs = get_log_files()
    return {"logs": [log.__dict__ for log in logs]}


@app.get("/api/reports")
async def api_reports():
    """API для получения списка отчетов"""
    reports = get_report_files()
    return {"reports": [report.__dict__ for report in reports]}


@app.get("/api/log/{filename}/trace")
async def api_log_trace(filename: str):
    """API для получения данных трейса лога"""
    log_file = LOGS_DIR / filename
    
    if not log_file.exists():
        raise HTTPException(status_code=404, detail="Лог файл не найден")
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            log_data = json.load(f)
        
        # Извлекаем информацию о модели из первого openai_request шага
        model_info = None
        model_name = "unknown"
        
        for step in log_data.get("log", []):
            if step.get("step_type") == "openai_request" and step.get("model_info"):
                model_info = step["model_info"]
                model_name = model_info.get("model", "unknown")
                break
        
        trace_data = {
            "task": f"Agent ID: {log_data.get('id', 'Unknown')[:20]}...",
            "total_steps": len(log_data.get("log", [])),
            "dataset": "SealQA",
            "model": model_name,
            "model_info": model_info,
            "state": log_data.get("context", {}).get("state", "unknown"),
            "github_url": "https://github.com/vakovalskii/sgr-deep-research",
            "trace": []
        }
        
        # Формируем данные для каждого шага
        for step in log_data.get("log", []):
            step_type = step.get("step_type", "Unknown")
            tool_name = step.get("tool_name", "")
            
            # Формируем краткое описание для трейса
            if step_type == "tool_execution" and tool_name:
                # Убираем 'tool' из названия и делаем красивое имя
                clean_name = tool_name.replace("tool", "").replace("_", " ")
                summary = clean_name.title()
            elif step_type == "openai_request":
                model = step.get("model_info", {}).get("model", "AI")
                summary = f"AI Request ({model})"
            else:
                summary = step_type.replace("_", " ").title()
            
            trace_step = {
                "step_number": step.get("step_number"),
                "step_type": step_type,
                "timestamp": step.get("timestamp"),
                "summary": summary,
                "tool_name": tool_name,
                "model_info": step.get("model_info") if step_type == "openai_request" else None
            }
            trace_data["trace"].append(trace_step)
        
        return trace_data
        
    except Exception as e:
        logger.error(f"Ошибка при чтении трейса лога {filename}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при чтении файла лога")


@app.get("/api/log/{filename}/analytics")
async def api_log_analytics(filename: str):
    """API для получения аналитики по логу"""
    log_file = LOGS_DIR / filename
    
    if not log_file.exists():
        raise HTTPException(status_code=404, detail="Лог файл не найден")
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            log_data = json.load(f)
        
        analytics = analyze_log(log_data)
        return analytics.dict()
    except Exception as e:
        logger.error(f"Ошибка при анализе лога {filename}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при анализе лога")


@app.get("/api/report/{filename}/analytics")
async def api_report_analytics(filename: str):
    """API для получения аналитики по отчету"""
    report_file = REPORTS_DIR / filename
    
    if not report_file.exists():
        raise HTTPException(status_code=404, detail="Отчет не найден")
    
    try:
        with open(report_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        analytics = analyze_report(content)
        return analytics.dict()
    except Exception as e:
        logger.error(f"Ошибка при анализе отчета {filename}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при анализе отчета")


@app.get("/api/log/{filename}/trace")
async def api_log_trace(filename: str):
    """API для получения структурированного трейса шагов агента"""
    log_file = LOGS_DIR / filename
    
    if not log_file.exists():
        raise HTTPException(status_code=404, detail="Лог файл не найден")
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            log_data = json.load(f)
        
        trace_steps = []
        log_entries = log_data.get('log', [])
        
        for step in log_entries:
            step_info = {
                "step_number": step.get('step_number', 0),
                "step_type": step.get('step_type', 'unknown'),
                "timestamp": step.get('timestamp', ''),
                "title": f"Step {step.get('step_number', 0)}: {step.get('step_type', '').title()}",
                "status": "completed",  # Все шаги в логе уже выполнены
                "duration": None
            }
            
            # Добавляем специфичную для типа шага информацию
            if step.get('step_type') == 'reasoning':
                reasoning = step.get('agent_reasoning', {})
                step_info.update({
                    "summary": reasoning.get('question_analysis', 'Reasoning step'),
                    "details": {
                        "reasoning_steps": reasoning.get('reasoning_steps', []),
                        "current_situation": reasoning.get('current_situation', ''),
                        "enough_data": reasoning.get('enough_data', False),
                        "task_completed": reasoning.get('task_completed', False)
                    }
                })
            elif step.get('step_type') == 'tool_execution':
                tool_name = step.get('tool_name', 'Unknown tool')
                step_info.update({
                    "summary": f"Executed {tool_name}",
                    "tool_name": tool_name,
                    "details": {
                        "context": step.get('agent_tool_context', {}),
                        "result_length": len(str(step.get('agent_tool_execution_result', '')))
                    }
                })
            else:
                step_info.update({
                    "summary": f"{step.get('step_type', 'Unknown')} step",
                    "details": {}
                })
            
            trace_steps.append(step_info)
        
        # Извлекаем информацию о модели из лога
        model_info = log_data.get('model_info', {})
        model_name = model_info.get('model', 'gpt-4o-mini')  # Fallback к gpt-4o-mini
        
        return {
            "task": log_data.get('task', 'Unknown task'),
            "agent_id": log_data.get('id', 'Unknown agent'),
            "total_steps": len(trace_steps),
            "state": log_data.get('context', {}).get('state', 'unknown'),
            "model": model_name,  # Используем модель из лога
            "model_info": model_info,  # Полная информация о модели
            "dataset": "SealQA",  # Датасет для тестирования и исследований
            "github_url": "https://github.com/vakovalskii/sgr-deep-research",
            "trace": trace_steps
        }
        
    except Exception as e:
        logger.error(f"Ошибка при создании трейса для лога {filename}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при создании трейса лога")


@app.get("/health")
async def health_check():
    """Проверка состояния сервиса"""
    return {
        "status": "healthy",
        "logs_directory": str(LOGS_DIR),
        "reports_directory": str(REPORTS_DIR),
        "logs_count": len(list(LOGS_DIR.glob("*.json")) if LOGS_DIR.exists() else []),
        "reports_count": len(list(REPORTS_DIR.glob("*.md")) if REPORTS_DIR.exists() else [])
    }


def main():
    """Запуск сервера"""
    print("🚀 Запуск SGR Deep Research Log Viewer...")
    print(f"📁 Директория логов: {LOGS_DIR}")
    print(f"📁 Директория отчетов: {REPORTS_DIR}")
    print(f"🌐 Веб-интерфейс будет доступен по адресу: http://localhost:8098")
    
    # Создаем директории если их нет
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Запускаем сервер
    uvicorn.run(
        "log_viewer_app:app",
        host="0.0.0.0",
        port=8098,
        reload=True,
        log_level="info"
    )


if __name__ == "__main__":
    main()
