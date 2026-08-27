"""Tests for the optional-dependency (extras) split.

The core install ships only pydantic, PyYAML, openai and httpx. Everything
else -- MCP, Tavily, the HTTP server, ACP, Langfuse -- lives behind an extra
and must be imported lazily, so that:

* importing ``sgr_agent_core`` never pulls an optional package in, and
* using a feature whose extra is missing fails with an actionable message.
"""

import subprocess
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sgr_agent_core._optional import MissingDependencyError, install_hint, require
from sgr_agent_core.mcp_config import MCPConfig

OPTIONAL_ROOTS = ("fastmcp", "jambo", "tavily", "fastapi", "uvicorn", "acp", "langfuse")


class BlockImports:
    """Meta path finder that makes selected top-level packages unimportable."""

    def __init__(self, *roots: str) -> None:
        self.roots = set(roots)
        self._saved: dict[str, object] = {}

    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in self.roots:
            raise ImportError(f"blocked by test: {fullname}")
        return None

    def __enter__(self):
        for name in list(sys.modules):
            if name.split(".")[0] in self.roots:
                self._saved[name] = sys.modules.pop(name)
        sys.meta_path.insert(0, self)
        return self

    def __exit__(self, *exc_info):
        sys.meta_path.remove(self)
        sys.modules.update(self._saved)
        self._saved.clear()
        return False


class TestCoreImportIsLight:
    """``import sgr_agent_core`` must not load any optional dependency."""

    def test_import_does_not_load_optional_packages(self):
        code = (
            "import sys; import sgr_agent_core; "
            f"loaded = sorted(r for r in {OPTIONAL_ROOTS!r} if r in sys.modules); "
            "print(','.join(loaded))"
        )
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
        assert result.stdout.strip() == "", f"optional packages imported at module scope: {result.stdout.strip()}"

    def test_import_succeeds_with_optional_packages_blocked(self):
        """A core-only install can still import the package and build
        agents."""
        code = "\n".join(
            [
                "import sys",
                "class Block:",
                "    def find_spec(self, fullname, path=None, target=None):",
                f"        if fullname.split('.')[0] in {OPTIONAL_ROOTS!r}:",
                "            raise ImportError(fullname)",
                "        return None",
                "sys.meta_path.insert(0, Block())",
                "import sgr_agent_core",
                "from sgr_agent_core import AgentConfig, ToolRegistry, WebSearchTool",
                "assert AgentConfig().mcp.mcpServers == {}",
                "assert ToolRegistry.get(WebSearchTool.tool_name) is WebSearchTool",
                "print('ok')",
            ]
        )
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "ok"


class TestInstallHints:
    @pytest.mark.parametrize(
        "module,extra",
        [
            ("fastmcp", "mcp"),
            ("fastmcp.mcp_config", "mcp"),
            ("jambo", "mcp"),
            ("tavily", "search"),
            ("fastapi", "server"),
            ("uvicorn", "server"),
            ("acp", "acp"),
            ("langfuse", "langfuse"),
        ],
    )
    def test_hint_names_the_extra(self, module, extra):
        assert install_hint(module) == f"pip install 'sgr-agent-core[{extra}]'"

    def test_unknown_module_falls_back_to_its_own_name(self):
        assert install_hint("some_other_pkg") == "pip install 'some_other_pkg'"

    def test_require_raises_actionable_error(self):
        with BlockImports("tavily"):
            with pytest.raises(MissingDependencyError) as exc_info:
                require("tavily", feature="WebSearchTool")
        message = str(exc_info.value)
        assert "WebSearchTool" in message
        assert "sgr-agent-core[search]" in message

    def test_missing_dependency_error_is_an_import_error(self):
        assert issubclass(MissingDependencyError, ImportError)

    def test_require_returns_the_module(self):
        assert require("json", feature="test").dumps({}) == "{}"


class TestCoreMCPConfig:
    """The core MCPConfig mirrors fastmcp's without importing it."""

    def test_defaults_to_no_servers(self):
        assert MCPConfig().mcpServers == {}

    def test_accepts_canonical_form(self):
        config = MCPConfig.model_validate({"mcpServers": {"docs": {"url": "http://localhost:9000/mcp"}}})
        assert list(config.mcpServers) == ["docs"]

    def test_wraps_servers_declared_at_root(self):
        config = MCPConfig.model_validate({"docs": {"command": "uvx", "args": ["mcp-server"]}})
        assert config.mcpServers["docs"]["command"] == "uvx"

    def test_preserves_unknown_top_level_keys(self):
        config = MCPConfig.model_validate({"mcpServers": {}, "someFastMCPExtension": True})
        assert config.to_dict()["someFastMCPExtension"] is True

    def test_leaves_unrecognised_mapping_alone(self):
        """Root wrapping only kicks in for entries that look like servers."""
        config = MCPConfig.model_validate({"notAServer": {"foo": "bar"}})
        assert config.mcpServers == {}


class TestMCPWithoutFastmcp:
    @pytest.mark.asyncio
    async def test_no_servers_configured_never_touches_fastmcp(self):
        from sgr_agent_core.services.mcp_service import MCP2ToolConverter

        with BlockImports("fastmcp", "jambo"):
            assert await MCP2ToolConverter.build_tools_from_mcp(MCPConfig()) == []

    @pytest.mark.asyncio
    async def test_configured_servers_report_the_missing_extra(self):
        from sgr_agent_core.services.mcp_service import MCP2ToolConverter

        config = MCPConfig.model_validate({"mcpServers": {"docs": {"url": "http://localhost:9000/mcp"}}})
        with BlockImports("fastmcp", "jambo"):
            with pytest.raises(MissingDependencyError) as exc_info:
                await MCP2ToolConverter.build_tools_from_mcp(config)
        assert "sgr-agent-core[mcp]" in str(exc_info.value)


class TestSearchWithoutTavily:
    @pytest.mark.asyncio
    async def test_brave_engine_works_without_tavily(self):
        from sgr_agent_core.tools.web_search_tool import _search_brave

        response = MagicMock()
        response.json.return_value = {"web": {"results": [{"title": "T", "url": "https://e.com", "description": "D"}]}}
        response.raise_for_status = MagicMock()

        with BlockImports("tavily"):
            with patch("sgr_agent_core.tools.web_search_tool.httpx.AsyncClient") as mock_client_cls:
                client = AsyncMock()
                client.get = AsyncMock(return_value=response)
                client.__aenter__ = AsyncMock(return_value=client)
                client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = client

                sources = await _search_brave("key", "https://api.brave.test", "query", 5, 0)
        assert [s.url for s in sources] == ["https://e.com"]

    @pytest.mark.asyncio
    async def test_tavily_engine_reports_the_missing_extra(self):
        from sgr_agent_core.tools.web_search_tool import _search_tavily

        with BlockImports("tavily"):
            with pytest.raises(MissingDependencyError) as exc_info:
                await _search_tavily("key", "https://api.tavily.test", "query", 5, 0)
        assert "sgr-agent-core[search]" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_extract_tool_reports_the_missing_extra(self):
        from sgr_agent_core.tools.extract_page_content_tool import (
            ExtractPageContentConfig,
            ExtractPageContentTool,
        )

        config = ExtractPageContentConfig(tavily_api_key="key")
        with BlockImports("tavily"):
            with pytest.raises(MissingDependencyError) as exc_info:
                await ExtractPageContentTool._extract(config, urls=["https://e.com"])
        assert "sgr-agent-core[search]" in str(exc_info.value)


class TestEntrypointsWithoutTheirExtra:
    """``sgr`` and ``sgracp`` explain the missing extra instead of crashing."""

    def test_sgr_reports_missing_server_extra(self, capsys):
        from sgr_agent_core.server.__main__ import main

        with BlockImports("fastapi", "uvicorn"):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 1
        assert "sgr-agent-core[server]" in capsys.readouterr().err

    def test_sgracp_reports_missing_acp_extra(self, capsys):
        from sgr_agent_core.acp.__main__ import main

        with BlockImports("acp"):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 1
        assert "sgr-agent-core[acp]" in capsys.readouterr().err
