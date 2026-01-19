"""History widget for displaying conversation history."""

from textual import events
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import ListView, ListItem, Label, Static

from ..models import Message


class HistoryWidget(Widget):
    """Widget for displaying conversation history."""

    DEFAULT_CSS = """
    HistoryWidget {
        height: 1fr;
        layout: vertical;
    }

    .history-header {
        height: 3;
        text-align: center;
        background: $surface;
        border-bottom: solid $primary;
    }

    .history-list {
        height: 1fr;
    }

    .history-item {
        padding: 1;
        margin: 1;
    }

    .history-item-user {
        background: $surface;
    }

    .history-item-assistant {
        background: $panel;
    }
    """

    def __init__(self, **kwargs):
        """Initialize history widget."""
        super().__init__(**kwargs)
        self.history: list[Message] = []
        self.max_items = 100

    def compose(self) -> ComposeResult:
        """Compose history widget."""
        yield Static("History", classes="history-header")
        yield ListView(id="history-list", classes="history-list")

    def add_message(self, message: Message) -> None:
        """Add a message to history.

        Args:
            message: Message to add
        """
        self.history.append(message)
        if len(self.history) > self.max_items:
            self.history.pop(0)

        list_view = self.query_one("#history-list")
        preview = message.content[:50] + "..." if len(message.content) > 50 else message.content
        item_label = f"[{message.role.value.upper()}] {preview}"
        item = ListItem(Label(item_label), id=f"msg-{len(self.history)}")
        list_view.append(item)

    def clear_history(self) -> None:
        """Clear history."""
        self.history.clear()
        list_view = self.query_one("#history-list")
        list_view.clear()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle history item selection."""
        if event.item and event.item.id:
            index = int(event.item.id.replace("msg-", "")) - 1
            if 0 <= index < len(self.history):
                message = self.history[index]
                self.post_message(self.HistoryItemSelected(message))

    class HistoryItemSelected(events.Message):
        """History item selected event."""

        def __init__(self, message: Message):
            """Initialize history item selected event.

            Args:
                message: Selected message
            """
            super().__init__()
            self.message = message
