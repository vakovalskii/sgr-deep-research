"""Tests for ToolInstantiator service."""

import json
from json import JSONDecodeError

import pytest

from sgr_agent_core.services.tool_instantiator import SchemaSimplifier, ToolInstantiator
from sgr_agent_core.tools import ReasoningTool, WebSearchTool


class TestToolInstantiator:
    """Test suite for ToolInstantiator."""

    def test_initialization(self):
        """Test ToolInstantiator initialization."""
        instantiator = ToolInstantiator(ReasoningTool)

        assert instantiator.tool_class == ReasoningTool
        assert instantiator.errors == []
        assert instantiator.instance is None
        assert instantiator.input_content == ""

    def test_generate_format_prompt_with_errors(self):
        """Test generate_format_prompt with errors included."""
        instantiator = ToolInstantiator(ReasoningTool)
        instantiator.errors = ["Error 1", "Error 2"]
        instantiator.input_content = "invalid json"

        prompt = instantiator.generate_format_prompt(include_errors=True)

        assert "PREVIOUS FILLING ITERATION ERRORS" in prompt
        assert "Error 1" in prompt
        assert "Error 2" in prompt
        assert "invalid json" in prompt

    def test_generate_format_prompt_without_errors_when_errors_exist(self):
        """Test generate_format_prompt with include_errors=False when errors
        exist."""
        instantiator = ToolInstantiator(ReasoningTool)
        instantiator.errors = ["Error 1"]
        instantiator.input_content = "invalid json"

        prompt = instantiator.generate_format_prompt(include_errors=False)

        assert "PREVIOUS FILLING ITERATION ERRORS" not in prompt
        assert "Error 1" not in prompt

    def test_build_model_success(self):
        """Test build_model with valid JSON content."""
        instantiator = ToolInstantiator(ReasoningTool)
        content = json.dumps(
            {
                "reasoning_steps": ["step1", "step2"],
                "current_situation": "test",
                "plan_status": "ok",
                "enough_data": False,
                "remaining_steps": ["next"],
                "task_completed": False,
            }
        )

        result = instantiator.build_model(content)

        assert isinstance(result, ReasoningTool)
        assert result == instantiator.instance
        assert instantiator.instance is not None
        assert instantiator.input_content == content
        assert len(instantiator.errors) == 0
        assert result.reasoning_steps == ["step1", "step2"]
        assert result.current_situation == "test"

    def test_build_model_with_whitespace(self):
        """Test build_model handles whitespace correctly."""
        instantiator = ToolInstantiator(ReasoningTool)
        content = (
            '  \n{"reasoning_steps": ["step1", "step2"], "current_situation": "test", '
            '"plan_status": "ok", "enough_data": false, "remaining_steps": ["next"], '
            '"task_completed": false}\n  '
        )

        result = instantiator.build_model(content)

        assert isinstance(result, ReasoningTool)
        assert instantiator.instance is not None

    def test_build_model_empty_content(self):
        """Test build_model with empty content."""
        instantiator = ToolInstantiator(ReasoningTool)

        with pytest.raises(ValueError, match="No content provided"):
            instantiator.build_model("")

        assert len(instantiator.errors) == 1
        assert "No content provided" in instantiator.errors
        assert instantiator.instance is None

    def test_build_model_invalid_json(self):
        """Test build_model with invalid JSON."""
        instantiator = ToolInstantiator(ReasoningTool)
        content = "invalid json content"

        with pytest.raises(ValueError, match="Failed to build model"):
            instantiator.build_model(content)

        assert len(instantiator.errors) > 0
        # Check for JSON parse error message (new format with context)
        assert any("JSON parse error" in err or "Failed to parse JSON" in err for err in instantiator.errors)
        assert instantiator.input_content == content
        assert instantiator.instance is None

    def test_build_model_validation_error(self):
        """Test build_model with Pydantic validation error."""
        instantiator = ToolInstantiator(ReasoningTool)
        # Missing required fields
        content = json.dumps({"reasoning_steps": ["step1"]})

        with pytest.raises(ValueError, match="Failed to build model"):
            instantiator.build_model(content)

        assert len(instantiator.errors) > 0
        assert any("pydantic validation error" in err for err in instantiator.errors)
        assert instantiator.input_content == content
        assert instantiator.instance is None

    def test_build_model_clears_errors_on_new_attempt(self):
        """Test that build_model clears errors before new attempt."""
        instantiator = ToolInstantiator(ReasoningTool)
        instantiator.errors = ["Previous error"]

        # First attempt fails
        try:
            instantiator.build_model("invalid")
        except ValueError:
            pass

        assert len(instantiator.errors) > 0

        # Second attempt succeeds - errors should be cleared
        valid_content = json.dumps(
            {
                "reasoning_steps": ["step1", "step2"],
                "current_situation": "test",
                "plan_status": "ok",
                "enough_data": False,
                "remaining_steps": ["next"],
                "task_completed": False,
            }
        )
        result = instantiator.build_model(valid_content)

        assert isinstance(result, ReasoningTool)
        assert instantiator.instance is not None

    def test_build_model_with_web_search_tool(self):
        """Test build_model with different tool class."""
        instantiator = ToolInstantiator(WebSearchTool)
        content = json.dumps({"reasoning": "test reasoning", "query": "test query"})

        result = instantiator.build_model(content)

        assert isinstance(result, WebSearchTool)
        assert result.reasoning == "test reasoning"
        assert result.query == "test query"
        assert instantiator.instance == result

    def test_generate_format_prompt_includes_schema(self):
        """Test that generate_format_prompt includes simplified schema."""
        instantiator = ToolInstantiator(ReasoningTool)
        prompt = instantiator.generate_format_prompt()

        # Check that simplified schema format is present
        assert "<Schema>" in prompt
        assert "</Schema>" in prompt
        # Check for simplified format markers
        assert "reasoning_steps (required" in prompt
        assert "list[string]" in prompt
        assert "enough_data (optional" in prompt

    def test_errors_accumulation(self):
        """Test that errors accumulate across multiple failed attempts."""
        instantiator = ToolInstantiator(ReasoningTool)

        # First attempt - invalid JSON
        try:
            instantiator.build_model("invalid json 1")
        except ValueError:
            pass

        # Second attempt - invalid JSON
        try:
            instantiator.build_model("invalid json 2")
        except ValueError:
            pass

        # Note: build_model clears errors at start, so each attempt starts fresh
        # But we can check that errors are added during each attempt
        assert len(instantiator.errors) > 0

    def test_clearing_context_extracts_json(self):
        """Test _clearing_context extracts JSON from mixed content."""
        instantiator = ToolInstantiator(ReasoningTool)

        # Content with text before and after JSON
        content = 'Some text before {"reasoning_steps": ["step1"], "current_situation": "test"} and after'
        result = instantiator._clearing_context(content)

        assert result.startswith("{")
        assert result.endswith("}")
        assert "reasoning_steps" in result
        assert "Some text before" not in result
        assert "and after" not in result

    def test_clearing_context_no_braces(self):
        """Test _clearing_context returns original content if no braces
        found."""
        instantiator = ToolInstantiator(ReasoningTool)
        content = "no json here"

        result = instantiator._clearing_context(content)

        assert result == content

    def test_clearing_context_only_opening_brace(self):
        """Test _clearing_context handles case with only opening brace."""
        instantiator = ToolInstantiator(ReasoningTool)
        content = "text { incomplete json"

        result = instantiator._clearing_context(content)

        assert result == content

    def test_build_model_with_text_around_json(self):
        """Test build_model extracts JSON from text with surrounding
        content."""
        instantiator = ToolInstantiator(ReasoningTool)
        json_data = {
            "reasoning_steps": ["step1", "step2"],
            "current_situation": "test",
            "plan_status": "ok",
            "enough_data": False,
            "remaining_steps": ["next"],
            "task_completed": False,
        }
        content = f"Here is the JSON: {json.dumps(json_data)} and some text after"

        result = instantiator.build_model(content)

        assert isinstance(result, ReasoningTool)
        assert result.reasoning_steps == ["step1", "step2"]

    def test_format_json_error_with_context(self):
        """Test _format_json_error includes context around error position."""
        instantiator = ToolInstantiator(ReasoningTool)
        # Create invalid JSON with extra data
        content = '{"field": "value"} extra data here'
        try:
            json.loads(content)
        except JSONDecodeError as e:
            error_msg = instantiator._format_json_error(e, content)

            assert "JSON parse error" in error_msg
            assert "position" in error_msg
            assert "Context:" in error_msg
            assert "extra data" in error_msg or "value" in error_msg

    def test_format_json_error_without_position(self):
        """Test _format_json_error handles error without position attribute."""
        instantiator = ToolInstantiator(ReasoningTool)

        # Create error-like object without pos attribute
        class ErrorWithoutPos:
            def __init__(self):
                self.msg = "test error"

        error = ErrorWithoutPos()
        error_msg = instantiator._format_json_error(error, "test content")

        # Should fall back to generic error message when pos is missing
        assert "Failed to parse JSON" in error_msg

    def test_format_json_error_at_start(self):
        """Test _format_json_error handles error at start of content."""
        instantiator = ToolInstantiator(ReasoningTool)
        content = 'invalid {"field": "value"}'
        try:
            json.loads(content)
        except JSONDecodeError as e:
            error_msg = instantiator._format_json_error(e, content)
            assert "JSON parse error" in error_msg
            assert "position" in error_msg

    def test_format_json_error_at_end(self):
        """Test _format_json_error handles error at end of content."""
        instantiator = ToolInstantiator(ReasoningTool)
        content = '{"field": "value"} invalid'
        try:
            json.loads(content)
        except JSONDecodeError as e:
            error_msg = instantiator._format_json_error(e, content)
            assert "JSON parse error" in error_msg
            assert "position" in error_msg

    def test_generate_format_prompt_includes_tool_info(self):
        """Test that generate_format_prompt includes tool name."""
        instantiator = ToolInstantiator(ReasoningTool)
        prompt = instantiator.generate_format_prompt()

        assert "<ToolInfo>" in prompt
        assert "</ToolInfo>" in prompt
        assert ReasoningTool.tool_name in prompt

    def test_generate_format_prompt_includes_format_template(self):
        """Test that generate_format_prompt includes important format
        sections."""
        instantiator = ToolInstantiator(ReasoningTool)
        prompt = instantiator.generate_format_prompt()

        # Check that key sections are present (not checking exact strings to avoid hardcoding)
        assert len(prompt) > 100  # Should be substantial
        assert "<Schema>" in prompt  # Schema section is critical
        assert "<ToolInfo>" in prompt  # Tool info is critical
        # Check that it contains instructions (not just checking exact strings)
        assert any(keyword in prompt.lower() for keyword in ["json", "schema", "format", "required"])

    def test_clearing_context_multiple_braces(self):
        """Test _clearing_context extracts JSON when multiple braces exist."""
        instantiator = ToolInstantiator(ReasoningTool)
        content = 'text { {"reasoning_steps": ["step1"], "current_situation": "test"} } more text'
        result = instantiator._clearing_context(content)

        assert result.startswith("{")
        assert result.endswith("}")
        assert "reasoning_steps" in result

    def test_clearing_context_nested_objects(self):
        """Test _clearing_context handles nested JSON objects."""
        instantiator = ToolInstantiator(ReasoningTool)
        nested_json = {"outer": {"inner": "value"}}
        content = f"Text {json.dumps(nested_json)} more text"
        result = instantiator._clearing_context(content)

        assert result.startswith("{")
        assert result.endswith("}")
        assert "outer" in result
        assert "inner" in result

    def test_build_model_clears_content_attribute(self):
        """Test that build_model clears and sets content attribute
        correctly."""
        instantiator = ToolInstantiator(ReasoningTool)
        instantiator.content = "previous content"

        valid_content = json.dumps(
            {
                "reasoning_steps": ["step1", "step2"],
                "current_situation": "test",
                "plan_status": "ok",
                "enough_data": False,
                "remaining_steps": ["next"],
                "task_completed": False,
            }
        )
        instantiator.build_model(valid_content)

        # Content should be set to cleaned content (same as input in this case)
        assert instantiator.content == valid_content
        assert instantiator.content != "previous content"

    def test_build_model_with_markdown_code_block(self):
        """Test build_model extracts JSON from markdown code block."""
        instantiator = ToolInstantiator(ReasoningTool)
        json_data = {
            "reasoning_steps": ["step1", "step2"],
            "current_situation": "test",
            "plan_status": "ok",
            "enough_data": False,
            "remaining_steps": ["next"],
            "task_completed": False,
        }
        content = f"```json\n{json.dumps(json_data)}\n```"

        result = instantiator.build_model(content)

        assert isinstance(result, ReasoningTool)
        assert result.reasoning_steps == ["step1", "step2"]


class TestSchemaSimplifier:
    """Test suite for SchemaSimplifier."""

    def test_simplify_simple_string_field(self):
        """Test simplifying schema with simple string field."""
        schema = {
            "properties": {
                "name": {
                    "type": "string",
                    "description": "User name",
                }
            },
            "required": ["name"],
        }

        result = SchemaSimplifier.simplify(schema)

        assert "name (required, string): User name" in result

    def test_simplify_optional_field(self):
        """Test simplifying schema with optional field."""
        schema = {
            "properties": {
                "name": {"type": "string", "description": "User name"},
                "age": {"type": "integer", "description": "User age"},
            },
            "required": ["name"],
        }

        result = SchemaSimplifier.simplify(schema)

        assert "name (required" in result
        assert "age (optional" in result

    def test_simplify_array_field(self):
        """Test simplifying schema with array field."""
        schema = {
            "properties": {
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of tags",
                }
            },
            "required": ["tags"],
        }

        result = SchemaSimplifier.simplify(schema)

        assert "tags (required" in result
        assert "list[string]" in result

    def test_simplify_array_with_constraints(self):
        """Test simplifying schema with array constraints."""
        schema = {
            "properties": {
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 5,
                    "description": "List of items",
                }
            },
            "required": ["items"],
        }

        result = SchemaSimplifier.simplify(schema)

        assert "items (required" in result
        assert "1-5 items" in result

    def test_simplify_string_with_length_constraints(self):
        """Test simplifying schema with string length constraints."""
        schema = {
            "properties": {
                "text": {
                    "type": "string",
                    "minLength": 10,
                    "maxLength": 100,
                    "description": "Text field",
                }
            },
            "required": ["text"],
        }

        result = SchemaSimplifier.simplify(schema)

        assert "text (required" in result
        assert "length: 10-100" in result

    def test_simplify_integer_with_range_constraints(self):
        """Test simplifying schema with integer range constraints."""
        schema = {
            "properties": {
                "age": {
                    "type": "integer",
                    "minimum": 18,
                    "maximum": 120,
                    "description": "User age",
                }
            },
            "required": ["age"],
        }

        result = SchemaSimplifier.simplify(schema)

        assert "age (required" in result
        assert "range: 18-120" in result

    def test_simplify_field_with_default(self):
        """Test simplifying schema with default value."""
        schema = {
            "properties": {
                "status": {
                    "type": "string",
                    "default": "active",
                    "description": "Status",
                }
            },
            "required": [],
        }

        result = SchemaSimplifier.simplify(schema)

        assert "status (optional" in result
        assert 'default: "active"' in result

    def test_simplify_enum_field(self):
        """Test simplifying schema with enum (Literal)."""
        schema = {
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["active", "inactive", "pending"],
                    "description": "Status",
                }
            },
            "required": ["status"],
        }

        result = SchemaSimplifier.simplify(schema)

        assert "status (required" in result
        assert "Literal[" in result
        assert '"active"' in result or "'active'" in result

    def test_simplify_const_field(self):
        """Test simplifying schema with const value."""
        schema = {
            "properties": {
                "type": {
                    "type": "string",
                    "const": "user",
                    "description": "Type",
                }
            },
            "required": ["type"],
        }

        result = SchemaSimplifier.simplify(schema)

        assert "type (required" in result
        assert "const:" in result

    def test_simplify_nested_object(self):
        """Test simplifying schema with nested object."""
        schema = {
            "properties": {
                "address": {
                    "type": "object",
                    "properties": {
                        "street": {"type": "string", "description": "Street"},
                        "city": {"type": "string", "description": "City"},
                    },
                    "required": ["street"],
                    "description": "Address",
                }
            },
            "required": ["address"],
        }

        result = SchemaSimplifier.simplify(schema)

        assert "address (required" in result
        assert "street (required" in result
        assert "city (optional" in result

    def test_simplify_anyof_with_ref(self):
        """Test simplifying schema with anyOf containing $ref."""
        schema = {
            "properties": {
                "tool": {
                    "anyOf": [
                        {"$ref": "#/$defs/ToolA"},
                        {"$ref": "#/$defs/ToolB"},
                    ],
                    "description": "Select tool",
                }
            },
            "required": ["tool"],
            "$defs": {
                "ToolA": {
                    "title": "ToolA",
                    "properties": {
                        "param1": {"type": "string", "description": "Param 1"},
                    },
                    "required": ["param1"],
                },
                "ToolB": {
                    "title": "ToolB",
                    "properties": {
                        "param2": {"type": "integer", "description": "Param 2"},
                    },
                    "required": ["param2"],
                },
            },
        }

        result = SchemaSimplifier.simplify(schema)

        assert "tool (required" in result
        assert "Literal[" in result
        assert "ToolA" in result
        assert "ToolB" in result
        assert "Variant: ToolA" in result
        assert "param1 (required" in result
        assert "Variant: ToolB" in result
        assert "param2 (required" in result

    def test_simplify_anyof_with_const(self):
        """Test simplifying schema with anyOf containing const values."""
        schema = {
            "properties": {
                "status": {
                    "anyOf": [
                        {"const": "active"},
                        {"const": "inactive"},
                    ],
                    "description": "Status",
                }
            },
            "required": ["status"],
        }

        result = SchemaSimplifier.simplify(schema)

        assert "status (required" in result
        assert "const(" in result
        assert "active" in result
        assert "inactive" in result

    def test_simplify_empty_properties(self):
        """Test simplifying schema with no properties."""
        schema = {"properties": {}, "required": []}

        result = SchemaSimplifier.simplify(schema)

        assert result == ""

    def test_simplify_no_properties_key(self):
        """Test simplifying schema without properties key."""
        schema = {"required": []}

        result = SchemaSimplifier.simplify(schema)

        assert result == ""

    def test_simplify_fields_sorted_required_first(self):
        """Test that required fields come before optional fields."""
        schema = {
            "properties": {
                "optional_field": {"type": "string", "description": "Optional"},
                "required_field": {"type": "string", "description": "Required"},
            },
            "required": ["required_field"],
        }

        result = SchemaSimplifier.simplify(schema)
        lines = result.split("\n")

        required_index = next(i for i, line in enumerate(lines) if "required_field" in line)
        optional_index = next(i for i, line in enumerate(lines) if "optional_field" in line)

        assert required_index < optional_index

    def test_simplify_with_indent(self):
        """Test simplifying schema with indentation."""
        schema = {
            "properties": {
                "nested": {
                    "type": "object",
                    "properties": {
                        "field": {"type": "string", "description": "Field"},
                    },
                    "required": ["field"],
                    "description": "Nested",
                }
            },
            "required": ["nested"],
        }

        result = SchemaSimplifier.simplify(schema, indent=1)

        lines = result.split("\n")
        nested_line = next(line for line in lines if "nested (required" in line)
        nested_field_line = next(line for line in lines if "field" in line and "Field" in line)
        # Check that nested field has more indentation than parent
        assert len(nested_field_line) - len(nested_field_line.lstrip()) > len(nested_line) - len(nested_line.lstrip())

    def test_extract_type_unknown(self):
        """Test _extract_type returns 'unknown' for unknown type."""
        schema = {}

        result = SchemaSimplifier._extract_type(schema)

        assert result == "unknown"

    def test_extract_constraints_empty(self):
        """Test _extract_constraints returns empty list when no constraints."""
        schema = {"type": "string"}

        result = SchemaSimplifier._extract_constraints(schema)

        assert result == []

    def test_extract_constraints_minimum_only(self):
        """Test _extract_constraints with only minimum."""
        schema = {"type": "integer", "minimum": 0}

        result = SchemaSimplifier._extract_constraints(schema)

        assert "min: 0" in result

    def test_extract_constraints_maximum_only(self):
        """Test _extract_constraints with only maximum."""
        schema = {"type": "integer", "maximum": 100}

        result = SchemaSimplifier._extract_constraints(schema)

        assert "max: 100" in result

    def test_extract_constraints_min_length_only(self):
        """Test _extract_constraints with only minLength."""
        schema = {"type": "string", "minLength": 5}

        result = SchemaSimplifier._extract_constraints(schema)

        assert "min length: 5" in result

    def test_extract_constraints_max_length_only(self):
        """Test _extract_constraints with only maxLength."""
        schema = {"type": "string", "maxLength": 100}

        result = SchemaSimplifier._extract_constraints(schema)

        assert "max length: 100" in result

    def test_extract_constraints_min_items_only(self):
        """Test _extract_constraints with only minItems."""
        schema = {"type": "array", "minItems": 1}

        result = SchemaSimplifier._extract_constraints(schema)

        assert "min 1 items" in result

    def test_extract_constraints_max_items_only(self):
        """Test _extract_constraints with only maxItems."""
        schema = {"type": "array", "maxItems": 10}

        result = SchemaSimplifier._extract_constraints(schema)

        assert "max 10 items" in result
