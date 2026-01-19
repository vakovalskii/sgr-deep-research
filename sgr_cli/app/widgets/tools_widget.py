"""Tools list widget for displaying tool executions."""

from textual import events
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable, Static

from ..models import ToolExecution


class ToolsListWidget(Widget):
    """Widget for displaying executed tools."""

    DEFAULT_CSS = """
    ToolsListWidget {
        height: 1fr;
        layout: vertical;
    }

    .tools-header {
        height: 3;
        text-align: center;
        background: $surface;
        border-bottom: solid $primary;
    }

    .tools-table {
        height: 1fr;
    }
    """

    def __init__(self, **kwargs):
        """Initialize tools list widget."""
        super().__init__(**kwargs)
        self.tools: list[ToolExecution] = []

    def compose(self) -> ComposeResult:
        """Compose tools widget."""
        yield Static("Executed Tools", classes="tools-header")
        table = DataTable(classes="tools-table")
        table.add_columns("Tool", "Status", "Iteration", "Time")
        yield table

    def add_tool_execution(self, tool_exec: ToolExecution) -> None:
        """Add a tool execution to the list.

        Args:
            tool_exec: Tool execution to add
        """
        self.tools.append(tool_exec)
        table = self.query_one(DataTable)
        table.add_row(
            tool_exec.tool_name,
            tool_exec.status,
            str(tool_exec.iteration),
            tool_exec.timestamp.strftime("%H:%M:%S"),
            key=str(len(self.tools)),
        )
        # Scroll to bottom
        if len(self.tools) > 0:
            table.move_cursor(row=len(self.tools) - 1, animate=False)

    def update_tool_executions(self, tools: list[ToolExecution]) -> None:
        """Update tool executions list.

        Args:
            tools: List of tool executions
        """
        self.tools = tools
        table = self.query_one(DataTable)
        table.clear()
        for tool_exec in tools:
            table.add_row(
                tool_exec.tool_name,
                tool_exec.status,
                str(tool_exec.iteration),
                tool_exec.timestamp.strftime("%H:%M:%S"),
                key=str(tool_exec.iteration),
            )
        if tools:
            table.move_cursor(row=len(tools) - 1, animate=False)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle tool row selection."""
        if event.cursor_row < len(self.tools):
            tool_exec = self.tools[event.cursor_row]
            # Emit event with tool details
            self.post_message(self.ToolSelected(tool_exec))

    class ToolSelected(events.Message):
        """Tool selected event."""

        def __init__(self, tool_exec: ToolExecution):
            """Initialize tool selected event.

            Args:
                tool_exec: Selected tool execution
            """
            super().__init__()
            self.tool_exec = tool_exec
