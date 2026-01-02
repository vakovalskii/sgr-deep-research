"""Tests for agent factory and configuration-based agent creation.

This module contains tests for AgentFactory and dynamic agent
instantiation.
"""

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from openai import AsyncOpenAI

from sgr_agent_core.agent_definition import (
    AgentDefinition,
    ExecutionConfig,
    LLMConfig,
    PromptsConfig,
)
from sgr_agent_core.agent_factory import AgentFactory
from sgr_agent_core.agents import (
    SGRAgent,
    SGRToolCallingAgent,
    ToolCallingAgent,
)
from sgr_agent_core.base_agent import BaseAgent
from sgr_agent_core.tools import BaseTool, ReasoningTool


def mock_global_config():
    """Create a mock GlobalConfig for tests."""
    mock_config = Mock()
    mock_config.llm = LLMConfig(api_key="default-key", base_url="https://api.openai.com/v1")
    mock_config.prompts = PromptsConfig(
        system_prompt_str="Default system prompt",
        initial_user_request_str="Default initial request",
        clarification_response_str="Default clarification response",
    )
    mock_config.execution = ExecutionConfig()
    mock_config.search = None
    # Create a mock MCP config that has model_copy and model_dump methods
    mock_mcp = Mock()
    mock_mcp.model_copy.return_value = mock_mcp
    mock_mcp.model_dump.return_value = {}
    mock_config.mcp = mock_mcp
    # Patch GlobalConfig where it's imported inside the validator
    # GlobalConfig is imported inside the method from agent_config, so we need to patch it there
    # The import happens at runtime inside the validator method
    return patch("sgr_agent_core.agent_config.GlobalConfig", return_value=mock_config)


class TestAgentFactory:
    """Tests for dynamic agent creation from configuration."""

    @pytest.mark.asyncio
    async def test_create_agent_from_definition(self):
        """Test creating agent from AgentDefinition."""
        with (
            patch("sgr_agent_core.agent_factory.MCP2ToolConverter.build_tools_from_mcp", return_value=[]),
            mock_global_config(),
        ):
            agent_def = AgentDefinition(
                name="sgr_agent",
                base_class=SGRAgent,
                tools=[ReasoningTool],
                llm={"api_key": "test-key", "base_url": "https://api.openai.com/v1"},
                prompts={
                    "system_prompt_str": "Test system prompt",
                    "initial_user_request_str": "Test initial request",
                    "clarification_response_str": "Test clarification response",
                },
                execution={},
            )
            agent = await AgentFactory.create(agent_def, task_messages=[{"role": "user", "content": "Test task"}])

            assert isinstance(agent, SGRAgent)
            assert len(agent.task_messages) == 1
            assert agent.task_messages[0]["content"] == "Test task"
            assert agent.name == "sgr_agent"

    @pytest.mark.asyncio
    async def test_create_all_agent_types(self):
        """Test creating all available agent types."""
        with (
            patch("sgr_agent_core.agent_factory.MCP2ToolConverter.build_tools_from_mcp", return_value=[]),
            mock_global_config(),
        ):
            task = "Universal test task"
            agent_classes = [
                SGRAgent,
                SGRToolCallingAgent,
                ToolCallingAgent,
            ]

            for agent_class in agent_classes:
                agent_def = AgentDefinition(
                    name=agent_class.name,
                    base_class=agent_class,
                    tools=[ReasoningTool],
                    llm={"api_key": "test-key", "base_url": "https://api.openai.com/v1"},
                    prompts={
                        "system_prompt_str": "Test system prompt",
                        "initial_user_request_str": "Test initial request",
                        "clarification_response_str": "Test clarification response",
                    },
                    execution={},
                )
                agent = await AgentFactory.create(agent_def, task_messages=[{"role": "user", "content": task}])

                assert isinstance(agent, BaseAgent)
                assert len(agent.task_messages) == 1
                assert agent.task_messages[0]["content"] == task
                assert agent.name == agent_class.name

    @pytest.mark.asyncio
    async def test_agent_factory_with_custom_params(self):
        """Test creating agents with custom execution parameters."""
        with (
            patch("sgr_agent_core.agent_factory.MCP2ToolConverter.build_tools_from_mcp", return_value=[]),
            mock_global_config(),
        ):
            agent_def = AgentDefinition(
                name="sgr_tool_calling_agent",
                base_class=SGRToolCallingAgent,
                tools=[ReasoningTool],
                llm={"api_key": "test-key", "base_url": "https://api.openai.com/v1"},
                prompts={
                    "system_prompt_str": "Test system prompt",
                    "initial_user_request_str": "Test initial request",
                    "clarification_response_str": "Test clarification response",
                },
                execution={"max_clarifications": 5, "max_iterations": 15, "max_searches": 10},
            )
            agent = await AgentFactory.create(agent_def, task_messages=[{"role": "user", "content": "Custom task"}])

            assert len(agent.task_messages) == 1
            assert agent.task_messages[0]["content"] == "Custom task"
            assert agent.config.execution.max_clarifications == 5
            assert agent.config.execution.max_iterations == 15
            assert agent.config.execution.max_searches == 10

    @pytest.mark.asyncio
    async def test_agent_creation_preserves_agent_properties(self):
        """Test that agent creation preserves specific agent properties."""
        with (
            patch("sgr_agent_core.agent_factory.MCP2ToolConverter.build_tools_from_mcp", return_value=[]),
            mock_global_config(),
        ):
            agent_def = AgentDefinition(
                name="sgr_tool_calling_agent",
                base_class=SGRToolCallingAgent,
                tools=[ReasoningTool],
                llm={"api_key": "test-key", "base_url": "https://api.openai.com/v1"},
                prompts={
                    "system_prompt_str": "Test system prompt",
                    "initial_user_request_str": "Test initial request",
                    "clarification_response_str": "Test clarification response",
                },
                execution={},
            )
            agent = await AgentFactory.create(agent_def, task_messages=[{"role": "user", "content": "Test"}])

            # Should have tool_choice property for tool calling agents
            if hasattr(agent, "tool_choice"):
                assert agent.tool_choice == "required"


class TestConfigurationBasedAgentCreation:
    """Tests for creating agents based on configuration patterns."""

    @pytest.mark.asyncio
    async def test_agent_config_integration(self):
        """Test that agents properly integrate configuration from settings."""
        with (
            patch("sgr_agent_core.agent_factory.MCP2ToolConverter.build_tools_from_mcp", return_value=[]),
            mock_global_config(),
        ):
            agent_def = AgentDefinition(
                name="sgr_agent",
                base_class=SGRAgent,
                tools=[ReasoningTool],
                llm={"api_key": "test-key", "base_url": "https://api.openai.com/v1"},
                prompts={
                    "system_prompt_str": "Test system prompt",
                    "initial_user_request_str": "Test initial request",
                    "clarification_response_str": "Test clarification response",
                },
                execution={},
            )
            agent = await AgentFactory.create(
                agent_def, task_messages=[{"role": "user", "content": "Test config integration"}]
            )

            assert len(agent.task_messages) == 1
            assert agent.task_messages[0]["content"] == "Test config integration"
            assert agent.name == "sgr_agent"

    def test_agent_name_consistency(self):
        """Test that agent names are consistent with class names."""
        agent_classes = [
            SGRAgent,
            SGRToolCallingAgent,
            ToolCallingAgent,
        ]
        for agent_class in agent_classes:
            assert hasattr(agent_class, "name")
            assert agent_class.name in [
                "sgr_agent",
                "sgr_tool_calling_agent",
                "tool_calling_agent",
            ]

    @pytest.mark.asyncio
    async def test_multiple_agent_creation_independence(self):
        """Test that multiple agents can be created independently."""
        with (
            patch("sgr_agent_core.agent_factory.MCP2ToolConverter.build_tools_from_mcp", return_value=[]),
            mock_global_config(),
        ):
            tasks = ["Task 1", "Task 2", "Task 3"]
            agent_classes = [SGRAgent, SGRToolCallingAgent, ToolCallingAgent]

            agents = []
            for i, agent_class in enumerate(agent_classes):
                agent_def = AgentDefinition(
                    name=agent_class.name,
                    base_class=agent_class,
                    tools=[ReasoningTool],
                    llm={"api_key": "test-key", "base_url": "https://api.openai.com/v1"},
                    prompts={
                        "system_prompt_str": "Test system prompt",
                        "initial_user_request_str": "Test initial request",
                        "clarification_response_str": "Test clarification response",
                    },
                    execution={},
                )
                agent = await AgentFactory.create(agent_def, task_messages=[{"role": "user", "content": tasks[i]}])
                agents.append(agent)

            # Verify all agents are independent
            for i, agent in enumerate(agents):
                assert len(agent.task_messages) == 1
                assert agent.task_messages[0]["content"] == tasks[i]
                assert agent.id != agents[(i + 1) % len(agents)].id  # Different IDs

            # Verify different types
            if len(agents) > 1:
                assert type(agents[0]) is not type(agents[1])  # noqa


class TestAgentCreationEdgeCases:
    """Tests for edge cases in agent creation."""

    @pytest.mark.asyncio
    async def test_empty_task_creation(self):
        """Test creating agent with empty task."""
        with (
            patch("sgr_agent_core.agent_factory.MCP2ToolConverter.build_tools_from_mcp", return_value=[]),
            mock_global_config(),
        ):
            agent_def = AgentDefinition(
                name="sgr_agent",
                base_class=SGRAgent,
                tools=[ReasoningTool],
                llm={"api_key": "test-key", "base_url": "https://api.openai.com/v1"},
                prompts={
                    "system_prompt_str": "Test system prompt",
                    "initial_user_request_str": "Test initial request",
                    "clarification_response_str": "Test clarification response",
                },
                execution={},
            )
            agent = await AgentFactory.create(agent_def, task_messages=[{"role": "user", "content": ""}])

            assert len(agent.task_messages) == 1
            assert agent.task_messages[0]["content"] == ""
            assert agent.name == "sgr_agent"

    @pytest.mark.asyncio
    async def test_agent_creation_with_toolkit(self):
        """Test creating agent with custom toolkit."""

        class CustomTool(BaseTool):
            tool_name = "custom_tool"
            description = "A custom test tool"

        with (
            patch("sgr_agent_core.agent_factory.MCP2ToolConverter.build_tools_from_mcp", return_value=[]),
            mock_global_config(),
        ):
            agent_def = AgentDefinition(
                name="sgr_agent",
                base_class=SGRAgent,
                tools=[CustomTool],
                llm={"api_key": "test-key", "base_url": "https://api.openai.com/v1"},
                prompts={
                    "system_prompt_str": "Test system prompt",
                    "initial_user_request_str": "Test initial request",
                    "clarification_response_str": "Test clarification response",
                },
                execution={},
            )
            agent = await AgentFactory.create(agent_def, task_messages=[{"role": "user", "content": "Test"}])

            # Verify custom tool was added to toolkit
            assert CustomTool in agent.toolkit


class TestAgentFactoryClientCreation:
    """Tests for OpenAI client creation in AgentFactory."""

    def test_create_client_without_proxy(self):
        """Test creating OpenAI client without proxy."""
        llm_config = LLMConfig(
            api_key="test-key",
            base_url="https://api.openai.com/v1",
        )
        client = AgentFactory._create_client(llm_config)

        assert client is not None
        assert client.api_key == "test-key"
        assert str(client.base_url).rstrip("/") == "https://api.openai.com/v1"

    def test_create_client_with_proxy(self):
        """Test creating OpenAI client with proxy."""
        llm_config = LLMConfig(
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            proxy="http://127.0.0.1:8080",
        )
        client = AgentFactory._create_client(llm_config)

        assert client is not None
        assert client.api_key == "test-key"
        assert str(client.base_url).rstrip("/") == "https://api.openai.com/v1"
        assert client._client is not None

    def test_create_client_with_socks_proxy(self):
        """Test creating OpenAI client with SOCKS proxy."""
        llm_config = LLMConfig(
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            proxy="socks5://127.0.0.1:1081",
        )
        client = AgentFactory._create_client(llm_config)

        assert client is not None
        assert client.api_key == "test-key"
        assert client._client is not None

    @pytest.mark.asyncio
    async def test_stream_request_with_extra_parameters(self):
        """Test that additional parameters from LLMConfig (extra='allow') are
        passed to stream requests."""
        from sgr_agent_core.agents.tool_calling_agent import ToolCallingAgent
        from sgr_agent_core.tools import ReasoningTool

        # Create LLMConfig with additional parameters for API requests
        llm_config = LLMConfig(
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
            top_p=0.9,  # Additional parameter for API requests
            top_k=40,  # Additional parameter for API requests
        )

        # Create real AsyncOpenAI client with mocked HTTP client
        # This allows us to test real OpenAI SDK behavior without making actual HTTP requests
        mock_http_client = AsyncMock(spec=httpx.AsyncClient)
        real_client = AsyncOpenAI(
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            http_client=mock_http_client,
        )

        # Create mock stream response
        async def async_iter(self):
            return
            yield

        mock_stream = AsyncMock()
        mock_stream.__aiter__ = async_iter
        mock_stream.get_final_completion = AsyncMock(
            return_value=Mock(
                choices=[
                    Mock(
                        message=Mock(
                            tool_calls=[
                                Mock(
                                    function=Mock(
                                        parsed_arguments=ReasoningTool(
                                            reasoning_steps=["Step 1", "Step 2"],
                                            current_situation="Test",
                                            plan_status="Test",
                                            enough_data=True,
                                            remaining_steps=["Next step"],
                                            task_completed=True,
                                        )
                                    )
                                )
                            ]
                        )
                    )
                ]
            )
        )

        mock_stream_context = AsyncMock()
        mock_stream_context.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream_context.__aexit__ = AsyncMock(return_value=None)

        # Patch chat.completions.stream to capture arguments while using real client
        with patch.object(
            real_client.chat.completions, "stream", return_value=mock_stream_context
        ) as mock_stream_method:
            # Create agent with real client
            agent = ToolCallingAgent(
                task_messages=[{"role": "user", "content": "Test task"}],
                openai_client=real_client,
                agent_config=AgentDefinition(
                    name="test_agent",
                    base_class=ToolCallingAgent,
                    tools=[ReasoningTool],
                    llm=llm_config,
                ),
                toolkit=[ReasoningTool],
            )

            await agent._select_action_phase()

            # Verify additional parameters from extra="allow" are passed to stream request
            call_kwargs = mock_stream_method.call_args.kwargs
            assert call_kwargs["top_p"] == 0.9
            assert call_kwargs["top_k"] == 40
            assert call_kwargs["model"] == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_stream_request_with_invalid_parameter_raises_error(self):
        """Test that invalid/unsupported parameters raise TypeError when passed
        to stream requests."""
        from sgr_agent_core.agents.tool_calling_agent import ToolCallingAgent
        from sgr_agent_core.tools import ReasoningTool

        # Create LLMConfig with invalid parameter (not supported by OpenAI API)
        llm_config = LLMConfig(
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
            my_custom_parameter="invalid_value",  # Invalid parameter
        )

        # Create real AsyncOpenAI client with mocked HTTP client
        # This allows us to test real OpenAI SDK validation without making actual HTTP requests
        mock_http_client = AsyncMock(spec=httpx.AsyncClient)
        real_client = AsyncOpenAI(
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            http_client=mock_http_client,
        )

        # Create agent with invalid parameter
        agent = ToolCallingAgent(
            task_messages=[{"role": "user", "content": "Test task"}],
            openai_client=real_client,
            agent_config=AgentDefinition(
                name="test_agent",
                base_class=ToolCallingAgent,
                tools=[ReasoningTool],
                llm=llm_config,
            ),
            toolkit=[ReasoningTool],
        )

        # Verify that invalid parameter raises TypeError from real OpenAI client
        # OpenAI SDK validates parameters before making HTTP requests
        with pytest.raises(TypeError, match="got an unexpected keyword argument 'my_custom_parameter'"):
            await agent._select_action_phase()


class TestAgentFactoryRegistryIntegration:
    """Tests for AgentFactory integration with registries."""

    @pytest.mark.asyncio
    async def test_create_agent_with_string_base_class(self):
        """Test creating agent with string base_class name from registry."""
        with (
            patch("sgr_agent_core.agent_factory.MCP2ToolConverter.build_tools_from_mcp", return_value=[]),
            mock_global_config(),
        ):
            # Use string name instead of class
            agent_def = AgentDefinition(
                name="sgr_agent",
                base_class="sgr_agent",  # String name
                tools=[ReasoningTool],
                llm={"api_key": "test-key", "base_url": "https://api.openai.com/v1"},
                prompts={
                    "system_prompt_str": "Test system prompt",
                    "initial_user_request_str": "Test initial request",
                    "clarification_response_str": "Test clarification response",
                },
                execution={},
            )
            agent = await AgentFactory.create(agent_def, task_messages=[{"role": "user", "content": "Test task"}])

            assert isinstance(agent, SGRAgent)
            assert len(agent.task_messages) == 1
            assert agent.task_messages[0]["content"] == "Test task"

    @pytest.mark.asyncio
    async def test_create_agent_with_string_tool(self):
        """Test creating agent with string tool name from registry."""
        with (
            patch("sgr_agent_core.agent_factory.MCP2ToolConverter.build_tools_from_mcp", return_value=[]),
            mock_global_config(),
        ):
            # Use string name instead of class
            agent_def = AgentDefinition(
                name="sgr_agent",
                base_class=SGRAgent,
                tools=["reasoningtool"],  # String name
                llm={"api_key": "test-key", "base_url": "https://api.openai.com/v1"},
                prompts={
                    "system_prompt_str": "Test system prompt",
                    "initial_user_request_str": "Test initial request",
                    "clarification_response_str": "Test clarification response",
                },
                execution={},
            )
            agent = await AgentFactory.create(agent_def, task_messages=[{"role": "user", "content": "Test task"}])

            assert isinstance(agent, SGRAgent)
            # Verify that ReasoningTool was resolved from string and added to toolkit
            # Note: SGRAgent may transform toolkit, so we check that toolkit is not empty
            assert len(agent.toolkit) > 0

    @pytest.mark.asyncio
    async def test_create_agent_with_mixed_tools(self):
        """Test creating agent with both class and string tool names."""

        class CustomTool(BaseTool):
            tool_name = "custom_tool"
            description = "A custom test tool"

        with (
            patch("sgr_agent_core.agent_factory.MCP2ToolConverter.build_tools_from_mcp", return_value=[]),
            mock_global_config(),
        ):
            agent_def = AgentDefinition(
                name="sgr_agent",
                base_class=SGRAgent,
                tools=[CustomTool, "reasoningtool"],  # Mix of class and string
                llm={"api_key": "test-key", "base_url": "https://api.openai.com/v1"},
                prompts={
                    "system_prompt_str": "Test system prompt",
                    "initial_user_request_str": "Test initial request",
                    "clarification_response_str": "Test clarification response",
                },
                execution={},
            )
            agent = await AgentFactory.create(agent_def, task_messages=[{"role": "user", "content": "Test task"}])

            # Verify that both tools were resolved and added to toolkit
            # Note: SGRAgent may transform toolkit, so we check that toolkit contains expected tools
            assert CustomTool in agent.toolkit
            # ReasoningTool should be resolved from string and added
            assert len(agent.toolkit) >= 1


class TestAgentFactoryErrorHandling:
    """Tests for error handling in AgentFactory."""

    @pytest.mark.asyncio
    async def test_create_agent_with_invalid_base_class_string(self):
        """Test creating agent with invalid base_class string name."""
        with (
            patch("sgr_agent_core.agent_factory.MCP2ToolConverter.build_tools_from_mcp", return_value=[]),
            mock_global_config(),
        ):
            agent_def = AgentDefinition(
                name="invalid_agent",
                base_class="nonexistent_agent",  # Invalid string name
                tools=[ReasoningTool],
                llm={"api_key": "test-key", "base_url": "https://api.openai.com/v1"},
                prompts={
                    "system_prompt_str": "Test system prompt",
                    "initial_user_request_str": "Test initial request",
                    "clarification_response_str": "Test clarification response",
                },
                execution={},
            )

            with pytest.raises(ValueError, match="Agent base class 'nonexistent_agent' not found in registry"):
                await AgentFactory.create(agent_def, task_messages=[{"role": "user", "content": "Test task"}])

    @pytest.mark.asyncio
    async def test_create_agent_with_invalid_tool_string(self):
        """Test creating agent with invalid tool string name."""
        with (
            patch("sgr_agent_core.agent_factory.MCP2ToolConverter.build_tools_from_mcp", return_value=[]),
            mock_global_config(),
        ):
            agent_def = AgentDefinition(
                name="sgr_agent",
                base_class=SGRAgent,
                tools=["nonexistent_tool"],  # Invalid string name
                llm={"api_key": "test-key", "base_url": "https://api.openai.com/v1"},
                prompts={
                    "system_prompt_str": "Test system prompt",
                    "initial_user_request_str": "Test initial request",
                    "clarification_response_str": "Test clarification response",
                },
                execution={},
            )

            with pytest.raises(ValueError, match="Tool 'nonexistent_tool' not found in registry"):
                await AgentFactory.create(agent_def, task_messages=[{"role": "user", "content": "Test task"}])

    @pytest.mark.asyncio
    async def test_create_agent_with_agent_creation_exception(self):
        """Test handling exception during agent instantiation."""
        with (
            patch("sgr_agent_core.agent_factory.MCP2ToolConverter.build_tools_from_mcp", return_value=[]),
            mock_global_config(),
            patch.object(SGRAgent, "__init__", side_effect=RuntimeError("Failed to initialize")),
        ):
            agent_def = AgentDefinition(
                name="sgr_agent",
                base_class=SGRAgent,
                tools=[ReasoningTool],
                llm={"api_key": "test-key", "base_url": "https://api.openai.com/v1"},
                prompts={
                    "system_prompt_str": "Test system prompt",
                    "initial_user_request_str": "Test initial request",
                    "clarification_response_str": "Test clarification response",
                },
                execution={},
            )

            with pytest.raises(ValueError, match="Failed to create agent"):
                await AgentFactory.create(agent_def, task_messages=[{"role": "user", "content": "Test task"}])


class TestAgentFactoryMCPIntegration:
    """Tests for MCP tools integration in AgentFactory."""

    @pytest.mark.asyncio
    async def test_create_agent_with_mcp_tools(self):
        """Test creating agent with MCP tools."""

        class MockMCPTool(BaseTool):
            tool_name = "mcp_tool"
            description = "Mock MCP tool"

        mock_mcp_tools = [MockMCPTool]

        with (
            patch(
                "sgr_agent_core.agent_factory.MCP2ToolConverter.build_tools_from_mcp",
                return_value=mock_mcp_tools,
            ),
            mock_global_config(),
        ):
            agent_def = AgentDefinition(
                name="sgr_agent",
                base_class=SGRAgent,
                tools=[ReasoningTool],
                llm={"api_key": "test-key", "base_url": "https://api.openai.com/v1"},
                prompts={
                    "system_prompt_str": "Test system prompt",
                    "initial_user_request_str": "Test initial request",
                    "clarification_response_str": "Test clarification response",
                },
                execution={},
            )
            agent = await AgentFactory.create(agent_def, task_messages=[{"role": "user", "content": "Test task"}])

            assert MockMCPTool in agent.toolkit
            assert ReasoningTool in agent.toolkit
            assert len(agent.toolkit) == 2

    @pytest.mark.asyncio
    async def test_create_agent_with_mcp_and_regular_tools(self):
        """Test creating agent with both MCP and regular tools."""

        class MockMCPTool1(BaseTool):
            tool_name = "mcp_tool_1"
            description = "Mock MCP tool 1"

        class MockMCPTool2(BaseTool):
            tool_name = "mcp_tool_2"
            description = "Mock MCP tool 2"

        mock_mcp_tools = [MockMCPTool1, MockMCPTool2]

        with (
            patch(
                "sgr_agent_core.agent_factory.MCP2ToolConverter.build_tools_from_mcp",
                return_value=mock_mcp_tools,
            ),
            mock_global_config(),
        ):
            agent_def = AgentDefinition(
                name="sgr_agent",
                base_class=SGRAgent,
                tools=[ReasoningTool],
                llm={"api_key": "test-key", "base_url": "https://api.openai.com/v1"},
                prompts={
                    "system_prompt_str": "Test system prompt",
                    "initial_user_request_str": "Test initial request",
                    "clarification_response_str": "Test clarification response",
                },
                execution={},
            )
            agent = await AgentFactory.create(agent_def, task_messages=[{"role": "user", "content": "Test task"}])

            assert MockMCPTool1 in agent.toolkit
            assert MockMCPTool2 in agent.toolkit
            assert ReasoningTool in agent.toolkit
            assert len(agent.toolkit) == 3


class TestAgentFactoryDefinitionsList:
    """Tests for getting agent definitions list."""

    def test_get_definitions_list(self):
        """Test getting list of agent definitions from config."""
        with patch("sgr_agent_core.agent_factory.GlobalConfig") as mock_global_config:
            mock_config = Mock()
            mock_agent_def1 = Mock()
            mock_agent_def1.name = "agent1"
            mock_agent_def2 = Mock()
            mock_agent_def2.name = "agent2"
            mock_config.agents = {"agent1": mock_agent_def1, "agent2": mock_agent_def2}
            mock_global_config.return_value = mock_config

            definitions = AgentFactory.get_definitions_list()

            assert len(definitions) == 2
            assert mock_agent_def1 in definitions
            assert mock_agent_def2 in definitions

    def test_get_definitions_list_empty(self):
        """Test getting empty list when no agents in config."""
        with patch("sgr_agent_core.agent_factory.GlobalConfig") as mock_global_config:
            mock_config = Mock()
            mock_config.agents = {}
            mock_global_config.return_value = mock_config

            definitions = AgentFactory.get_definitions_list()

            assert len(definitions) == 0
            assert definitions == []
