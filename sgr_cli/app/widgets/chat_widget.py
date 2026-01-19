"""Chat widget for displaying messages and streaming responses."""

import json
from pathlib import Path
from typing import Optional

from textual import events
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.widgets import Input, Markdown, Static
from textual.widget import Widget

from ..models import Message, MessageRole
from ..utils import is_base64_image, is_image_url


def get_event_type(message: Message) -> str:
    """Get event type string for message.
    
    Args:
        message: Message to get event type for
        
    Returns:
        Event type string (clarification, tool_call, streaming, or role name)
    """
    if message.clarification_questions:
        return "clarification"
    elif message.tool_name:
        return "tool_call"
    else:
        return message.role.value


class MessageWidget(Widget):
    """Widget for displaying a single message."""

    def __init__(self, message: Message, **kwargs):
        """Initialize message widget.

        Args:
            message: Message to display
            **kwargs: Additional widget arguments
        """
        super().__init__(**kwargs)
        self.message = message
        self.event_type = get_event_type(message)

    def compose(self) -> ComposeResult:
        """Compose message widget."""
        role_class = f"message-{self.message.role.value}"
        
        # Create container with border title showing event type
        with Container(classes=role_class):
            if self.message.tool_name:
                yield Static(f"Tool: {self.message.tool_name}", classes="tool-name")
            if self.message.clarification_questions:
                with Container(classes="clarification"):
                    yield Static("Clarification needed:", classes="clarification-header")
                    for i, question in enumerate(self.message.clarification_questions, 1):
                        yield Static(f"{i}. {question}", classes="clarification-question")
            # Display images if present
            if self.message.images:
                with Container(classes="images-container"):
                    yield Static("Images:", classes="images-label")
                    for img in self.message.images:
                        if is_image_url(img):
                            yield Static(f"  📷 URL: {img}", classes="image-info")
                        elif is_base64_image(img):
                            yield Static("  📷 [Base64 Image]", classes="image-info")
                        else:
                            img_path = Path(img)
                            if img_path.exists():
                                yield Static(f"  📷 File: {img_path.name}", classes="image-info")
                            else:
                                yield Static(f"  📷 {img}", classes="image-info")
            # Use Static for empty content, Markdown for non-empty content
            if self.message.content:
                yield Markdown(self.message.content, classes="message-content")
            else:
                yield Static("(empty message)", classes="message-content")
    
    def on_mount(self) -> None:
        """Set border title after mounting."""
        role_class = f"message-{self.message.role.value}"
        container = self.query_one(f".{role_class}")
        container.border_title = self.event_type.upper()


class ChatWidget(Widget):
    """Chat widget for displaying conversation."""

    DEFAULT_CSS = """
    ChatWidget {
        height: 1fr;
        layout: vertical;
    }

    .chat-messages {
        height: 1fr;
        overflow-y: auto;
        padding: 0;
        layout: vertical;
    }

    MessageWidget {
        width: 1fr;
        min-height: 3;
        height: auto;
    }

    .message-user {
        margin: 1 0;
        padding: 1;
        background: $surface;
        border: solid $primary;
        border-title-align: left;
        width: 1fr;
        min-height: 3;
        height: auto;
    }

    .message-assistant {
        margin: 1 0;
        padding: 1;
        background: $panel;
        border: solid $accent;
        border-title-align: left;
        width: 1fr;
        min-height: 3;
        height: auto;
    }

    .message-tool {
        margin: 1 0;
        padding: 1;
        background: $background;
        border: solid $warning;
        border-title-align: left;
        width: 1fr;
        min-height: 3;
        height: auto;
    }

    .message-system {
        margin: 1 0;
        padding: 1;
        background: $background;
        border: solid $accent;
        border-title-align: left;
        text-align: center;
        width: 1fr;
        min-height: 3;
        height: auto;
    }

    .message-system .message-content {
        text-align: center;
        color: $accent;
        text-style: bold;
    }

    .tool-name {
        color: $warning;
        text-style: italic;
        margin: 1 0;
    }

    .clarification {
        margin: 1 0;
        padding: 1;
        background: $warning;
        border: solid $error;
    }

    .clarification-header {
        text-style: bold;
        color: $error;
        margin-bottom: 1;
    }

    .clarification-question {
        margin-left: 2;
        color: $text;
    }

    .message-content {
        margin-top: 1;
        width: 1fr;
    }
    
    .message-content Markdown {
        width: 1fr;
    }
    
    .message-content Static {
        width: 1fr;
    }

    .images-container {
        margin: 1 0;
        padding: 1;
        background: $background;
        border: solid $accent;
    }

    .images-label {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    .image-info {
        color: $text-muted;
        margin-left: 2;
    }

    .chat-input-container {
        height: 3;
        dock: bottom;
        padding: 0;
        background: $background;
        border: round $primary;
        border-title-align: left;
    }

    .chat-input-container:focus-within {
        border: round $accent;
    }

    .input-wrapper {
        layout: horizontal;
        height: 1fr;
        padding: 0 1;
        align: center middle;
    }

    .input-prefix {
        width: 1;
        text-align: right;
        color: $accent;
        text-style: bold;
        margin-right: 1;
    }

    .chat-input-container:focus-within .input-prefix {
        color: $secondary;
    }

    #chat-input {
        width: 1fr;
        background: transparent;
        color: $text;
        border: none;
        padding: 0;
        margin: 0;
    }

    #chat-input:focus {
        background: transparent;
        color: $text;
        border: none;
    }

    .streaming-indicator {
        color: $accent;
        text-style: italic;
    }
    """
    WATCH_CSS = True


    def __init__(self, **kwargs):
        """Initialize chat widget."""
        super().__init__(**kwargs)
        self.messages: list[Message] = []
        self.current_streaming_content = ""
        self.streaming_widget: Optional[Widget] = None
        self.streaming_container: Optional[Widget] = None
        self.pending_images: list[str] = []

    def compose(self) -> ComposeResult:
        """Compose chat widget."""
        with ScrollableContainer(classes="chat-messages"):
            pass
        with Container(classes="chat-input-container"):
            with Horizontal(classes="input-wrapper"):
                yield Static(">", classes="input-prefix")
                yield Input(
                    placeholder="Type message, /image <path>, /agent <name>, or /agents to list...",
                    id="chat-input",
                    type="text",
                )

    def on_mount(self) -> None:
        """Called when widget is mounted."""
        # CSS :focus-within will handle the styling automatically
        pass

    def add_message(self, message: Message) -> None:
        """Add a message to the chat.

        Args:
            message: Message to add
        """
        self.messages.append(message)
        messages_container = self.query_one(".chat-messages")
        message_widget = MessageWidget(message)
        try:
            messages_container.mount(message_widget)
            # Force refresh and layout recalculation
            messages_container.refresh(layout=True)
            # Ensure the widget is visible
            message_widget.display = True
            self.scroll_to_end()
        except Exception as e:
            # Fallback: try to add message content directly as Static
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error mounting message widget: {e}")
            # Try simple fallback
            try:
                content_text = message.content[:100] if message.content else "(empty)"
                fallback_widget = Static(f"[{message.role.value.upper()}] {content_text}")
                messages_container.mount(fallback_widget)
                messages_container.refresh(layout=True)
                self.scroll_to_end()
            except Exception as e2:
                logger.error(f"Fallback also failed: {e2}")

    def start_streaming(self, role: MessageRole = MessageRole.ASSISTANT) -> None:
        """Start streaming a message.

        Args:
            role: Role of the streaming message
        """
        self.current_streaming_content = ""
        messages_container = self.query_one(".chat-messages")

        # Create streaming widget - mount container first, then mount children
        streaming_container = Container(classes=f"message-{role.value}")
        streaming_container.border_title = "streaming".upper()
        messages_container.mount(streaming_container)
        self.streaming_container = streaming_container
        
        # Now mount children after container is mounted
        streaming_markdown = Markdown("", classes="message-content streaming-indicator")
        streaming_container.mount(streaming_markdown)

        self.streaming_widget = streaming_markdown
        self.scroll_to_end()

    def append_streaming_content(self, content: str) -> None:
        """Append content to streaming message.

        Args:
            content: Content to append
        """
        if not content:
            return
        self.current_streaming_content += content
        if self.streaming_widget:
            # Markdown widget update should work, but ensure content is not empty
            if self.current_streaming_content.strip():
                self.streaming_widget.update(self.current_streaming_content)
            self.scroll_to_end()

    def finish_streaming(self) -> Message:
        """Finish streaming and create message.

        Returns:
            Created message
        """
        message = Message(
            role=MessageRole.ASSISTANT,
            content=self.current_streaming_content,
        )
        
        # Update container title to show final event type
        if self.streaming_container:
            event_type = get_event_type(message)
            self.streaming_container.border_title = event_type.upper()
        
        self.current_streaming_content = ""
        self.streaming_widget = None
        self.streaming_container = None
        return message

    def add_clarification_questions(self, questions: list[str]) -> None:
        """Add clarification questions to chat.

        Args:
            questions: List of clarification questions
        """
        message = Message(
            role=MessageRole.ASSISTANT,
            content="",
            clarification_questions=questions,
        )
        self.add_message(message)

    def scroll_to_end(self) -> None:
        """Scroll chat to the end."""
        messages_container = self.query_one(".chat-messages")
        messages_container.scroll_end(animate=False)


    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        if event.input.id == "chat-input":
            value = event.input.value.strip()
            if value:
                # Check for /image command
                if value.startswith("/image "):
                    image_path = value[7:].strip()
                    if image_path:
                        self.pending_images.append(image_path)
                        event.input.value = ""
                        event.input.placeholder = f"Image added: {Path(image_path).name}. Type message..."
                        event.input.focus()
                        return
                    else:
                        # Clear pending images
                        self.pending_images.clear()
                        event.input.value = ""
                        event.input.placeholder = "Type message, /image <path>, /agent <name>, or /agents to list..."
                        event.input.focus()
                        return

                # Check for /agent command
                if value.startswith("/agent "):
                    agent_name = value[7:].strip()
                    if agent_name:
                        event.input.value = ""
                        event.input.focus()
                        # Emit agent change event
                        self.post_message(self.AgentChangeRequested(agent_name))
                        return

                # Check for /agents command (list agents)
                if value == "/agents" or value == "/list":
                    event.input.value = ""
                    event.input.focus()
                    self.post_message(self.ListAgentsRequested())
                    return

                # Create message with images if any
                message = Message(
                    role=MessageRole.USER,
                    content=value,
                    images=self.pending_images.copy() if self.pending_images else [],
                )
                self.add_message(message)
                event.input.value = ""
                self.pending_images.clear()
                event.input.placeholder = "Type message, /image <path>, /agent <name>, or /agents to list..."
                # Keep focus on input after sending
                event.input.focus()
                # Emit event for app to handle
                self.post_message(self.MessageSubmitted(message))

    class MessageSubmitted(events.Message):
        """Message submitted event."""

        def __init__(self, message: Message):
            """Initialize message submitted event.

            Args:
                message: Submitted message
            """
            super().__init__()
            self.message = message

    class AgentChangeRequested(events.Message):
        """Agent change requested event."""

        def __init__(self, agent_name: str):
            """Initialize agent change requested event.

            Args:
                agent_name: Name of agent to switch to
            """
            super().__init__()
            self.agent_name = agent_name

    class ListAgentsRequested(events.Message):
        """List agents requested event."""

        def __init__(self):
            """Initialize list agents requested event."""
            super().__init__()
