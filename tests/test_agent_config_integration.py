"""Tests for agent configuration integration.

This module contains tests for configuration-based agent functionality,
including settings loading, MCP integration, and environment-based
setup.
"""

import sys
import tempfile
from pathlib import Path

import pytest
import yaml

from sgr_agent_core.agent_config import GlobalConfig
from sgr_agent_core.agents import SGRAgent, SGRToolCallingAgent
from sgr_agent_core.server.settings import ServerConfig, setup_logging
from tests.conftest import create_test_agent


class TestAgentConfigurationIntegration:
    """Tests for agent integration with configuration system."""

    def test_config_loading_in_agents(self):
        """Test that agents properly load configuration."""
        agent = create_test_agent(SGRAgent, task="Config integration test")

        assert agent.task == "Config integration test"
        assert agent.name == "sgr_agent"

    def test_mcp_integration_in_agents(self):
        """Test that agents properly integrate MCP tools from config."""
        agent = create_test_agent(SGRAgent, task="MCP integration test")

        assert agent.task == "MCP integration test"
        assert hasattr(agent, "toolkit")


class TestAgentEnvironmentVariables:
    """Tests for agent behavior with environment variables."""

    def test_default_config_parameters(self):
        """Test that agents work with default configuration parameters."""
        agent = create_test_agent(SGRAgent, task="Default config test")

        assert agent.task == "Default config test"
        assert agent.name == "sgr_agent"


class TestAgentConfigurationEdgeCases:
    """Tests for edge cases in agent configuration."""

    def test_missing_config_file_handling(self):
        """Test handling when config file is missing in from_yaml method."""
        # GlobalConfig() can work without config file using defaults
        # But from_yaml() should raise FileNotFoundError for missing file
        GlobalConfig._instance = None
        GlobalConfig._initialized = False

        with pytest.raises(FileNotFoundError):
            GlobalConfig.from_yaml("/nonexistent/config.yaml")

    def test_invalid_config_values(self):
        """Test handling of invalid configuration values."""
        from sgr_agent_core.agent_definition import LLMConfig

        # Should still create agent (validation happens in OpenAI client)
        agent = create_test_agent(
            SGRAgent,
            task="Invalid config test",
            llm_config=LLMConfig(api_key="test-key", base_url=""),
        )
        assert agent.task == "Invalid config test"


class TestMultipleAgentConfigurationConsistency:
    """Tests for configuration consistency across multiple agents."""

    def test_multiple_agents_same_config(self):
        """Test that multiple agents can be created successfully."""
        agent1 = create_test_agent(SGRAgent, task="Task 1")
        agent2 = create_test_agent(SGRToolCallingAgent, task="Task 2")

        assert agent1.task == "Task 1"
        assert agent2.task == "Task 2"
        assert agent1.name == "sgr_agent"
        assert agent2.name == "sgr_tool_calling_agent"

    def test_config_caching_behavior(self):
        """Test that multiple agents have unique IDs."""
        agents = []
        for i in range(3):
            agents.append(create_test_agent(SGRAgent, task=f"Task {i}"))

        assert len(agents) == 3

        # All agents should have same task format and different IDs
        for i, agent in enumerate(agents):
            assert agent.task == f"Task {i}"
            # Verify unique IDs
            for j, other_agent in enumerate(agents):
                if i != j:
                    assert agent.id != other_agent.id


class TestServerConfig:
    """Tests for ServerConfig reading configuration."""

    def test_server_config_defaults(self):
        """Test that ServerConfig has correct default values."""
        original_argv = sys.argv
        try:
            sys.argv = ["test"]
            config = ServerConfig()
        finally:
            sys.argv = original_argv

        assert config.logging_file == "logging_config.yaml"
        assert config.config_file == "config.yaml"
        assert config.agents_file is None
        assert config.host == "0.0.0.0"
        assert config.port == 8010

    def test_server_config_from_environment(self):
        """Test that ServerConfig reads from environment variables."""
        original_argv = sys.argv
        try:
            sys.argv = ["test"]
            with pytest.MonkeyPatch().context() as m:
                m.setenv("LOGGING_FILE", "custom_logging.yaml")
                m.setenv("CONFIG_FILE", "custom_config.yaml")
                m.setenv("AGENTS_FILE", "custom_agents.yaml")
                m.setenv("HOST", "127.0.0.1")
                m.setenv("PORT", "9000")

                config = ServerConfig()

                assert config.logging_file == "custom_logging.yaml"
                assert config.config_file == "custom_config.yaml"
                assert config.agents_file == "custom_agents.yaml"
                assert config.host == "127.0.0.1"
                assert config.port == 9000
        finally:
            sys.argv = original_argv

    def test_server_config_logging_file_reading(self):
        """Test that setup_logging uses logging_file from ServerConfig."""
        import sys

        original_argv = sys.argv
        try:
            sys.argv = ["test"]
            with tempfile.TemporaryDirectory() as tmpdir:
                logging_file = Path(tmpdir) / "test_logging.yaml"
                logging_config = {
                    "version": 1,
                    "disable_existing_loggers": False,
                    "formatters": {"standard": {"format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"}},
                    "handlers": {
                        "console": {
                            "class": "logging.StreamHandler",
                            "level": "INFO",
                            "formatter": "standard",
                            "stream": "ext://sys.stdout",
                        }
                    },
                    "loggers": {"root": {"level": "INFO", "handlers": ["console"]}},
                }

                with open(logging_file, "w", encoding="utf-8") as f:
                    yaml.dump(logging_config, f)

                config = ServerConfig(logging_file=str(logging_file))
                # Should not raise an error
                setup_logging(config.logging_file)
        finally:
            sys.argv = original_argv
