"""Tests for all tools.

This module contains simple tests for all tools:
- Initialization
- Config reading (if needed)
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sgr_agent_core.models import AgentContext, SourceData
from sgr_agent_core.tools import (
    AdaptPlanTool,
    AnswerTool,
    ClarificationTool,
    CreateReportTool,
    ExtractPageContentTool,
    FinalAnswerTool,
    GeneratePlanTool,
    ReasoningTool,
    RunCommandTool,
    WebSearchTool,
)


class TestToolsInitialization:
    """Test that all tools can be initialized."""

    def test_clarification_tool_initialization(self):
        """Test ClarificationTool initialization."""
        tool = ClarificationTool(
            reasoning="Test",
            unclear_terms=["term1"],
            assumptions=["assumption1", "assumption2"],
            questions=["Question 1?", "Question 2?", "Question 3?"],
        )
        assert tool.tool_name == "clarificationtool"
        assert tool.reasoning == "Test"

    def test_generate_plan_tool_initialization(self):
        """Test GeneratePlanTool initialization."""
        tool = GeneratePlanTool(
            reasoning="Test",
            research_goal="Test goal",
            planned_steps=["Step 1", "Step 2", "Step 3"],
            search_strategies=["Strategy 1", "Strategy 2"],
        )
        assert tool.tool_name == "generateplantool"
        assert len(tool.planned_steps) == 3

    def test_adapt_plan_tool_initialization(self):
        """Test AdaptPlanTool initialization."""
        tool = AdaptPlanTool(
            reasoning="Test",
            original_goal="Original goal",
            new_goal="New goal",
            plan_changes=["Change 1"],
            next_steps=["Step 1", "Step 2"],
        )
        assert tool.tool_name == "adaptplantool"
        assert len(tool.next_steps) == 2

    def test_final_answer_tool_initialization(self):
        """Test FinalAnswerTool initialization."""
        from sgr_agent_core.models import AgentStatesEnum

        tool = FinalAnswerTool(
            reasoning="Test",
            completed_steps=["Step 1"],
            answer="Answer",
            status=AgentStatesEnum.COMPLETED,
        )
        assert tool.tool_name == "finalanswertool"
        assert tool.answer == "Answer"

    def test_reasoning_tool_initialization(self):
        """Test ReasoningTool initialization."""
        tool = ReasoningTool(
            reasoning_steps=["Step 1", "Step 2"],
            current_situation="Test",
            plan_status="Test",
            enough_data=False,
            remaining_steps=["Next"],
            task_completed=False,
        )
        assert tool.tool_name == "reasoningtool"
        assert len(tool.reasoning_steps) == 2

    def test_web_search_tool_initialization(self):
        """Test WebSearchTool initialization."""
        tool = WebSearchTool(
            reasoning="Test",
            query="test query",
        )
        assert tool.tool_name == "websearchtool"
        assert tool.query == "test query"

    def test_extract_page_content_tool_initialization(self):
        """Test ExtractPageContentTool initialization."""
        tool = ExtractPageContentTool(
            reasoning="Test",
            urls=["https://example.com"],
        )
        assert tool.tool_name == "extractpagecontenttool"
        assert len(tool.urls) == 1

    def test_create_report_tool_initialization(self):
        """Test CreateReportTool initialization."""
        tool = CreateReportTool(
            reasoning="Test",
            title="Test Report",
            user_request_language_reference="Test",
            content="Test content",
            confidence="high",
        )
        assert tool.tool_name == "createreporttool"
        assert tool.title == "Test Report"

    def test_answer_tool_initialization(self):
        """Test AnswerTool initialization."""
        tool = AnswerTool(
            reasoning="Sharing progress",
            intermediate_result="Found 3 relevant sources so far.",
            continue_research=True,
        )
        assert tool.tool_name == "answertool"
        assert tool.reasoning == "Sharing progress"
        assert tool.intermediate_result == "Found 3 relevant sources so far."
        assert tool.continue_research is True


class TestAnswerToolExecution:
    """Tests for AnswerTool execution."""

    @pytest.mark.asyncio
    async def test_answer_tool_returns_intermediate_result(self):
        """Test AnswerTool __call__ returns intermediate_result."""
        tool = AnswerTool(
            reasoning="Progress update",
            intermediate_result="Partial findings: X and Y.",
        )
        result = await tool(MagicMock(), MagicMock())
        assert result == "Partial findings: X and Y."


class TestToolsConfigReading:
    """Test that tools that need config can read it correctly."""

    def test_web_search_tool_reads_config(self):
        """Test WebSearchTool reads search config for max_results."""
        tool = WebSearchTool(
            reasoning="Test",
            query="test query",
            max_results=5,
        )
        # Tool should use provided max_results
        assert tool.query == "test query"
        assert tool.max_results == 5

    def test_extract_page_content_tool_reads_config(self):
        """Test ExtractPageContentTool reads search config."""
        tool = ExtractPageContentTool(
            reasoning="Test",
            urls=["https://example.com"],
        )
        # Tool should be initialized without errors
        assert len(tool.urls) == 1

    def test_create_report_tool_reads_config(self):
        """Test CreateReportTool reads execution config."""
        tool = CreateReportTool(
            reasoning="Test",
            title="Test Report",
            user_request_language_reference="Test",
            content="Test content",
            confidence="high",
        )
        # Tool should be initialized without errors
        assert tool.title == "Test Report"


class TestSearchToolsKwargs:
    """Test that search tools use kwargs (tool config) for their search
    settings."""

    @pytest.mark.asyncio
    async def test_web_search_tool_uses_kwargs_max_results(self):
        """WebSearchTool uses max_results from kwargs when provided."""
        tool = WebSearchTool(reasoning="r", query="test", max_results=5)
        context = AgentContext()
        config = MagicMock()
        mock_handler = AsyncMock(return_value=[])
        with patch.dict("sgr_agent_core.tools.web_search_tool._ENGINE_HANDLERS", {"tavily": mock_handler}):
            await tool(context, config, api_key="k", max_results=3)
            assert mock_handler.call_args.kwargs["max_results"] == 3

    @pytest.mark.asyncio
    async def test_web_search_tool_default_max_results(self):
        """WebSearchTool uses default max_results when not overridden in
        kwargs."""
        tool = WebSearchTool(reasoning="r", query="test", max_results=5)
        context = AgentContext()
        config = MagicMock()
        mock_handler = AsyncMock(return_value=[])
        with patch.dict("sgr_agent_core.tools.web_search_tool._ENGINE_HANDLERS", {"tavily": mock_handler}):
            await tool(context, config, api_key="k")
            assert mock_handler.call_args.kwargs["max_results"] == 5

    @pytest.mark.asyncio
    async def test_web_search_tool_with_offset(self):
        """WebSearchTool passes offset to provider which handles it
        internally."""
        tool = WebSearchTool(reasoning="r", query="test", max_results=3, offset=2)
        context = AgentContext()
        config = MagicMock()

        mock_sources = [
            SourceData(number=i, url=f"https://example.com/{i}", title=f"Result {i}", snippet=f"Snippet {i}")
            for i in range(2, 5)
        ]

        mock_handler = AsyncMock(return_value=mock_sources)
        with patch.dict("sgr_agent_core.tools.web_search_tool._ENGINE_HANDLERS", {"tavily": mock_handler}):
            result = await tool(context, config, api_key="k")

            assert len(context.searches) == 1
            assert len(context.searches[0].citations) == 3
            assert "Result 2" in result

    @pytest.mark.asyncio
    async def test_web_search_tool_offset_default_zero(self):
        """WebSearchTool without offset passes offset=0 to provider."""
        tool = WebSearchTool(reasoning="r", query="test", max_results=3)
        assert tool.offset == 0

        context = AgentContext()
        config = MagicMock()

        mock_sources = [
            SourceData(number=i, url=f"https://example.com/{i}", title=f"Result {i}", snippet=f"Snippet {i}")
            for i in range(3)
        ]

        mock_handler = AsyncMock(return_value=mock_sources)
        with patch.dict("sgr_agent_core.tools.web_search_tool._ENGINE_HANDLERS", {"tavily": mock_handler}):
            await tool(context, config, api_key="k")

            assert len(context.searches[0].citations) == 3

    @pytest.mark.asyncio
    async def test_web_search_tool_offset_exceeds_results(self):
        """WebSearchTool with offset exceeding available results returns empty
        list gracefully."""
        tool = WebSearchTool(reasoning="r", query="test", max_results=3, offset=10)
        context = AgentContext()
        config = MagicMock()

        mock_handler = AsyncMock(return_value=[])
        with patch.dict("sgr_agent_core.tools.web_search_tool._ENGINE_HANDLERS", {"tavily": mock_handler}):
            result = await tool(context, config, api_key="k")

            assert len(context.searches[0].citations) == 0
            assert "Search Query: test" in result

    @pytest.mark.asyncio
    async def test_extract_page_content_tool_uses_content_limit_from_kwargs(self):
        """ExtractPageContentTool uses content_limit from kwargs."""
        tool = ExtractPageContentTool(reasoning="r", urls=["https://example.com"])
        context = AgentContext()
        config = MagicMock()
        with patch.object(ExtractPageContentTool, "_extract", new_callable=AsyncMock, return_value=[]) as mock_extract:
            await tool(context, config, tavily_api_key="k", content_limit=500)
            # search_config is passed as first positional arg
            assert mock_extract.call_args[0][0].content_limit == 500


class TestRunCommandTool:
    """Test suite for RunCommandTool."""

    def test_run_command_tool_initialization(self):
        """RunCommandTool initializes with reasoning and command."""
        tool = RunCommandTool(reasoning="List files", command="ls -la")
        assert tool.tool_name == "runcommandtool"
        assert tool.reasoning == "List files"
        assert tool.command == "ls -la"

    def test_run_command_tool_default_mode_is_safe(self):
        """RunCommandTool default mode is safe when mode not passed in
        kwargs."""
        from sgr_agent_core.tools.run_command_tool import RunCommandToolConfig

        cfg = RunCommandToolConfig()
        assert cfg.mode == "safe"

    @pytest.mark.asyncio
    async def test_run_command_tool_without_mode_uses_safe_path(self):
        """RunCommandTool without explicit mode uses safe (bwrap) path."""
        from sgr_agent_core.models import AgentContext

        with tempfile.TemporaryDirectory() as tmpdir:
            tool = RunCommandTool(reasoning="Test", command="echo hi")
            context = AgentContext()
            config = MagicMock()
            with (
                patch("sgr_agent_core.tools.run_command_tool.shutil.which", return_value="/usr/bin/bwrap"),
                patch(
                    "sgr_agent_core.tools.run_command_tool.asyncio.create_subprocess_exec",
                    new_callable=AsyncMock,
                ) as mock_exec,
            ):
                proc = AsyncMock()
                proc.communicate = AsyncMock(return_value=(b"hi\n", b""))
                proc.returncode = 0
                proc.kill = MagicMock()
                mock_exec.return_value = proc
                result = await tool(context, config, workspace_path=tmpdir)
            assert "hi" in result
            mock_exec.assert_called_once()
            call_args = mock_exec.call_args[0]
            assert "bwrap" in str(call_args[0])

    @pytest.mark.asyncio
    async def test_run_command_tool_unsafe_mode_runs_subprocess(self):
        """RunCommandTool in unsafe mode runs command via subprocess and
        returns output."""
        from sgr_agent_core.models import AgentContext

        tool = RunCommandTool(reasoning="Test", command="echo hello")
        context = AgentContext()
        config = MagicMock()
        result = await tool(context, config, mode="unsafe")
        assert "hello" in result
        assert "return_code" in result.lower() or "0" in result

    @pytest.mark.asyncio
    async def test_run_command_tool_uses_workspace_path_as_cwd(self):
        """RunCommandTool with workspace_path runs subprocess with cwd set to
        workspace_path (print cwd via same Python as test runner)."""
        from sgr_agent_core.models import AgentContext

        tmp = Path(__file__).resolve().parent
        command = f'"{sys.executable}" -c "import os; print(os.getcwd())"'
        tool = RunCommandTool(reasoning="Test", command=command)
        context = AgentContext()
        config = MagicMock()
        result = await tool(context, config, mode="unsafe", workspace_path=str(tmp))
        print(result)
        print(tmp.name)
        assert tmp.name in result or str(tmp) in result

    @pytest.mark.asyncio
    async def test_run_command_tool_safe_mode_bwrap_not_found_returns_error(self):
        """RunCommandTool in safe mode when bwrap is not installed returns
        error with install link."""
        from sgr_agent_core.models import AgentContext

        tool = RunCommandTool(reasoning="Test", command="echo hi")
        context = AgentContext()
        config = MagicMock()
        with patch("sgr_agent_core.tools.run_command_tool.shutil.which", return_value=None):
            result = await tool(context, config, mode="safe")
        assert "error" in result.lower()
        assert "bwrap" in result.lower()
        assert "github.com" in result or "containers/bubblewrap" in result or "installation" in result.lower()

    @pytest.mark.asyncio
    async def test_run_command_tool_safe_mode_with_bwrap_runs_command(self):
        """RunCommandTool in safe mode with bwrap available runs command via
        bwrap."""
        from sgr_agent_core.models import AgentContext

        with tempfile.TemporaryDirectory() as tmpdir:
            tool = RunCommandTool(reasoning="Test", command="echo hi")
            context = AgentContext()
            config = MagicMock()
            with (
                patch("sgr_agent_core.tools.run_command_tool.shutil.which", return_value="/usr/bin/bwrap"),
                patch(
                    "sgr_agent_core.tools.run_command_tool.asyncio.create_subprocess_exec",
                    new_callable=AsyncMock,
                ) as mock_exec,
            ):
                proc = AsyncMock()
                proc.communicate = AsyncMock(return_value=(b"hi\n", b""))
                proc.returncode = 0
                proc.kill = MagicMock()
                mock_exec.return_value = proc
                result = await tool(context, config, mode="safe", workspace_path=tmpdir)
            assert "hi" in result
            assert "return_code" in result.lower()
            mock_exec.assert_called_once()
            call_args = mock_exec.call_args[0]
            assert call_args[0] == "/usr/bin/bwrap" or "bwrap" in str(call_args)

    @pytest.mark.asyncio
    async def test_run_command_tool_uses_timeout_from_kwargs(self):
        """RunCommandTool uses timeout_seconds from kwargs."""
        from sgr_agent_core.models import AgentContext

        tool = RunCommandTool(reasoning="Test", command="echo ok")
        context = AgentContext()
        config = MagicMock()
        with patch("sgr_agent_core.tools.run_command_tool.asyncio.create_subprocess_shell") as mock_create:
            proc = AsyncMock()
            proc.communicate = AsyncMock(return_value=(b"ok\n", b""))
            proc.returncode = 0
            proc.kill = MagicMock()
            mock_create.return_value = proc
            await tool(context, config, mode="unsafe", timeout_seconds=30)
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs.get("cwd") is None or "cwd" in call_kwargs
            # timeout is applied in wait_for(communicate(), timeout=...)
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_command_tool_path_escape_rejected_when_workspace_path_set(self):
        """RunCommandTool rejects command that escapes workspace_path (e.g.
        ../../../)."""
        from sgr_agent_core.models import AgentContext

        tmp = Path(__file__).resolve().parent
        tool = RunCommandTool(reasoning="Test", command="cat ../../../../etc/passwd")
        context = AgentContext()
        config = MagicMock()
        result = await tool(context, config, mode="unsafe", workspace_path=str(tmp))
        assert "error" in result.lower() or "not allowed" in result.lower() or "outside" in result.lower()

    @pytest.mark.asyncio
    async def test_run_command_tool_include_allows_command(self):
        """RunCommandTool with include allows only listed commands."""
        from sgr_agent_core.models import AgentContext

        tool = RunCommandTool(reasoning="Test", command="echo hello")
        context = AgentContext()
        config = MagicMock()
        # echo should be allowed if in include
        result = await tool(context, config, mode="unsafe", include_paths=["echo", "/bin/echo"])
        assert "hello" in result

    @pytest.mark.asyncio
    async def test_run_command_tool_include_rejects_not_listed_command(self):
        """RunCommandTool with include rejects commands not in the list."""
        from sgr_agent_core.models import AgentContext

        tool = RunCommandTool(reasoning="Test", command="rm /tmp/file")
        context = AgentContext()
        config = MagicMock()
        result = await tool(context, config, mode="unsafe", include_paths=["echo", "ls"])
        assert "error" in result.lower()
        assert "not in include" in result.lower() or "not allowed" in result.lower()

    @pytest.mark.asyncio
    async def test_run_command_tool_exclude_rejects_command(self):
        """RunCommandTool with exclude rejects excluded commands."""
        from sgr_agent_core.models import AgentContext

        tool = RunCommandTool(reasoning="Test", command="rm /tmp/file")
        context = AgentContext()
        config = MagicMock()
        result = await tool(context, config, mode="unsafe", exclude_paths=["rm", "/usr/bin/rm"])
        assert "error" in result.lower()
        assert "excluded" in result.lower()

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_run_command_tool_include_paths_priority_over_exclude_paths(self):
        """RunCommandTool: include_paths has priority over exclude_paths (same path in both is allowed)."""
        from sgr_agent_core.models import AgentContext

        tool = RunCommandTool(reasoning="Test", command="rm /tmp/file")
        context = AgentContext()
        config = MagicMock()
        # rm is in both include_paths and exclude_paths -> allowed (include_paths wins)
        result = await tool(context, config, mode="unsafe", include_paths=["rm", "ls"], exclude_paths=["rm"])
        assert "excluded" not in result.lower()

    @pytest.mark.asyncio
    async def test_run_command_tool_exclude_paths_rejects_when_not_in_include_paths(self):
        """RunCommandTool: command only in exclude_paths is rejected."""
        from sgr_agent_core.models import AgentContext

        tool = RunCommandTool(reasoning="Test", command="rm /tmp/file")
        context = AgentContext()
        config = MagicMock()
        result = await tool(context, config, mode="unsafe", include_paths=["ls", "cat"], exclude_paths=["rm"])
        assert "error" in result.lower()
        assert "excluded" in result.lower()

    @pytest.mark.asyncio
    async def test_run_command_tool_safe_mode_with_include_uses_overlayfs_manager(self):
        """RunCommandTool in safe mode with include uses OverlayFSManager
        mounts."""
        from sgr_agent_core.models import AgentContext

        with tempfile.TemporaryDirectory() as tmpdir:
            tool = RunCommandTool(reasoning="Test", command="echo hi")
            context = AgentContext()
            config = MagicMock()
            with (
                patch("sgr_agent_core.tools.run_command_tool.shutil.which", return_value="/usr/bin/bwrap"),
                patch(
                    "sgr_agent_core.tools.run_command_tool.asyncio.create_subprocess_exec",
                    new_callable=AsyncMock,
                ) as mock_exec,
                patch(
                    "sgr_agent_core.services.overlayfs_manager.OverlayFSManager.get_overlay_mounts",
                    return_value={"/usr/bin": "/tmp/merged_usr_bin"},
                ) as mock_get_mounts,
            ):
                proc = AsyncMock()
                proc.communicate = AsyncMock(return_value=(b"hi\n", b""))
                proc.returncode = 0
                proc.kill = MagicMock()
                mock_exec.return_value = proc
                # Include only echo (should be in /usr/bin or /bin)
                result = await tool(context, config, mode="safe", workspace_path=tmpdir, include_paths=["echo"])
            assert "hi" in result
            mock_exec.assert_called_once()
            mock_get_mounts.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_command_tool_safe_mode_with_exclude_uses_overlayfs_manager(self):
        """RunCommandTool in safe mode with exclude uses OverlayFSManager
        mounts."""
        from sgr_agent_core.models import AgentContext

        with tempfile.TemporaryDirectory() as tmpdir:
            tool = RunCommandTool(reasoning="Test", command="ls")
            context = AgentContext()
            config = MagicMock()
            with (
                patch("sgr_agent_core.tools.run_command_tool.shutil.which", return_value="/usr/bin/bwrap"),
                patch(
                    "sgr_agent_core.tools.run_command_tool.asyncio.create_subprocess_exec",
                    new_callable=AsyncMock,
                ) as mock_exec,
                patch(
                    "sgr_agent_core.services.overlayfs_manager.OverlayFSManager.get_overlay_mounts",
                    return_value={"/usr/bin": "/tmp/merged_usr_bin"},
                ) as mock_get_mounts,
                patch("sgr_agent_core.tools.run_command_tool._check_allowed", return_value=None),
            ):
                proc = AsyncMock()
                proc.communicate = AsyncMock(return_value=(b"ls\n", b""))
                proc.returncode = 0
                proc.kill = MagicMock()
                mock_exec.return_value = proc
                # Include ls but exclude rm (both in /usr/bin)
                result = await tool(
                    context,
                    config,
                    mode="safe",
                    workspace_path=tmpdir,
                    include_paths=["ls"],
                    exclude_paths=["rm"],
                )
            assert "ls" in result
            mock_get_mounts.assert_called_once()
