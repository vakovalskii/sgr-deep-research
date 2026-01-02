"""Very basic demo for processing research queries and clarification requests
from agent.

Usage:
    pip install rich openai
    python -m docs.examples.simple_shine_cli
"""

import json

from openai import OpenAI
from rich.console import Console
from rich.prompt import Prompt

console = Console()
client = OpenAI(base_url="http://localhost:8010/v1", api_key="dummy")


def safe_get_delta(chunk):
    if not hasattr(chunk, "choices") or not chunk.choices:
        return None
    first_choice = chunk.choices[0]
    if first_choice is None or not hasattr(first_choice, "delta"):
        return None
    return first_choice.delta


def stream_response_until_tool_call_or_end(model, messages):
    """Real-time streaming."""
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
        temperature=0,
    )

    agent_id = None
    full_content = ""
    clarification_questions = None

    for chunk in response:
        if hasattr(chunk, "model") and chunk.model and chunk.model.startswith("sgr_agent_"):
            agent_id = chunk.model

        delta = safe_get_delta(chunk)
        if delta is None:
            continue

        if hasattr(delta, "tool_calls") and delta.tool_calls:
            for tool_call in delta.tool_calls:
                if tool_call.function and tool_call.function.name == "clarificationtool":
                    try:
                        args = json.loads(tool_call.function.arguments)
                        clarification_questions = args.get("questions", [])
                    except Exception as e:
                        console.print(f"[red]Error parsing clarification: {e}[/red]")
            # stop streaming after tool calling detect
            return full_content, clarification_questions, agent_id

        if hasattr(delta, "content") and delta.content:
            text = delta.content
            full_content += text
            console.print(text, end="", style="white")

    return full_content, None, agent_id


console.print("\n[bold green]Research Assistant v1.0[/bold green]", style="bold white")
initial_request = Prompt.ask("[bold yellow]Enter your research request[/bold yellow]")
console.print(f"\nStarting research: [bold]{initial_request}[/bold]")

current_model = "sgr_agent"
messages = [{"role": "user", "content": initial_request}]
agent_id = None

while True:
    console.print()

    full_content, clarification_questions, returned_agent_id = stream_response_until_tool_call_or_end(
        model=current_model, messages=messages
    )

    if returned_agent_id:
        agent_id = returned_agent_id
        current_model = agent_id
    if clarification_questions is not None:
        console.print()

        console.print("\n[bold red]Clarification needed:[/bold red]")
        for i, question in enumerate(clarification_questions, 1):
            console.print(f"[bold]{i}.[/bold] {question}", style="yellow")

        clarification = Prompt.ask("[bold grey]Enter your clarification[/bold grey]")
        console.print(f"\n[bold green]Providing clarification:[/bold green] [italic]{clarification}[/italic]")

        messages.append({"role": "user", "content": clarification})
        continue

    else:
        console.print()
        break

console.print("\n[bold green] Report will be prepared in appropriate directory![/bold green]")
