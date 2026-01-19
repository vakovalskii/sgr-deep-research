"""Main Textual application for SGR CLI."""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Optional

# Add current directory to path for imports when running directly
if __name__ == "__main__":
    current_dir = Path(__file__).parent.resolve()
    if str(current_dir) not in sys.path:
        sys.path.insert(0, str(current_dir))

from textual import events
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Static
from textual.events import Key

from sgr_agent_core.agent_config import GlobalConfig
from sgr_agent_core.models import AgentStatesEnum
from sgr_agent_core.tools import ClarificationTool

from .ascii_art import get_ascii_logo, get_full_logo
from .agent_manager import AgentManager
from .config import CLIConfig, load_agent_config, load_cli_config
from .models import Message, MessageRole, ToolExecution
from .widgets import ChatWidget, HistoryWidget, ToolsListWidget

logger = logging.getLogger(__name__)


class SGRCLIApp(App):
    """Main SGR CLI application."""

    CSS = """
    Screen {
        background: $background;
    }

    #main-container {
        layout: horizontal;
        height: 1fr;
    }

    #chat-container {
        width: 1fr;
        layout: vertical;
    }

    #tools-container {
        width: 40;
        border-left: solid $primary;
        layout: vertical;
        display: none;
    }

    #tools-container.visible {
        display: block;
    }

    #history-container {
        height: 10;
        border-top: solid $primary;
        layout: vertical;
        display: none;
    }

    #history-container.visible {
        display: block;
    }

    #status-bar {
        height: 3;
        background: $surface;
        border-top: solid $primary;
        padding: 1;
    }
    """
    WATCH_CSS = True
    TITLE = "SGR CLI"
    SUB_TITLE = "Schema-Guided Reasoning Agent Interface"

    def __init__(
        self,
        agent_config_path: Path,
        cli_config_path: Optional[Path] = None,
        agents_config_path: Optional[Path] = None,
        agent_name: Optional[str] = None,
        **kwargs,
    ):
        """Initialize SGR CLI app.

        Args:
            agent_config_path: Path to main agent configuration YAML (config.yaml)
            cli_config_path: Path to CLI configuration YAML (optional)
            agents_config_path: Path to agents configuration YAML (agents.yaml, optional)
            agent_name: Name of agent to use (optional)
            **kwargs: Additional app arguments
        """
        super().__init__(**kwargs)
        self.agent_config_path = agent_config_path
        self.cli_config_path = cli_config_path
        self.agents_config_path = agents_config_path
        self.agent_name = agent_name

        # Load CLI config early so it's available in compose()
        self.cli_config = load_cli_config(self.cli_config_path)
        self.agent_config: Optional[GlobalConfig] = None
        self.agent_manager: Optional[AgentManager] = None

        self.chat_widget: Optional[ChatWidget] = None
        self.tools_widget: Optional[ToolsListWidget] = None
        self.history_widget: Optional[HistoryWidget] = None

        self.current_clarification: Optional[ClarificationTool] = None
        self.streaming_task: Optional[asyncio.Task] = None
        self.execution_task: Optional[asyncio.Task] = None
        
        # Panel visibility state
        self.tools_panel_visible = False
        self.history_panel_visible = False
        
        # Track displayed log entries to avoid duplicates
        self.displayed_log_indices: set[int] = set()
        
        # Processing status
        self.processing_start_time: Optional[float] = None
        self.status_update_task: Optional[asyncio.Task] = None

    def compose(self) -> ComposeResult:
        """Compose the application."""
        # No header for minimal interface like gemini-cli
        with Container(id="main-container"):
            with Vertical(id="chat-container"):
                yield ChatWidget(id="chat")
            # Tools panel - always created but hidden by default
            with Vertical(id="tools-container"):
                yield ToolsListWidget(id="tools")
        # History panel - always created but hidden by default
        with Horizontal(id="history-container"):
            yield HistoryWidget(id="history")
        yield Static("Ready | Ctrl+T: tools | Ctrl+H: history", id="status-bar")
        yield Footer()

    async def on_mount(self) -> None:
        """Called when app is mounted."""
        # Load agent configuration
        self.agent_config = load_agent_config(
            self.agent_config_path,
            agents_path=self.agents_config_path,
        )

        # Get widgets
        self.chat_widget = self.query_one("#chat", ChatWidget)
        self.tools_widget = self.query_one("#tools", ToolsListWidget)
        self.history_widget = self.query_one("#history", HistoryWidget)
        
        # Focus on input field
        input_widget = self.chat_widget.query_one("#chat-input")
        input_widget.focus()
        
        # Panels are hidden by default - show them if enabled in config
        if self.cli_config.show_tools_panel:
            self.toggle_tools_panel()
        if self.cli_config.show_history_panel:
            self.toggle_history_panel()

        # Show ASCII logo and available agents if no agent specified
        if not self.agent_name and self.agent_config.agents:
            available_agents = list(self.agent_config.agents.keys())
            agents_info = "\n".join([f"  {i+1}. {name}" for i, name in enumerate(available_agents)])
            
            # Get ASCII logo
            ascii_logo = ""
            try:
                # Get terminal size after app is mounted
                terminal_width = self.size.width if hasattr(self, 'size') and self.size.width > 0 else 80
                ascii_logo = get_full_logo(terminal_width)
            except Exception:
                # If ASCII art fails, continue without it
                pass
            
            # Combine ASCII logo with agents info
            if ascii_logo:
                welcome_content = f"{ascii_logo}\n\nSchema-Guided Reasoning Agent CLI\n\nAvailable agents:\n{agents_info}\n\nUsing default agent: {available_agents[0]}\nType '/agent <name>' to switch agents or start chatting."
            else:
                welcome_content = f"Available agents:\n{agents_info}\n\nUsing default agent: {available_agents[0]}\nType '/agent <name>' to switch agents or start chatting."
            
            welcome_msg = Message(
                role=MessageRole.SYSTEM,
                content=welcome_content
            )
            self.chat_widget.add_message(welcome_msg)
        else:
            # Show ASCII logo only if agent is already specified
            try:
                # Get terminal size after app is mounted
                terminal_width = self.size.width if hasattr(self, 'size') and self.size.width > 0 else 80
                ascii_logo = get_ascii_logo(terminal_width)
                logo_msg = Message(
                    role=MessageRole.SYSTEM,
                    content=f"{ascii_logo}\n\nSchema-Guided Reasoning Agent CLI"
                )
                self.chat_widget.add_message(logo_msg)
            except Exception:
                # If ASCII art fails, continue without it
                pass

        # Initialize agent manager
        self.agent_manager = AgentManager(self.agent_config, self.agent_name)

        # Update status with shortcuts hint
        status_parts = []
        if self.agent_manager.agent_name:
            status_parts.append(f"Agent: {self.agent_manager.agent_name}")
        status_parts.append("Ctrl+T: tools | Ctrl+H: history")
        self.update_status(" | ".join(status_parts))

    def update_status(self, status: str) -> None:
        """Update status bar.

        Args:
            status: Status message
        """
        status_bar = self.query_one("#status-bar", Static)
        status_bar.update(status)


    async def on_chat_widget_message_submitted(self, event: ChatWidget.MessageSubmitted) -> None:
        """Handle message submission from chat widget.

        Args:
            event: Message submitted event
        """
        message = event.message

        # Add to history
        if self.history_widget:
            self.history_widget.add_message(message)

        # If we're waiting for clarification, provide it
        if self.current_clarification and self.agent_manager:
            # Prepare clarification message with images if any
            if message.images:
                clarification_msg = self.agent_manager.prepare_message_with_images(message.content, message.images)
            else:
                clarification_msg = {"role": "user", "content": message.content}
            await self.agent_manager.agent.provide_clarification([clarification_msg])
            self.current_clarification = None
            self.update_status("Processing clarification...")
            # Continue execution
            self.streaming_task = asyncio.create_task(self._execute_agent_with_streaming())
            return

        # Start new conversation or continue existing
        if not self.agent_manager.agent:
            # Prepare message with images if any
            if message.images:
                task_message = self.agent_manager.prepare_message_with_images(message.content, message.images)
            else:
                task_message = {"role": "user", "content": message.content}
            # Create agent with initial message
            await self.agent_manager.create_agent([task_message])
            self.update_status(f"Agent '{self.agent_manager.agent_name}' created")

        # Start agent execution
        self.update_status("Agent thinking...")
        self.streaming_task = asyncio.create_task(self._execute_agent_with_streaming())

    async def _execute_agent_with_streaming(self) -> None:
        """Execute agent and handle streaming."""
        if not self.agent_manager or not self.chat_widget:
            return

        try:
            # Start streaming
            self.chat_widget.start_streaming(MessageRole.ASSISTANT)

            agent = self.agent_manager.agent
            if not agent:
                return

            # Reset displayed log indices for new execution
            self.displayed_log_indices.clear()
            
            # Start status update task
            self.status_update_task = asyncio.create_task(self._update_processing_status())
            
            # Start agent execution in background
            self.execution_task = asyncio.create_task(self.agent_manager.execute_agent())
            execution_task = self.execution_task

            # Monitor agent logs for reasoning and tool executions
            log_monitor_task = asyncio.create_task(self._monitor_agent_logs(agent, execution_task))

            # Monitor agent state and stream responses
            streaming_task = None
            if agent.streaming_generator:
                streaming_task = asyncio.create_task(self._stream_responses(agent, execution_task))

            # Wait for execution to complete
            try:
                result = await execution_task
            except asyncio.CancelledError:
                # Execution was cancelled for clarification or by user
                if streaming_task:
                    streaming_task.cancel()
                if log_monitor_task and not log_monitor_task.done():
                    log_monitor_task.cancel()
                    try:
                        await log_monitor_task
                    except asyncio.CancelledError:
                        pass
                if self.status_update_task and not self.status_update_task.done():
                    self.status_update_task.cancel()
                self.processing_start_time = None
                # Don't return here - let it fall through to display cancellation message
                raise  # Re-raise to be caught by outer handler

            # Cancel streaming if still running
            if streaming_task and not streaming_task.done():
                streaming_task.cancel()
                try:
                    await streaming_task
                except asyncio.CancelledError:
                    pass
            
            # Cancel log monitor if still running
            if log_monitor_task and not log_monitor_task.done():
                log_monitor_task.cancel()
                try:
                    await log_monitor_task
                except asyncio.CancelledError:
                    pass
            
            # Display any remaining logs
            await self._display_pending_logs(agent)

            # Check if agent needs clarification
            if agent._context.state == AgentStatesEnum.WAITING_FOR_CLARIFICATION:
                # Get clarification from last tool execution
                if agent.log:
                    for log_entry in reversed(agent.log):
                        if log_entry.get("step_type") == "tool_execution":
                            tool_context = log_entry.get("agent_tool_context", {})
                            if tool_context.get("tool_name") == "ClarificationTool":
                                questions = tool_context.get("questions", [])
                                if questions:
                                    self.chat_widget.add_clarification_questions(questions)
                                    self.update_status("Waiting for clarification...")
                                    return

            # Finish streaming
            final_message = self.chat_widget.finish_streaming()
            if result:
                final_message.content = result
                self.chat_widget.add_message(final_message)

            # Update tools list
            if self.tools_widget:
                tools = self.agent_manager.get_tool_executions()
                self.tools_widget.update_tool_executions(tools)

            # Reset processing time
            self.processing_start_time = None
            
            # Update status with shortcuts hint
            status_parts = []
            if self.agent_manager.agent_name:
                status_parts.append(f"Agent: {self.agent_manager.agent_name}")
            status_parts.append("Ctrl+T: tools | Ctrl+H: history")
            self.update_status(" | ".join(status_parts))
            
            # Return focus to input after agent finishes
            if self.chat_widget:
                input_widget = self.chat_widget.query_one("#chat-input")
                input_widget.focus()

        except asyncio.CancelledError:
            # Request was cancelled
            self.processing_start_time = None
            if self.status_update_task and not self.status_update_task.done():
                self.status_update_task.cancel()
                try:
                    await self.status_update_task
                except asyncio.CancelledError:
                    pass
            
            # Cancel all related tasks
            if log_monitor_task and not log_monitor_task.done():
                log_monitor_task.cancel()
                try:
                    await log_monitor_task
                except asyncio.CancelledError:
                    pass
            
            if streaming_task and not streaming_task.done():
                streaming_task.cancel()
                try:
                    await streaming_task
                except asyncio.CancelledError:
                    pass
            
            self.update_status("Запрос отменен")
            if self.chat_widget:
                # Finish streaming if it was started
                try:
                    self.chat_widget.finish_streaming()
                except:
                    pass
                cancel_message = Message(role=MessageRole.SYSTEM, content="Запрос отменен пользователем")
                self.chat_widget.add_message(cancel_message)
                input_widget = self.chat_widget.query_one("#chat-input")
                input_widget.focus()
        except Exception as e:
            logger.error(f"Agent execution error: {e}", exc_info=True)
            self.processing_start_time = None
            if self.status_update_task and not self.status_update_task.done():
                self.status_update_task.cancel()
            self.update_status(f"Error: {str(e)}")
            if self.chat_widget:
                error_message = Message(role=MessageRole.SYSTEM, content=f"Error: {str(e)}")
                self.chat_widget.add_message(error_message)
                # Return focus to input after error
                input_widget = self.chat_widget.query_one("#chat-input")
                input_widget.focus()

    async def _stream_responses(self, agent, execution_task: asyncio.Task) -> None:
        """Stream agent responses.

        Args:
            agent: Agent instance
            execution_task: Agent execution task
        """
        if not agent.streaming_generator:
            return

        try:
            async for chunk in agent.streaming_generator.stream():
                if execution_task.done():
                    break

                if chunk:
                    # Parse SSE chunk format
                    try:
                        if chunk.startswith("data: "):
                            data_str = chunk[6:].strip()
                            if data_str == "[DONE]":
                                break
                            data = json.loads(data_str)
                            if "choices" in data and data["choices"]:
                                delta = data["choices"][0].get("delta", {})
                                if "content" in delta and delta["content"]:
                                    self.chat_widget.append_streaming_content(delta["content"])
                                # Check for tool calls
                                if "tool_calls" in delta and delta["tool_calls"]:
                                    for tool_call in delta["tool_calls"]:
                                        if tool_call.get("function", {}).get("name") == "ClarificationTool":
                                            # Will be handled after execution
                                            pass
                    except (json.JSONDecodeError, KeyError):
                        # If not JSON, treat as plain text
                        if chunk.strip() and not chunk.startswith("data:"):
                            self.chat_widget.append_streaming_content(chunk)

                await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            # Streaming cancelled
            pass

    async def _monitor_agent_logs(self, agent, execution_task: asyncio.Task) -> None:
        """Monitor agent logs and display reasoning and tool executions.
        
        Args:
            agent: Agent instance
            execution_task: Agent execution task
        """
        last_log_size = 0
        try:
            while not execution_task.done():
                # Check for new log entries
                if len(agent.log) > last_log_size:
                    # Display new log entries
                    for i in range(last_log_size, len(agent.log)):
                        if i not in self.displayed_log_indices:
                            await self._display_log_entry(agent.log[i])
                            self.displayed_log_indices.add(i)
                    last_log_size = len(agent.log)
                
                await asyncio.sleep(0.1)  # Check every 100ms
        except asyncio.CancelledError:
            # Monitoring cancelled
            pass

    async def _display_pending_logs(self, agent) -> None:
        """Display any remaining log entries that weren't displayed yet.
        
        Args:
            agent: Agent instance
        """
        if not agent or not agent.log:
            return
        
        for i, log_entry in enumerate(agent.log):
            if i not in self.displayed_log_indices:
                await self._display_log_entry(log_entry)
                self.displayed_log_indices.add(i)

    async def _display_log_entry(self, log_entry: dict) -> None:
        """Display a log entry in the chat widget.
        
        Args:
            log_entry: Log entry dictionary
        """
        if not self.chat_widget:
            return
        
        step_type = log_entry.get("step_type")
        
        if step_type == "reasoning":
            await self._display_reasoning(log_entry)
        elif step_type == "tool_execution":
            await self._display_tool_execution(log_entry)

    async def _display_reasoning(self, log_entry: dict) -> None:
        """Display reasoning step in chat.
        
        Args:
            log_entry: Reasoning log entry
        """
        if not self.chat_widget:
            return
        
        reasoning_data = log_entry.get("agent_reasoning", {})
        if isinstance(reasoning_data, str):
            try:
                import json
                reasoning_data = json.loads(reasoning_data)
            except (json.JSONDecodeError, TypeError):
                reasoning_data = {}
        
        # Format reasoning for display (simplified, like KODA)
        reasoning_steps = reasoning_data.get("reasoning_steps", [])
        current_situation = reasoning_data.get("current_situation", "")
        remaining_steps = reasoning_data.get("remaining_steps", [])
        next_step = remaining_steps[0] if remaining_steps else None
        
        # Show reasoning steps if available, otherwise show current situation
        if reasoning_steps:
            content_parts = []
            for step in reasoning_steps[:3]:  # Limit to first 3 steps
                content_parts.append(f"• {step}")
            content = "\n".join(content_parts)
        elif current_situation:
            content = current_situation[:300] + "..." if len(current_situation) > 300 else current_situation
        elif next_step:
            content = f"Следующий шаг: {next_step}"
        else:
            content = "Обработка..."
        
        reasoning_message = Message(
            role=MessageRole.ASSISTANT,
            content=content
        )
        self.chat_widget.add_message(reasoning_message)

    async def _display_tool_execution(self, log_entry: dict) -> None:
        """Display tool execution in chat.
        
        Args:
            log_entry: Tool execution log entry
        """
        if not self.chat_widget:
            return
        
        tool_name = log_entry.get("tool_name", "unknown")
        tool_context = log_entry.get("agent_tool_context", {})
        result = log_entry.get("agent_tool_execution_result", "")
        
        # Determine status - check if result indicates error
        is_error = False
        if isinstance(result, str):
            result_lower = result.lower()
            is_error = any(keyword in result_lower for keyword in [
                "error", "failed", "exception", "ошибка", "не удалось", 
                "requires", "требуется", "authentication", "аутентификация"
            ])
        
        # Format tool execution for display (similar to KODA style)
        status_icon = "✗" if is_error else "✓"
        status_color = "error" if is_error else "success"
        
        # Extract query/arguments for display
        query = tool_context.get("query") or tool_context.get("research_goal") or tool_context.get("url") or ""
        if isinstance(query, dict):
            query = str(query)
        
        # Format as: icon ToolName {"key": "value"}
        args_str = ""
        if tool_context:
            display_args = {k: v for k, v in tool_context.items() 
                          if k not in ["tool_name", "type"] and v}
            if display_args:
                import json
                try:
                    args_str = json.dumps(display_args, ensure_ascii=False, indent=0)
                    if len(args_str) > 200:
                        args_str = args_str[:200] + "..."
                except (TypeError, ValueError):
                    args_str = str(display_args)[:200]
        
        content_parts = [f"{status_icon} {tool_name}"]
        if args_str:
            content_parts.append(args_str)
        
        # Add error message if present
        if is_error and result:
            error_msg = result[:200] + "..." if len(result) > 200 else result
            content_parts.append(f"\n{error_msg}")
        
        content = " ".join(content_parts) if len(content_parts) == 2 else "\n".join(content_parts)
        
        tool_message = Message(
            role=MessageRole.TOOL,
            content=content,
            tool_name=tool_name,
            tool_arguments=tool_context,
            tool_result=result
        )
        self.chat_widget.add_message(tool_message)
        
        # Also update tools widget in real-time
        if self.tools_widget and self.agent_manager:
            tools = self.agent_manager.get_tool_executions()
            self.tools_widget.update_tool_executions(tools)

    def on_tools_list_widget_tool_selected(self, event: ToolsListWidget.ToolSelected) -> None:
        """Handle tool selection.

        Args:
            event: Tool selected event
        """
        tool_exec = event.tool_exec
        # Show tool details in a modal or status
        details = f"Tool: {tool_exec.tool_name}\nArguments: {json.dumps(tool_exec.arguments, indent=2)}\nResult: {tool_exec.result[:200]}..."
        self.update_status(f"Selected: {tool_exec.tool_name}")

    async def on_chat_widget_agent_change_requested(self, event: ChatWidget.AgentChangeRequested) -> None:
        """Handle agent change request.

        Args:
            event: Agent change requested event
        """
        agent_name = event.agent_name
        if not self.agent_config or agent_name not in self.agent_config.agents:
            error_msg = Message(
                role=MessageRole.SYSTEM,
                content=f"Agent '{agent_name}' not found. Available agents: {', '.join(self.agent_config.agents.keys()) if self.agent_config else 'none'}"
            )
            self.chat_widget.add_message(error_msg)
            return

        # Reset agent manager with new agent
        self.agent_name = agent_name
        self.agent_manager = AgentManager(self.agent_config, agent_name)
        
        # Clear current conversation if agent was already created
        if self.agent_manager.agent:
            self.agent_manager.agent = None

        success_msg = Message(
            role=MessageRole.SYSTEM,
            content=f"Switched to agent: {agent_name}"
        )
        self.chat_widget.add_message(success_msg)
        self.update_status(f"Agent changed to: {agent_name}")

    async def on_chat_widget_list_agents_requested(self, event: ChatWidget.ListAgentsRequested) -> None:
        """Handle list agents request.

        Args:
            event: List agents requested event
        """
        if not self.agent_config or not self.agent_config.agents:
            error_msg = Message(
                role=MessageRole.SYSTEM,
                content="No agents configured."
            )
            self.chat_widget.add_message(error_msg)
            return

        agents_list = list(self.agent_config.agents.keys())
        current_agent = self.agent_manager.agent_name if self.agent_manager else None
        
        agents_info = "Available agents:\n"
        for i, name in enumerate(agents_list, 1):
            marker = " (current)" if name == current_agent else ""
            agents_info += f"  {i}. {name}{marker}\n"
        agents_info += f"\nUse '/agent <name>' to switch agents."

        list_msg = Message(
            role=MessageRole.SYSTEM,
            content=agents_info
        )
        self.chat_widget.add_message(list_msg)

    def toggle_tools_panel(self) -> None:
        """Toggle tools panel visibility."""
        self.tools_panel_visible = not self.tools_panel_visible
        tools_container = self.query_one("#tools-container")
        if self.tools_panel_visible:
            tools_container.add_class("visible")
            self.update_status("Tools panel shown | Ctrl+T to hide")
        else:
            tools_container.remove_class("visible")
            self.update_status("Tools panel hidden | Ctrl+T to show")

    def toggle_history_panel(self) -> None:
        """Toggle history panel visibility."""
        self.history_panel_visible = not self.history_panel_visible
        history_container = self.query_one("#history-container")
        if self.history_panel_visible:
            history_container.add_class("visible")
            self.update_status("History panel shown | Ctrl+H to hide")
        else:
            history_container.remove_class("visible")
            self.update_status("History panel hidden | Ctrl+H to show")

    def action_toggle_tools(self) -> None:
        """Action to toggle tools panel (Ctrl+T)."""
        self.toggle_tools_panel()

    def action_toggle_history(self) -> None:
        """Action to toggle history panel (Ctrl+H)."""
        self.toggle_history_panel()

    def action_quit(self) -> None:
        """Quit the application."""
        if self.streaming_task and not self.streaming_task.done():
            self.streaming_task.cancel()
        self.exit()

    async def _update_processing_status(self) -> None:
        """Update processing status with elapsed time."""
        try:
            while self.processing_start_time is not None:
                elapsed = int(asyncio.get_event_loop().time() - self.processing_start_time)
                self.update_status(f"Обрабатываю ваш запрос... (Esc для отмены), {elapsed} сек")
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    def action_escape(self) -> None:
        """Handle Escape key press."""
        if self.streaming_task and not self.streaming_task.done():
            # Cancel execution
            if self.execution_task and not self.execution_task.done():
                self.execution_task.cancel()
            self.streaming_task.cancel()
            self.processing_start_time = None
            if self.status_update_task and not self.status_update_task.done():
                self.status_update_task.cancel()

    def on_key(self, event: Key) -> None:
        """Handle keyboard shortcuts."""
        # Esc - Cancel ongoing request (handled by action_escape)
        if event.key == "escape":
            self.action_escape()
            return
        
        # Ctrl+T - Toggle tools panel
        if event.key == "t" and event.ctrl:
            self.action_toggle_tools()
            return
        # Ctrl+H - Toggle history panel
        elif event.key == "h" and event.ctrl:
            self.action_toggle_history()
            return
        # Let other keys be handled normally by Textual
        # Don't call super() - just let the event propagate naturally


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="SGR CLI - Textual UI for SGR Agent Core",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Load from single config file
  %(prog)s --config config.yaml

  # Load from config.yaml + agents.yaml
  %(prog)s --config config.yaml --agents agents.yaml

  # With CLI config and specific agent
  %(prog)s --config config.yaml --agents agents.yaml --cli-config cli.yaml --agent sgr_agent
        """,
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to main agent config YAML (config.yaml)",
    )
    parser.add_argument(
        "--agents",
        type=Path,
        dest="agents_config",
        help="Path to agents config YAML (agents.yaml). Agents will be merged with config.yaml",
    )
    parser.add_argument(
        "--cli-config",
        type=Path,
        help="Path to CLI config YAML (cli.yaml)",
    )
    parser.add_argument(
        "--agent",
        type=str,
        help="Agent name to use (if not specified, first agent from config will be used)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        help="Path to log file. If not specified, logs go to console only.",
    )

    args = parser.parse_args()

    # Setup logging
    log_level = getattr(logging, args.log_level.upper())
    
    # Configure logging handlers
    handlers = []
    
    # Only log to file to avoid interfering with Textual UI
    # Console logging is disabled because it interferes with Textual's terminal UI
    if args.log_file:
        file_handler = logging.FileHandler(args.log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        handlers.append(file_handler)
        logger.info(f"Logging to file: {args.log_file}")
    else:
        # If no log file specified, use NullHandler to suppress all logging
        # This prevents logs from interfering with Textual UI
        handlers.append(logging.NullHandler())
    
    logging.basicConfig(
        level=log_level,
        handlers=handlers,
        force=True  # Override any existing configuration
    )

    # Run app
    app = SGRCLIApp(
        agent_config_path=args.config,
        cli_config_path=args.cli_config,
        agents_config_path=args.agents_config,
        agent_name=args.agent,
    )
    app.run()


if __name__ == "__main__":
    main()
