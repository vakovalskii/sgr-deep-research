#!/usr/bin/env python3
"""
Interactive CLI client for SGR Deep Research Agent
Supports streaming, clarifications, and continuous conversations
"""

import asyncio
import json
import sys
import re
from typing import Optional, Dict, Any
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from rich.live import Live
from rich.spinner import Spinner

console = Console()

class SGRClient:
    def __init__(self, base_url: str = "http://localhost:8010"):
        self.base_url = base_url
        self.current_agent_id: Optional[str] = None
        self.waiting_for_clarification = False
        
    async def send_message(self, message: str, agent_model: str = "sgr_agent") -> Optional[str]:
        """Send message to agent and handle streaming response"""
        url = f"{self.base_url}/v1/chat/completions"
        
        # If we have an active agent waiting for clarification, use its ID
        model = self.current_agent_id if self.current_agent_id and self.waiting_for_clarification else agent_model
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": message}],
            "stream": True
        }
        
        headers = {"Content-Type": "application/json"}
        
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    if response.status_code != 200:
                        try:
                            error_text = await response.aread()
                            error_text = error_text.decode('utf-8')
                        except:
                            error_text = "Unknown error"
                        console.print(f"[red]Error: {response.status_code} - {error_text}[/red]")
                        return None
                    
                    # Extract agent ID from headers
                    agent_id = response.headers.get("X-Agent-ID")
                    if agent_id and not self.waiting_for_clarification:
                        self.current_agent_id = agent_id
                        console.print(f"[dim]🤖 Agent ID: {agent_id}[/dim]")
                    
                    return await self._process_stream(response)
                    
        except Exception as e:
            console.print(f"[red]Connection error: {e}[/red]")
            return None
    
    async def _process_stream(self, response) -> Optional[str]:
        """Process streaming response and handle different chunk types"""
        console.print("\n[bold blue]🤖 Agent Response:[/bold blue]")
        
        full_response = ""
        tool_calls_buffer = {}
        
        async for line in response.aiter_lines():
            if not line.strip():
                continue
                
            if line.startswith("data: "):
                data_str = line[6:]
                
                if data_str.strip() == "[DONE]":
                    break
                
                try:
                    chunk = json.loads(data_str)
                    if "choices" in chunk and chunk["choices"]:
                        choice = chunk["choices"][0]
                        
                        # Handle regular content
                        if "delta" in choice and "content" in choice["delta"]:
                            content = choice["delta"]["content"]
                            if content:
                                full_response += content
                                # Check if this looks like a tool result
                                if content.strip().startswith("✅") or content.strip().startswith("📄") or content.strip().startswith("🔍"):
                                    console.print(f"\n[green]{content.strip()}[/green]")
                                elif content.strip().startswith("❌"):
                                    console.print(f"\n[red]{content.strip()}[/red]")
                                else:
                                    console.print(content, end="")
                        
                        # Handle tool calls
                        if "delta" in choice and "tool_calls" in choice["delta"]:
                            tool_calls = choice["delta"]["tool_calls"]
                            if tool_calls:
                                for tool_call in tool_calls:
                                    tool_id = tool_call.get("id", "")
                                    if tool_id:
                                        if tool_id not in tool_calls_buffer:
                                            tool_calls_buffer[tool_id] = {
                                                "name": "",
                                                "arguments": ""
                                            }
                                        
                                        if "function" in tool_call:
                                            func = tool_call["function"]
                                            if "name" in func:
                                                tool_calls_buffer[tool_id]["name"] = func["name"]
                                            if "arguments" in func:
                                                tool_calls_buffer[tool_id]["arguments"] += func["arguments"]
                                                
                                                # Try to parse and display tool call when complete
                                                try:
                                                    args = json.loads(tool_calls_buffer[tool_id]["arguments"])
                                                    self._display_tool_call(tool_calls_buffer[tool_id]["name"], args)
                                                    # Clear buffer after displaying
                                                    del tool_calls_buffer[tool_id]
                                                except json.JSONDecodeError:
                                                    # Arguments not complete yet, continue buffering
                                                    pass
                        
                        # Check for finish_reason and final parsed result
                        if choice.get("finish_reason") == "stop":
                            # Try to parse the complete response as structured output
                            try:
                                parsed_response = json.loads(full_response)
                                return self._handle_structured_response(parsed_response)
                            except json.JSONDecodeError:
                                pass
                
                except json.JSONDecodeError:
                    continue
        
        console.print()  # Add newline
        return full_response or "Task completed"
    
    def _handle_structured_response(self, response: Dict[str, Any]) -> str:
        """Handle structured response from agent"""
        
        # Check if this is a clarification request
        if "function" in response:
            function = response["function"]
            tool_name = function.get("tool_name_discriminator", "")
            
            if tool_name == "clarificationtool":
                questions = function.get("questions", [])
                if questions:
                    console.print("\n")
                    self._display_clarification_questions(questions)
                    self.waiting_for_clarification = True
                    return "CLARIFICATION_NEEDED"
            
            elif tool_name == "simpleanswertool":
                answer = function.get("answer", "")
                confidence = function.get("confidence", "medium")
                console.print(f"\n[cyan]💬 Simple answer ({confidence} confidence): {answer}[/cyan]")
                # Reset session after simple answer
                self.reset_session()
                return answer
            
            elif tool_name == "websearchtool":
                query = function.get("query", "")
                console.print(f"\n[green]🔍 Searching: {query}[/green]")
                
            elif tool_name == "createreporttool":
                title = function.get("title", "")
                console.print(f"\n[blue]📄 Creating report: {title}[/blue]")
                
            elif tool_name == "agentcompletiontool":
                console.print("\n[green]✅ Task completed[/green]")
                # Reset session after task completion
                self.reset_session()
        
        return "Task in progress"
    
    def _format_streaming_content(self, content: str) -> Panel:
        """Format streaming content for display"""
        text = Text(content)
        return Panel(text, title="Response", border_style="blue")
    
    def _display_clarification_questions(self, questions: list):
        """Display clarification questions to user"""
        console.print("[bold yellow]🤔 Agent needs clarification:[/bold yellow]")
        
        for i, question in enumerate(questions, 1):
            console.print(f"[yellow]{i}. {question}[/yellow]")
        
        console.print(f"\n[dim]💡 To answer, just type your response below. Agent will continue the conversation.[/dim]")
    
    def _display_tool_call(self, tool_name: str, args: dict):
        """Display information about a single tool call"""
        if tool_name == "websearchtool":
            query = args.get("query", "")
            console.print(f"\n[green]🔍 Searching: {query}[/green]")
            
        elif tool_name == "createreporttool":
            title = args.get("title", "")
            console.print(f"\n[blue]📄 Creating report: {title}[/blue]")
            
        elif tool_name == "agentcompletiontool":
            status = args.get("status", "")
            completed_steps = args.get("completed_steps", [])
            console.print(f"\n[green]✅ Task completed ({status})[/green]")
            if completed_steps:
                console.print("[dim]Completed steps:[/dim]")
                for step in completed_steps:
                    console.print(f"[dim]  • {step}[/dim]")
            
        elif tool_name == "simpleanswertool":
            answer = args.get("answer", "")
            confidence = args.get("confidence", "medium")
            console.print(f"\n[cyan]💬 Simple answer ({confidence} confidence): {answer}[/cyan]")
            
        elif tool_name == "clarificationtool":
            questions = args.get("questions", [])
            console.print(f"\n[yellow]🤔 Agent needs clarification:[/yellow]")
            for i, question in enumerate(questions, 1):
                console.print(f"[yellow]{i}. {question}[/yellow]")
        
        else:
            # Generic tool call display
            console.print(f"\n[magenta]🛠️ Using tool: {tool_name}[/magenta]")
            if args:
                reasoning = args.get("reasoning", "")
                if reasoning:
                    console.print(f"[dim]Reasoning: {reasoning}[/dim]")

    def _display_tool_calls(self, tool_calls: list):
        """Display information about tool calls (legacy method)"""
        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            args = tool_call.get("args", {})
            self._display_tool_call(tool_name, args)
    
    def show_help(self):
        """Show help information"""
        help_text = """
[bold blue]SGR Agent CLI Commands:[/bold blue]

[green]/help[/green]     - Show this help
[green]/quit[/green]     - Exit the client
[green]/new[/green]      - Start new conversation (reset agent)
[green]/status[/green]   - Show current agent status

[bold]Usage:[/bold]
- Type your question or message
- If agent asks for clarification, just type your answer
- The client automatically handles agent IDs and continues conversations

[bold]Examples:[/bold]
- "Найди цену биткоина"
- "Какая погода в Москве сегодня"
- "Да, мне нужен точный прогноз" (response to clarification)
"""
        console.print(Panel(help_text, title="Help", border_style="cyan"))
    
    def show_status(self):
        """Show current status"""
        if self.current_agent_id:
            status = "Waiting for clarification" if self.waiting_for_clarification else "Active conversation"
            console.print(f"[blue]Agent ID: {self.current_agent_id}[/blue]")
            console.print(f"[blue]Status: {status}[/blue]")
        else:
            console.print("[dim]No active agent session[/dim]")
    
    def reset_session(self):
        """Reset current session"""
        self.current_agent_id = None
        self.waiting_for_clarification = False
        console.print("[green]✅ Session reset. Next message will create a new agent.[/green]")

async def main():
    client = SGRClient()
    
    # Welcome message
    console.print(Panel(
        "[bold blue]Welcome to SGR Deep Research Agent CLI![/bold blue]\n"
        "Type [green]/help[/green] for commands or start asking questions.",
        title="SGR CLI",
        border_style="cyan"
    ))
    
    while True:
        try:
            # Get user input
            if client.waiting_for_clarification:
                prompt_text = f"[yellow]Answer ({client.current_agent_id[:8]}...): [/yellow]"
            else:
                prompt_text = "[green]You: [/green]"
            
            user_input = Prompt.ask(prompt_text).strip()
            
            if not user_input:
                continue
            
            # Handle commands
            if user_input.startswith('/'):
                command = user_input[1:].lower()
                
                if command == 'help':
                    client.show_help()
                elif command == 'quit' or command == 'exit':
                    console.print("[yellow]Goodbye! 👋[/yellow]")
                    break
                elif command == 'new':
                    client.reset_session()
                elif command == 'status':
                    client.show_status()
                else:
                    console.print(f"[red]Unknown command: /{command}[/red]")
                continue
            
            # Send message to agent
            response = await client.send_message(user_input)
            
            if response is None:
                console.print("[red]Failed to get response from agent[/red]")
            elif response == "CLARIFICATION_NEEDED":
                # Agent is waiting for clarification, continue loop
                pass
            else:
                # If we were waiting for clarification and got a response, reset for next message
                if client.waiting_for_clarification:
                    client.reset_session()
                    console.print("[dim]✨ Ready for new conversation[/dim]")
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Goodbye! 👋[/yellow]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

if __name__ == "__main__":
    asyncio.run(main())
