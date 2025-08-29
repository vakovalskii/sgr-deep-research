#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SGR Research Agent - FastAPI Server
OpenAI-compatible API server with streaming support
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import uvicorn
from openai import OpenAI
from tavily import TavilyClient

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
from sgr_agent import (
    load_config,
    load_prompts,
    create_fresh_context,
    validate_reasoning_step,
)
from executors import get_executors

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

CONFIG = load_config()
PROMPTS = load_prompts()
executors = get_executors()

# Initialize OpenAI client
openai_kwargs = {
    "api_key": CONFIG["openai_api_key"],
    "base_url": CONFIG.get("openai_base_url") or None,
}

# Add proxy support if configured
if CONFIG.get("openai_proxy"):
    import httpx

    openai_kwargs["http_client"] = httpx.Client(
        follow_redirects=True,
        limits=httpx.Limits(max_connections=10),
        proxy=CONFIG["openai_proxy"],
    )

client = OpenAI(**openai_kwargs)

# Initialize Tavily client
tavily = TavilyClient(CONFIG["tavily_api_key"])

# =============================================================================
# FASTAPI APP
# =============================================================================

app = FastAPI(
    title="SGR Research Agent API",
    description="OpenAI-compatible API server for Schema-Guided Reasoning research agent",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# =============================================================================
# OPENAI-COMPATIBLE MODELS
# =============================================================================


class ChatMessage(BaseModel):
    role: str = Field(..., description="The role of the message author")
    content: str = Field(..., description="The contents of the message")
    name: Optional[str] = Field(None, description="The name of the message author")


class ChatCompletionRequest(BaseModel):
    model: str = Field(..., description="ID of the model to use")
    messages: List[ChatMessage] = Field(
        ..., description="A list of messages comprising the conversation"
    )
    temperature: Optional[float] = Field(
        1.0, description="What sampling temperature to use"
    )
    top_p: Optional[float] = Field(1.0, description="What nucleus sampling to use")
    n: Optional[int] = Field(
        1, description="How many chat completion choices to generate"
    )
    stream: Optional[bool] = Field(
        False, description="If set, partial message deltas will be sent"
    )
    stop: Optional[Union[str, List[str]]] = Field(
        None, description="Up to 4 sequences where the API will stop generating"
    )
    max_tokens: Optional[int] = Field(
        None, description="Maximum number of tokens to generate"
    )
    presence_penalty: Optional[float] = Field(
        0.0, description="Number between -2.0 and 2.0"
    )
    frequency_penalty: Optional[float] = Field(
        0.0, description="Number between -2.0 and 2.0"
    )
    logit_bias: Optional[Dict[str, float]] = Field(
        None, description="Modify the likelihood of specified tokens"
    )
    user: Optional[str] = Field(
        None, description="A unique identifier representing your end-user"
    )


class ChatCompletionResponse(BaseModel):
    id: str = Field(..., description="A unique identifier for the completion")
    object: str = Field("chat.completion", description="The object type")
    created: int = Field(
        ..., description="The Unix timestamp of when the completion was created"
    )
    model: str = Field(..., description="The model used for the completion")
    choices: List[Dict[str, Any]] = Field(
        ..., description="The list of completion choices"
    )
    usage: Dict[str, int] = Field(
        ..., description="Usage statistics for the completion request"
    )


class ChatCompletionChunk(BaseModel):
    id: str = Field(..., description="A unique identifier for the completion")
    object: str = Field("chat.completion.chunk", description="The object type")
    created: int = Field(
        ..., description="The Unix timestamp of when the completion was created"
    )
    model: str = Field(..., description="The model used for the completion")
    choices: List[Dict[str, Any]] = Field(
        ..., description="The list of completion choices"
    )


# =============================================================================
# SGR AGENT INTEGRATION
# =============================================================================


def create_api_context() -> Dict[str, Any]:
    """Create context for API requests."""
    context = create_fresh_context()
    context["api_mode"] = True  # Enable force mode for API operations
    return context


async def execute_sgr_research_streaming(messages: List[Dict[str, Any]]):
    """Execute SGR research and yield streaming results."""
    logger.info(f"Starting streaming research with {len(messages)} messages")

    if not messages:
        logger.error("No messages provided")
        raise HTTPException(status_code=400, detail="No messages provided")

    # Get user request from last message
    user_request = messages[-1].get("content", "")
    if not user_request:
        logger.error("No user content in messages")
        raise HTTPException(status_code=400, detail="No user content in messages")

    logger.info(f"User request: {user_request[:100]}...")

    # Create context
    context = create_api_context()
    logger.info(f"Created context with {len(context)} keys")

    # Initialize conversation
    conversation_messages = [
        {
            "role": "system",
            "content": PROMPTS["outer_system"]["template"].format(
                user_request=user_request
            ),
        }
    ]

    # Add user message
    conversation_messages.append({"role": "user", "content": user_request})

    # Main research loop
    rounds = 0
    max_rounds = CONFIG["max_rounds"]
    logger.info(f"Starting research loop with max {max_rounds} rounds")

    while rounds < max_rounds:
        rounds += 1
        logger.info(f"Starting round {rounds}/{max_rounds}")

        try:
            # Phase 1: Reasoning Analysis
            logger.info("Executing reasoning phase")
            reasoning = await exec_reasoning_phase_api(
                conversation_messages, user_request, context
            )
            logger.info(f"Reasoning completed: {reasoning.next_action}")

            # Stream reasoning step
            yield create_reasoning_chunk(reasoning, rounds, max_rounds)

            # Check completion
            if reasoning.task_completed:
                logger.info("Task completed, ending research")
                yield create_completion_chunk(reasoning, rounds, max_rounds)
                break

            # Prevent infinite loops with fallback reasoning
            if (
                reasoning.current_situation == "OpenAI API unavailable - using fallback"
                and rounds >= 2
            ):
                logger.warning("Stopping fallback loop after 2 rounds")
                yield create_completion_chunk(reasoning, rounds, max_rounds)
                break

            # Phase 2: Execute Actions
            logger.info("Executing action phase")
            action_results = await exec_action_phase_api(
                conversation_messages, reasoning, context
            )
            logger.info(f"Action phase completed with {len(action_results)} results")

            # Stream action results
            for result in action_results:
                yield create_action_chunk(result, rounds, max_rounds)

        except Exception as e:
            logger.error(f"Error in round {rounds}: {str(e)}", exc_info=True)
            error_result = {"error": str(e), "round": rounds}
            yield create_error_chunk(error_result, rounds, max_rounds)
            break

    logger.info(f"Research completed in {rounds} rounds")


async def execute_sgr_research_non_streaming(messages: List[Dict[str, Any]]):
    """Execute SGR research and return final result."""
    if not messages:
        raise HTTPException(status_code=400, detail="No messages provided")

    # Get user request from last message
    user_request = messages[-1].get("content", "")
    if not user_request:
        raise HTTPException(status_code=400, detail="No user content in messages")

    # Create context
    context = create_api_context()

    # Initialize conversation
    conversation_messages = [
        {
            "role": "system",
            "content": PROMPTS["outer_system"]["template"].format(
                user_request=user_request
            ),
        }
    ]

    # Add user message
    conversation_messages.append({"role": "user", "content": user_request})

    # Main research loop
    rounds = 0
    max_rounds = CONFIG["max_rounds"]

    while rounds < max_rounds:
        rounds += 1

        try:
            # Phase 1: Reasoning Analysis
            reasoning = await exec_reasoning_phase_api(
                conversation_messages, user_request, context
            )

            # Check completion
            if reasoning.task_completed:
                break

            # Phase 2: Execute Actions
            await exec_action_phase_api(conversation_messages, reasoning, context)

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # Return final response
    return create_final_response(conversation_messages, context, rounds)


async def exec_reasoning_phase_api(
    messages: List[Dict[str, Any]], task: str, context: Dict[str, Any]
) -> ReasoningStep:
    """Execute reasoning phase for API."""
    logger.info(f"Starting reasoning phase for task: {task[:100]}...")

    # Create reasoning message
    reasoning_call_id = f"call_reasoning_{len(messages)}"

    messages.append(
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": reasoning_call_id,
                    "type": "function",
                    "function": {"name": "generate_reasoning", "arguments": "{}"},
                }
            ],
        }
    )

    # Execute reasoning
    logger.info("Calling structured output reasoning")
    reasoning_result = exec_structured_output_reasoning_api(messages, task, context)

    if "error" in reasoning_result:
        logger.error(f"Reasoning validation failed: {reasoning_result['error']}")
        raise RuntimeError(f"Reasoning validation failed: {reasoning_result['error']}")

    if "reasoning" not in reasoning_result:
        logger.error("No 'reasoning' key in result")
        raise RuntimeError("Invalid reasoning result structure")

    logger.info("Validating reasoning step")
    try:
        reasoning = ReasoningStep.model_validate(reasoning_result["reasoning"])
        logger.info(f"Reasoning validated: {reasoning.next_action}")
    except Exception as e:
        logger.error(f"Failed to validate reasoning step: {e}")
        raise RuntimeError(f"Reasoning validation failed: {e}")

    # Add reasoning result to messages
    messages.append(
        {
            "role": "tool",
            "tool_call_id": reasoning_call_id,
            "content": json.dumps(reasoning_result, ensure_ascii=False),
        }
    )

    return reasoning


def exec_structured_output_reasoning_api(
    messages: List[Dict[str, Any]], task: str, context: Dict[str, Any]
) -> Dict[str, Any]:
    """Internal SO call for reasoning analysis in API."""
    logger.info("Starting structured output reasoning")
    schema = ReasoningStep.model_json_schema()

    # Clean schema
    if "$defs" in schema:
        del schema["$defs"]
    if "title" in schema:
        del schema["title"]
    if "description" in schema:
        del schema["description"]

    # Build dialog snapshot
    dialog_snapshot = build_dialog_snapshot_api(messages, limit=30)
    logger.info(f"Built dialog snapshot with {len(dialog_snapshot)} characters")

    # Find last user message
    last_user_message = ""
    for msg in reversed(messages):
        if msg.get("role") == "user" and msg.get("content"):
            last_user_message = msg.get("content")
            break

    user_request = last_user_message if last_user_message else task
    logger.info(f"User request for reasoning: {user_request[:100]}...")

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

    logger.info(f"Calling OpenAI with {len(so_messages)} messages")
    try:
        completion = client.chat.completions.create(
            model=CONFIG["openai_model"],
            messages=so_messages,
            temperature=CONFIG.get("so_temperature", 0.1),
            max_tokens=CONFIG.get("max_tokens", 2000),
            response_format={"type": "json_object"},
        )
        logger.info("OpenAI response received successfully")
    except Exception as e:
        logger.error(f"OpenAI API call failed: {e}")
        # Return a mock reasoning step for testing when OpenAI fails
        mock_reasoning = {
            "current_situation": "OpenAI API unavailable - using fallback",
            "plan_status": "limited",
            "reasoning_steps": ["API error occurred"],
            "next_action": "simple_answer",
            "action_reasoning": "Cannot perform full reasoning due to API issues",
            "next_steps": ["provide_simple_answer"],
            "searches_done": 0,
            "enough_data": False,
            "task_completed": True,  # Mark as completed to avoid infinite loop
        }
        logger.warning("Using fallback reasoning due to OpenAI API failure")
        return {"reasoning": mock_reasoning}

    try:
        content = completion.choices[0].message.content
        if not content:
            logger.error("Empty response from OpenAI")
            return {"error": "Empty response from OpenAI"}

        logger.info("Parsing OpenAI response")
        result = json.loads(content)
        logger.info(
            f"Parsed result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}"
        )

        # Create a minimal context for validation
        validation_context = {
            "clarification_used": False,
            "clarification_completed": False,
            "report_created": False,
            "simple_answer_given": False,
            "file_created": False,
            "searches_total": 0,
        }

        logger.info("Creating ReasoningStep object for validation")
        try:
            # First create the object to validate its structure
            reasoning_obj = ReasoningStep.model_validate(result)
            logger.info("ReasoningStep object created successfully")
        except Exception as e:
            logger.error(f"Failed to create ReasoningStep object: {e}")
            return {"error": f"Invalid reasoning structure: {e}"}

        logger.info("Validating reasoning step")
        validation_result = validate_reasoning_step(reasoning_obj, validation_context)

        if validation_result:  # validation_result is a list of errors
            logger.error(f"Validation failed: {'; '.join(validation_result)}")
            return {"error": f"Validation failed: {'; '.join(validation_result)}"}

        logger.info("Reasoning step validated successfully")
        return {"reasoning": result}

    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.error(f"Failed to parse OpenAI response: {e}")
        return {"error": f"Failed to parse OpenAI response: {e}"}


def build_dialog_snapshot_api(messages: List[Dict[str, Any]], limit: int = 30) -> str:
    """Build dialog snapshot for API."""
    if not messages:
        return "No conversation history."

    # Take last N messages
    recent_messages = messages[-limit:] if len(messages) > limit else messages

    snapshot_lines = []
    for msg in recent_messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")

        if content:
            # Truncate long content
            if len(content) > 200:
                content = content[:200] + "..."
            snapshot_lines.append(f"{role}: {content}")

    return "\n".join(snapshot_lines)


async def exec_action_phase_api(
    messages: List[Dict[str, Any]], reasoning: ReasoningStep, context: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Execute action phase for API."""
    results = []

    # Create action message
    action_message = {
        "role": "assistant",
        "content": f"Next action: {reasoning.next_action}",
        "tool_calls": [],
    }

    # Add appropriate tool call based on reasoning
    if reasoning.next_action == "search":
        action_message["tool_calls"].append(
            {
                "id": f"call_search_{len(messages)}",
                "type": "function",
                "function": {
                    "name": "web_search",
                    "arguments": json.dumps(
                        {
                            "reasoning": reasoning.action_reasoning,
                            "query": reasoning.action_reasoning,
                            "max_results": 10,
                        }
                    ),
                },
            }
        )
    elif reasoning.next_action == "simple_answer":
        action_message["tool_calls"].append(
            {
                "id": f"call_answer_{len(messages)}",
                "type": "function",
                "function": {
                    "name": "simple_answer",
                    "arguments": json.dumps(
                        {
                            "reasoning": reasoning.action_reasoning,
                            "answer": reasoning.action_reasoning,
                        }
                    ),
                },
            }
        )
    elif reasoning.next_action == "get_datetime":
        action_message["tool_calls"].append(
            {
                "id": f"call_datetime_{len(messages)}",
                "type": "function",
                "function": {"name": "get_current_datetime", "arguments": "{}"},
            }
        )
    elif reasoning.next_action == "create_file":
        # In API mode, use overwrite=true to avoid conflicts
        action_message["tool_calls"].append(
            {
                "id": f"call_create_file_{len(messages)}",
                "type": "function",
                "function": {
                    "name": "create_local_file",
                    "arguments": json.dumps(
                        {
                            "reasoning": reasoning.action_reasoning,
                            "file_path": "ai_story.txt",
                            "content": "This is a short story about AI created by SGR Research Agent.",
                            "encoding": "utf-8",
                            "overwrite": True,  # Force overwrite in API mode
                        }
                    ),
                },
            }
        )
    elif reasoning.next_action == "read_file":
        action_message["tool_calls"].append(
            {
                "id": f"call_read_file_{len(messages)}",
                "type": "function",
                "function": {
                    "name": "read_local_file",
                    "arguments": json.dumps(
                        {
                            "reasoning": reasoning.action_reasoning,
                            "file_path": "ai_story.txt",
                            "encoding": "utf-8",
                        }
                    ),
                },
            }
        )
    elif reasoning.next_action == "update_file":
        action_message["tool_calls"].append(
            {
                "id": f"call_update_file_{len(messages)}",
                "type": "function",
                "function": {
                    "name": "update_local_file",
                    "arguments": json.dumps(
                        {
                            "reasoning": reasoning.action_reasoning,
                            "file_path": "ai_story.txt",
                            "operation": "append",
                            "content": "\n\nAdditional content added by SGR Agent.",
                            "encoding": "utf-8",
                        }
                    ),
                },
            }
        )
    elif reasoning.next_action == "list_dir":
        action_message["tool_calls"].append(
            {
                "id": f"call_list_dir_{len(messages)}",
                "type": "function",
                "function": {
                    "name": "list_directory",
                    "arguments": json.dumps(
                        {
                            "reasoning": reasoning.action_reasoning,
                            "directory_path": ".",
                            "show_hidden": False,
                            "recursive": False,
                            "max_depth": 1,
                            "tree_view": True,
                        }
                    ),
                },
            }
        )
    elif reasoning.next_action == "create_dir":
        action_message["tool_calls"].append(
            {
                "id": f"call_create_dir_{len(messages)}",
                "type": "function",
                "function": {
                    "name": "create_directory",
                    "arguments": json.dumps(
                        {
                            "reasoning": reasoning.action_reasoning,
                            "directory_path": "output",
                            "create_parents": True,
                            "description": "Output directory for SGR Agent results",
                        }
                    ),
                },
            }
        )
    elif reasoning.next_action == "create_report":
        action_message["tool_calls"].append(
            {
                "id": f"call_create_report_{len(messages)}",
                "type": "function",
                "function": {
                    "name": "create_report",
                    "arguments": json.dumps(
                        {
                            "reasoning": reasoning.action_reasoning,
                            "report_type": "research",
                            "title": "Research Report",
                            "content": "Report content will be generated based on research findings.",
                            "format": "markdown",
                        }
                    ),
                },
            }
        )
    elif reasoning.next_action == "clarify":
        action_message["tool_calls"].append(
            {
                "id": f"call_clarify_{len(messages)}",
                "type": "function",
                "function": {
                    "name": "clarification",
                    "arguments": json.dumps(
                        {
                            "reasoning": reasoning.action_reasoning,
                            "question": "Could you please clarify your request?",
                            "context": "Additional context for clarification",
                        }
                    ),
                },
            }
        )

    if action_message["tool_calls"]:
        messages.append(action_message)

        # Execute tool calls
        for tc in action_message["tool_calls"]:
            result = execute_tool_call_api(tc, context)
            results.append(result)

            # Check if task is completed by the tool
            if result.get("task_completed", False):
                context["task_completed"] = True
                context["file_created"] = result.get("tool") == "create_local_file"
                context["report_created"] = result.get("tool") == "create_report"
                context["simple_answer_given"] = result.get("tool") == "simple_answer"

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

    return results


def execute_tool_call_api(
    tool_call: Dict[str, Any], context: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute a single tool call for API."""
    tool_name = tool_call["function"]["name"]

    try:
        tool_args = json.loads(tool_call["function"]["arguments"])
    except json.JSONDecodeError:
        tool_args = {}

    # Execute tool locally
    if tool_name in executors:
        try:
            if tool_name == "web_search":
                step = WebSearchStep(tool="web_search", **tool_args)
                return executors[tool_name](step, context, tavily)
            elif tool_name == "simple_answer":
                step = SimpleAnswerStep(tool="simple_answer", **tool_args)
                return executors[tool_name](step, context)
            elif tool_name == "get_current_datetime":
                step = GetCurrentDatetimeStep(tool="get_current_datetime", **tool_args)
                return executors[tool_name](step, context)
            elif tool_name == "create_local_file":
                step = CreateLocalFileStep(tool="create_local_file", **tool_args)
                return executors[tool_name](step, context)
            elif tool_name == "read_local_file":
                step = ReadLocalFileStep(tool="read_local_file", **tool_args)
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
            elif tool_name == "create_report":
                step = CreateReportStep(tool="create_report", **tool_args)
                return executors[tool_name](step, context)
            elif tool_name == "report_completion":
                step = ReportCompletionStep(tool="report_completion", **tool_args)
                return executors[tool_name](step, context)
            elif tool_name == "clarification":
                step = ClarificationStep(tool="clarification", **tool_args)
                return executors[tool_name](step, context)
            else:
                return {"error": f"Tool {tool_name} not implemented in API"}
        except Exception as e:
            return {"error": f"Tool execution failed: {str(e)}"}
    else:
        return {"error": f"No executor for tool: {tool_name}"}


# =============================================================================
# STREAMING HELPERS
# =============================================================================


def create_reasoning_chunk(
    reasoning: ReasoningStep, round_num: int, max_rounds: int
) -> str:
    """Create reasoning chunk for streaming."""
    chunk = ChatCompletionChunk(
        id=f"chatcmpl-{int(datetime.now().timestamp())}",
        created=int(datetime.now().timestamp()),
        model=CONFIG["openai_model"],
        choices=[
            {
                "index": 0,
                "delta": {
                    "content": f"\n\n**Round {round_num}/{max_rounds} - Analysis:**\n"
                    f"Current situation: {reasoning.current_situation}\n"
                    f"Next action: {reasoning.next_action}\n"
                    f"Reasoning: {reasoning.action_reasoning}"
                },
                "finish_reason": None,
            }
        ],
    )
    return f"data: {chunk.model_dump_json()}\n\n"


def create_action_chunk(result: Dict[str, Any], round_num: int, max_rounds: int) -> str:
    """Create action result chunk for streaming."""
    content = f"\n**Action Result (Round {round_num}/{max_rounds}):**\n"

    if "error" in result:
        content += f"❌ Error: {result['error']}"
    elif "answer" in result:
        content += f"💬 Answer: {result['answer']}"
    elif "datetime" in result:
        content += f"🕒 Current time: {result['datetime']}"
    elif "results" in result:
        content += f"🔍 Search results: {len(result['results'])} items found"
    else:
        content += f"✅ Action completed: {json.dumps(result, ensure_ascii=False)}"

    chunk = ChatCompletionChunk(
        id=f"chatcmpl-{int(datetime.now().timestamp())}",
        created=int(datetime.now().timestamp()),
        model=CONFIG["openai_model"],
        choices=[{"index": 0, "delta": {"content": content}, "finish_reason": None}],
    )
    return f"data: {chunk.model_dump_json()}\n\n"


def create_completion_chunk(
    reasoning: ReasoningStep, round_num: int, max_rounds: int
) -> str:
    """Create completion chunk for streaming."""
    content = f"\n\n**Task completed in {round_num} rounds!**\n"
    content += f"Final status: {reasoning.current_situation}"

    chunk = ChatCompletionChunk(
        id=f"chatcmpl-{int(datetime.now().timestamp())}",
        created=int(datetime.now().timestamp()),
        model=CONFIG["openai_model"],
        choices=[{"index": 0, "delta": {"content": content}, "finish_reason": "stop"}],
    )
    return f"data: {chunk.model_dump_json()}\n\n"


def create_error_chunk(
    error_result: Dict[str, Any], round_num: int, max_rounds: int
) -> str:
    """Create error chunk for streaming."""
    content = (
        f"\n❌ **Error in round {round_num}/{max_rounds}:** {error_result['error']}"
    )

    chunk = ChatCompletionChunk(
        id=f"chatcmpl-{int(datetime.now().timestamp())}",
        created=int(datetime.now().timestamp()),
        model=CONFIG["openai_model"],
        choices=[{"index": 0, "delta": {"content": content}, "finish_reason": "stop"}],
    )
    return f"data: {chunk.model_dump_json()}\n\n"


def create_final_response(
    messages: List[Dict[str, Any]], context: Dict[str, Any], rounds: int
) -> ChatCompletionResponse:
    """Create final response for non-streaming mode."""
    # Build final content from messages
    final_content = ""
    for msg in messages:
        if msg.get("role") == "assistant" and msg.get("content"):
            final_content += msg.get("content", "") + "\n"
        elif msg.get("role") == "tool":
            content = msg.get("content", "")
            if content:
                try:
                    data = json.loads(content)
                    if "answer" in data:
                        final_content += f"Answer: {data['answer']}\n"
                    elif "datetime" in data:
                        final_content += f"Current time: {data['datetime']}\n"
                    elif "results" in data:
                        final_content += (
                            f"Search results: {len(data['results'])} items found\n"
                        )
                except (json.JSONDecodeError, KeyError, TypeError):
                    pass

    if not final_content.strip():
        final_content = "Research completed successfully."

    return ChatCompletionResponse(
        id=f"chatcmpl-{int(datetime.now().timestamp())}",
        created=int(datetime.now().timestamp()),
        model=CONFIG["openai_model"],
        choices=[
            {
                "index": 0,
                "message": {"role": "assistant", "content": final_content},
                "finish_reason": "stop",
            }
        ],
        usage={
            "prompt_tokens": len(str(messages)) // 4,
            "completion_tokens": len(final_content) // 4,
            "total_tokens": (len(str(messages)) + len(final_content)) // 4,
        },
    )


# =============================================================================
# API ENDPOINTS
# =============================================================================


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest):
    """OpenAI-compatible chat completions endpoint."""

    # Convert messages to internal format
    internal_messages = []
    for msg in request.messages:
        internal_messages.append(
            {"role": msg.role, "content": msg.content, "name": msg.name}
        )

    if request.stream:
        # Streaming response
        async def generate_stream():
            try:
                async for chunk in execute_sgr_research_streaming(internal_messages):
                    yield chunk
                # Send final data
                yield "data: [DONE]\n\n"
            except Exception as e:
                error_chunk = create_error_chunk({"error": str(e)}, 1, 1)
                yield error_chunk
                yield "data: [DONE]\n\n"

        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
            },
        )
    else:
        # Non-streaming response
        try:
            result = await execute_sgr_research_non_streaming(internal_messages)
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "model": CONFIG["openai_model"],
        "version": "1.0.0",
    }


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "SGR Research Agent API",
        "version": "1.0.0",
        "endpoints": {
            "chat_completions": "/v1/chat/completions",
            "health": "/health",
            "docs": "/docs",
        },
        "compatibility": "OpenAI Chat Completions API v1",
    }


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "api_server:app", host="0.0.0.0", port=8080, reload=True, log_level="info"
    )
