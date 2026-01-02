"""Tests for agents loading from config.yaml and agents.yaml files.

This module tests the loading order and override behavior:
1. Load config.yaml (including agents section if present)
2. Add default agents
3. Load agents.yaml if provided (overrides existing agents)
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from sgr_agent_core.agent_config import GlobalConfig
from sgr_agent_core.server.__main__ import load_config

# Verify we're importing the real function
assert (
    load_config.__module__ == "sgr_agent_core.server.__main__"
), "Must import load_config from sgr_agent_core.server.__main__, not a mock!"


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def reset_global_config():
    """Reset GlobalConfig singleton before and after each test.

    This ensures each test starts with a clean GlobalConfig state.
    IMPORTANT: All tests in this file must use this fixture!
    """
    # Save original state
    original_instance = GlobalConfig._instance
    original_initialized = getattr(GlobalConfig, "_initialized", False)

    # Reset before test - must be done before each test
    GlobalConfig._instance = None
    GlobalConfig._initialized = False

    yield

    # Reset after test - restore original state
    GlobalConfig._instance = original_instance
    GlobalConfig._initialized = original_initialized
    # Also clear agents dict if instance exists
    if GlobalConfig._instance is not None and hasattr(GlobalConfig._instance, "agents"):
        GlobalConfig._instance.agents.clear()


class TestAgentsLoadingFromAgentsYaml:
    """Test loading agents from agents.yaml file."""

    def test_load_agents_from_agents_yaml_only(self, temp_dir, reset_global_config):
        """Test that agents are loaded from agents.yaml when it exists."""
        # Create agents.yaml
        agents_yaml = temp_dir / "agents.yaml"
        agents_data = {
            "agents": {
                "test_agent_from_agents_yaml": {
                    "base_class": "sgr_agent_core.agents.sgr_agent.SGRAgent",
                    "llm": {"api_key": "test-key", "model": "gpt-4o-mini"},
                    "tools": ["FinalAnswerTool"],
                }
            }
        }
        agents_yaml.write_text(yaml.dump(agents_data), encoding="utf-8")

        # Create minimal config.yaml without agents section
        config_yaml = temp_dir / "config.yaml"
        config_data = {
            "llm": {"api_key": "test-key", "model": "gpt-4o-mini"},
        }
        config_yaml.write_text(yaml.dump(config_data), encoding="utf-8")

        # Use actual load_config() from __main__.py
        config = load_config(str(config_yaml), str(agents_yaml))

        # Verify agent was loaded from agents.yaml
        assert "test_agent_from_agents_yaml" in config.agents
        assert config.agents["test_agent_from_agents_yaml"].name == "test_agent_from_agents_yaml"

    def test_load_agents_from_agents_yaml_with_config_override(self, temp_dir, reset_global_config):
        """Test that config.yaml agents are loaded first, then agents.yaml
        overrides them."""
        # Create agents.yaml with agent that overrides temperature
        agents_yaml = temp_dir / "agents.yaml"
        agents_data = {
            "agents": {
                "test_agent": {
                    "base_class": "sgr_agent_core.agents.sgr_agent.SGRAgent",
                    "llm": {"api_key": "test-key", "model": "gpt-4o-mini", "temperature": 0.8},
                    "tools": ["FinalAnswerTool"],
                }
            }
        }
        agents_yaml.write_text(yaml.dump(agents_data), encoding="utf-8")

        # Create config.yaml with agents section that has different temperature
        config_yaml = temp_dir / "config.yaml"
        config_data = {
            "llm": {"api_key": "test-key", "model": "gpt-4o-mini"},
            "agents": {
                "test_agent": {
                    "base_class": "sgr_agent_core.agents.sgr_agent.SGRAgent",
                    "llm": {"api_key": "test-key", "model": "gpt-4o-mini", "temperature": 0.5},
                    "tools": ["FinalAnswerTool"],
                }
            },
        }
        config_yaml.write_text(yaml.dump(config_data), encoding="utf-8")

        # Use actual load_config() from __main__.py
        # Order: config.yaml (temperature 0.5) -> default agents -> agents.yaml (temperature 0.8, overrides)
        config = load_config(str(config_yaml), str(agents_yaml))

        # Verify agent exists and has overridden temperature from agents.yaml
        assert "test_agent" in config.agents
        # agents.yaml should override config.yaml, so temperature should be 0.8
        assert config.agents["test_agent"].llm.temperature == 0.8  # From agents.yaml (loaded last, overrides)


class TestAgentsLoadingFromConfigYaml:
    """Test loading agents from config.yaml file."""

    def test_load_agents_from_config_yaml_only(self, temp_dir, reset_global_config):
        """Test that agents are loaded from config.yaml when agents.yaml
        doesn't exist."""
        # Create config.yaml with agents section
        config_yaml = temp_dir / "config.yaml"
        config_data = {
            "llm": {"api_key": "test-key", "model": "gpt-4o-mini"},
            "agents": {
                "test_agent_from_config": {
                    "base_class": "sgr_agent_core.agents.sgr_agent.SGRAgent",
                    "llm": {"api_key": "test-key", "model": "gpt-4o-mini"},
                    "tools": ["FinalAnswerTool"],
                }
            },
        }
        config_yaml.write_text(yaml.dump(config_data), encoding="utf-8")

        # Use actual load_config() from __main__.py (no agents.yaml)
        config = load_config(str(config_yaml), None)

        # Verify agent was loaded from config.yaml
        assert "test_agent_from_config" in config.agents
        assert config.agents["test_agent_from_config"].name == "test_agent_from_config"


class TestAgentsLoadingOrder:
    """Test the correct loading order: config.yaml first, then default agents, then agents.yaml override."""

    def test_agents_yaml_first_then_config_override(self, temp_dir, reset_global_config):
        """Test that config.yaml is loaded first, then agents.yaml overrides
        settings."""
        # Create agents.yaml with agent having temperature 0.8 (will override)
        agents_yaml = temp_dir / "agents.yaml"
        agents_data = {
            "agents": {
                "overridden_agent": {
                    "base_class": "sgr_agent_core.agents.sgr_agent.SGRAgent",
                    "llm": {"api_key": "test-key", "model": "gpt-4o-mini", "temperature": 0.8},
                    "tools": ["FinalAnswerTool"],
                }
            }
        }
        agents_yaml.write_text(yaml.dump(agents_data), encoding="utf-8")

        # Create config.yaml with same agent but different temperature
        config_yaml = temp_dir / "config.yaml"
        config_data = {
            "llm": {"api_key": "test-key", "model": "gpt-4o-mini"},
            "agents": {
                "overridden_agent": {
                    "base_class": "sgr_agent_core.agents.sgr_agent.SGRAgent",
                    "llm": {"api_key": "test-key", "model": "gpt-4o-mini", "temperature": 0.5},
                    "tools": ["FinalAnswerTool"],
                }
            },
        }
        config_yaml.write_text(yaml.dump(config_data), encoding="utf-8")

        # Use actual load_config() from __main__.py
        # Order: config.yaml (temperature 0.5) -> default agents -> agents.yaml (temperature 0.8, overrides)
        config = load_config(str(config_yaml), str(agents_yaml))

        # Verify: agents.yaml should override config.yaml
        assert "overridden_agent" in config.agents
        assert config.agents["overridden_agent"].llm.temperature == 0.8  # From agents.yaml (overrides config.yaml)

    def test_both_files_different_agents(self, temp_dir, reset_global_config):
        """Test loading different agents from both files."""
        # Create agents.yaml with agent1
        agents_yaml = temp_dir / "agents.yaml"
        agents_data = {
            "agents": {
                "agent_from_agents_yaml": {
                    "base_class": "sgr_agent_core.agents.sgr_agent.SGRAgent",
                    "llm": {"api_key": "test-key", "model": "gpt-4o-mini"},
                    "tools": ["FinalAnswerTool"],
                }
            }
        }
        agents_yaml.write_text(yaml.dump(agents_data), encoding="utf-8")

        # Create config.yaml with agent2
        config_yaml = temp_dir / "config.yaml"
        config_data = {
            "llm": {"api_key": "test-key", "model": "gpt-4o-mini"},
            "agents": {
                "agent_from_config": {
                    "base_class": "sgr_agent_core.agents.sgr_agent.SGRAgent",
                    "llm": {"api_key": "test-key", "model": "gpt-4o-mini"},
                    "tools": ["FinalAnswerTool"],
                }
            },
        }
        config_yaml.write_text(yaml.dump(config_data), encoding="utf-8")

        # Use actual load_config() from __main__.py
        config = load_config(str(config_yaml), str(agents_yaml))

        # Verify both agents exist
        assert "agent_from_agents_yaml" in config.agents
        assert "agent_from_config" in config.agents

    def test_agents_yaml_missing_agents_key(self, temp_dir, reset_global_config):
        """Test that missing 'agents' key in agents.yaml raises ValueError.

        This test will FAIL if error handling (try/except) is commented
        out in __main__.py, because it checks that ValueError is
        properly raised.
        """
        # Create agents.yaml without 'agents' key
        agents_yaml = temp_dir / "agents.yaml"
        agents_data = {"some_other_key": "value"}
        agents_yaml.write_text(yaml.dump(agents_data), encoding="utf-8")

        # Create config.yaml
        config_yaml = temp_dir / "config.yaml"
        config_data = {"llm": {"api_key": "test-key", "model": "gpt-4o-mini"}}
        config_yaml.write_text(yaml.dump(config_data), encoding="utf-8")

        # Use actual load_config() from __main__.py
        # Loading agents.yaml without 'agents' key should raise ValueError
        with pytest.raises(ValueError, match="must contain 'agents' key"):
            load_config(str(config_yaml), str(agents_yaml))

    def test_agents_yaml_error_logging(self, temp_dir, reset_global_config):
        """Test that ValueError from agents.yaml is logged.

        This test will FAIL if error handling (try/except with
        logger.error) is commented out in __main__.py.
        """
        # Create agents.yaml without 'agents' key
        agents_yaml = temp_dir / "agents.yaml"
        agents_data = {"some_other_key": "value"}
        agents_yaml.write_text(yaml.dump(agents_data), encoding="utf-8")

        # Create config.yaml
        config_yaml = temp_dir / "config.yaml"
        config_data = {"llm": {"api_key": "test-key", "model": "gpt-4o-mini"}}
        config_yaml.write_text(yaml.dump(config_data), encoding="utf-8")

        # Mock logger to check if error is logged
        with patch("sgr_agent_core.server.__main__.logger") as mock_logger:
            # Use actual load_config() from __main__.py
            with pytest.raises(ValueError, match="must contain 'agents' key"):
                load_config(str(config_yaml), str(agents_yaml))

            # Check that logger.error was called (only if try/except is uncommented)
            # If try/except is commented out, this assertion will FAIL
            (
                mock_logger.error.assert_called_once(),
                "ERROR: logger.error was not called! This means try/except block is commented out in __main__.py",
            )
            error_message = mock_logger.error.call_args[0][0]
            assert "Invalid agents file format" in error_message or "must contain 'agents' key" in str(
                error_message
            ), f"Expected error message about invalid format, got: {error_message}"

    def test_agents_yaml_yaml_error_logging(self, temp_dir, reset_global_config):
        """Test that yaml.YAMLError from agents.yaml is logged.

        This test will FAIL if error handling (try/except with
        logger.error) is commented out in __main__.py.
        """
        # Create invalid YAML file
        agents_yaml = temp_dir / "agents.yaml"
        agents_yaml.write_text("invalid: yaml: content: [unclosed", encoding="utf-8")

        # Create config.yaml
        config_yaml = temp_dir / "config.yaml"
        config_data = {"llm": {"api_key": "test-key", "model": "gpt-4o-mini"}}
        config_yaml.write_text(yaml.dump(config_data), encoding="utf-8")

        # Mock logger to check if error is logged
        with patch("sgr_agent_core.server.__main__.logger") as mock_logger:
            # Use actual load_config() from __main__.py
            with pytest.raises(yaml.YAMLError):
                load_config(str(config_yaml), str(agents_yaml))

            # Check that logger.error was called (only if try/except is uncommented)
            # If try/except is commented out, this assertion will FAIL
            (
                mock_logger.error.assert_called_once(),
                "ERROR: logger.error was not called! This means try/except block is commented out in __main__.py",
            )
            error_message = mock_logger.error.call_args[0][0]
            assert (
                "YAML parsing error" in error_message
            ), f"Expected 'YAML parsing error' in log message, got: {error_message}"

    def test_config_yaml_without_agents_section(self, temp_dir, reset_global_config):
        """Test that config.yaml can be loaded without agents section."""
        # Create config.yaml without agents section
        config_yaml = temp_dir / "config.yaml"
        config_data = {"llm": {"api_key": "test-key", "model": "gpt-4o-mini"}}
        config_yaml.write_text(yaml.dump(config_data), encoding="utf-8")

        # Use actual load_config() from __main__.py
        config = load_config(str(config_yaml), None)

        # Agents dict should be empty if no agents in config
        assert isinstance(config.agents, dict)
        # No default agents should be loaded automatically (core has no hard dependencies)
        assert len(config.agents) == 0

    def test_agents_file_not_exists(self, temp_dir, reset_global_config):
        """Test that load_config works when agents_file doesn't exist."""
        # Create config.yaml
        config_yaml = temp_dir / "config.yaml"
        config_data = {"llm": {"api_key": "test-key", "model": "gpt-4o-mini"}}
        config_yaml.write_text(yaml.dump(config_data), encoding="utf-8")

        # Use actual load_config() from __main__.py with non-existent agents file
        non_existent_agents_file = temp_dir / "non_existent_agents.yaml"
        config = load_config(str(config_yaml), str(non_existent_agents_file))

        # Should still work, but no agents if not in config
        assert isinstance(config.agents, dict)
        # No default agents should be loaded automatically
        assert len(config.agents) == 0

    def test_config_yaml_agents_loaded_correctly(self, temp_dir, reset_global_config):
        """Test that agents from config.yaml are loaded correctly.

        Core should load agents only from config files, without hard
        dependencies.
        """
        # Create config.yaml with an agent
        config_yaml = temp_dir / "config.yaml"
        config_data = {
            "llm": {"api_key": "test-key", "model": "gpt-4o-mini"},
            "agents": {
                "sgr_agent": {
                    "base_class": "sgr_agent_core.agents.sgr_agent.SGRAgent",
                    "llm": {"api_key": "test-key", "model": "gpt-4o-mini", "temperature": 0.9},
                    "tools": ["FinalAnswerTool"],
                }
            },
        }
        config_yaml.write_text(yaml.dump(config_data), encoding="utf-8")

        # Load config - agents should be loaded from config.yaml
        config = load_config(str(config_yaml), None)

        # Agent from config.yaml should be present with correct temperature
        assert "sgr_agent" in config.agents
        # Temperature should be 0.9 from config.yaml (no defaults override)
        assert config.agents["sgr_agent"].llm.temperature == 0.9

    def test_agents_yaml_overrides_config_yaml(self, temp_dir, reset_global_config):
        """Test that agents.yaml overrides config.yaml agents.

        This test verifies the loading order: config.yaml -> agents.yaml (overrides).
        """
        # Create config.yaml with agent
        config_yaml = temp_dir / "config.yaml"
        config_data = {
            "llm": {"api_key": "test-key", "model": "gpt-4o-mini"},
            "agents": {
                "test_agent": {
                    "base_class": "sgr_agent_core.agents.sgr_agent.SGRAgent",
                    "llm": {"api_key": "test-key", "model": "gpt-4o-mini", "temperature": 0.5},
                    "tools": ["FinalAnswerTool"],
                },
                "sgr_agent": {
                    "base_class": "sgr_agent_core.agents.sgr_agent.SGRAgent",
                    "llm": {"api_key": "test-key", "model": "gpt-4o-mini", "temperature": 0.6},
                    "tools": ["FinalAnswerTool"],
                },
            },
        }
        config_yaml.write_text(yaml.dump(config_data), encoding="utf-8")

        # Create agents.yaml that overrides config.yaml
        agents_yaml = temp_dir / "agents.yaml"
        agents_data = {
            "agents": {
                "test_agent": {
                    "base_class": "sgr_agent_core.agents.sgr_agent.SGRAgent",
                    "llm": {"api_key": "test-key", "model": "gpt-4o-mini", "temperature": 0.8},
                    "tools": ["FinalAnswerTool"],
                },
                "sgr_agent": {
                    "base_class": "sgr_agent_core.agents.sgr_agent.SGRAgent",
                    "llm": {"api_key": "test-key", "model": "gpt-4o-mini", "temperature": 0.9},
                    "tools": ["FinalAnswerTool"],
                },
            }
        }
        agents_yaml.write_text(yaml.dump(agents_data), encoding="utf-8")

        # Load config
        config = load_config(str(config_yaml), str(agents_yaml))

        # agents.yaml should override config.yaml
        assert config.agents["test_agent"].llm.temperature == 0.8  # From agents.yaml
        assert config.agents["sgr_agent"].llm.temperature == 0.9  # From agents.yaml (overrides config.yaml 0.6)

    def test_load_config_order_matters(self, temp_dir, reset_global_config):
        """Test that changing the order of operations in load_config() breaks
        tests.

        This test specifically checks that:
        1. config.yaml is loaded first (line 32 in __main__.py)
        2. default agents are added second (line 33 in __main__.py, overrides config.yaml)
        3. agents.yaml is loaded last (line 38 in __main__.py, overrides everything)

        If you change the order of these operations, this test will fail.
        """
        # Create config.yaml with custom agent
        config_yaml = temp_dir / "config.yaml"
        config_data = {
            "llm": {"api_key": "test-key", "model": "gpt-4o-mini"},
            "agents": {
                "custom_agent": {
                    "base_class": "sgr_agent_core.agents.sgr_agent.SGRAgent",
                    "llm": {"api_key": "test-key", "model": "gpt-4o-mini"},
                    "tools": ["FinalAnswerTool"],
                }
            },
        }
        config_yaml.write_text(yaml.dump(config_data), encoding="utf-8")

        # Create agents.yaml that overrides custom_agent
        agents_yaml = temp_dir / "agents.yaml"
        agents_data = {
            "agents": {
                "custom_agent": {
                    "base_class": "sgr_agent_core.agents.sgr_agent.SGRAgent",
                    "llm": {"api_key": "test-key", "model": "gpt-4o-mini", "temperature": 0.7},
                    "tools": ["FinalAnswerTool"],
                }
            }
        }
        agents_yaml.write_text(yaml.dump(agents_data), encoding="utf-8")

        config = load_config(str(config_yaml), str(agents_yaml))

        # Verify final state: should have custom_agent from agents.yaml
        assert "custom_agent" in config.agents
        assert config.agents["custom_agent"].llm.temperature == 0.7  # From agents.yaml
        # No default agents should be loaded automatically
        assert len(config.agents) == 1

    def test_changing_load_config_order_breaks_tests(self, temp_dir, reset_global_config):
        """CRITICAL TEST: This test will FAIL if you change the order in load_config().

        This test verifies the exact order:
        1. GlobalConfig.from_yaml() - loads config.yaml and its agents
        2. config.definitions_from_yaml() - loads agents.yaml (overrides config.yaml)
        """
        # Create config.yaml with agent that conflicts with default
        config_yaml = temp_dir / "config.yaml"
        config_data = {
            "llm": {"api_key": "test-key", "model": "gpt-4o-mini"},
            "agents": {
                "sgr_agent": {
                    "base_class": "sgr_agent_core.agents.sgr_agent.SGRAgent",
                    "llm": {"api_key": "test-key", "model": "gpt-4o-mini", "temperature": 0.99},
                    "tools": ["FinalAnswerTool"],
                }
            },
        }
        config_yaml.write_text(yaml.dump(config_data), encoding="utf-8")

        # Create agents.yaml that overrides sgr_agent
        agents_yaml = temp_dir / "agents.yaml"
        agents_data = {
            "agents": {
                "sgr_agent": {
                    "base_class": "sgr_agent_core.agents.sgr_agent.SGRAgent",
                    "llm": {"api_key": "test-key", "model": "gpt-4o-mini", "temperature": 0.88},
                    "tools": ["FinalAnswerTool"],
                }
            }
        }
        agents_yaml.write_text(yaml.dump(agents_data), encoding="utf-8")

        config = load_config(str(config_yaml), str(agents_yaml))

        # Final temperature should be 0.88 from agents.yaml
        # Correct order: config.yaml (0.99) -> agents.yaml (0.88, overrides)
        actual_temp = config.agents["sgr_agent"].llm.temperature
        assert actual_temp == 0.88, (
            f"Temperature should be 0.88 from agents.yaml, but got {actual_temp}. "
            f"This means the order in load_config() was changed! "
            f"Expected order: config.yaml -> agents.yaml"
        )

    def test_config_agents_replace_core_class_names(self, temp_dir, reset_global_config):
        """Test that agents from config with names matching core class names
        replace existing definitions.

        If an agent in config has the same name as a core agent class
        (e.g., 'sgr_agent'), it should replace any existing definition
        with that name.
        """
        # Create config.yaml with agent that has same name as core class
        config_yaml = temp_dir / "config.yaml"
        config_data = {
            "llm": {"api_key": "test-key", "model": "gpt-4o-mini"},
            "agents": {
                "sgr_agent": {
                    "base_class": "examples.sgr_deep_research.agents.ResearchSGRAgent",
                    "llm": {"api_key": "test-key", "model": "gpt-4o-mini", "temperature": 0.9},
                    "tools": ["FinalAnswerTool"],
                },
                "tool_calling_agent": {
                    "base_class": "examples.sgr_deep_research.agents.ResearchToolCallingAgent",
                    "llm": {"api_key": "test-key", "model": "gpt-4o-mini", "temperature": 0.7},
                    "tools": ["FinalAnswerTool"],
                },
            },
        }
        config_yaml.write_text(yaml.dump(config_data), encoding="utf-8")

        # Load config
        config = load_config(str(config_yaml), None)

        # Verify that config agents replaced any existing definitions
        assert "sgr_agent" in config.agents
        assert "tool_calling_agent" in config.agents

        # Verify they use the classes from config, not core defaults
        assert config.agents["sgr_agent"].llm.temperature == 0.9
        assert config.agents["tool_calling_agent"].llm.temperature == 0.7

        # Verify base_class is from config (examples.sgr_deep_research), not core
        base_class_name = config.agents["sgr_agent"].base_class.__name__
        assert base_class_name == "ResearchSGRAgent", f"Expected ResearchSGRAgent, got {base_class_name}"
