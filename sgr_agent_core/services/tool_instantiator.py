import json
from json import JSONDecodeError
from typing import TYPE_CHECKING

from pydantic import ValidationError

if TYPE_CHECKING:
    from sgr_agent_core.base_tool import BaseTool


class SchemaSimplifier:
    """Converts JSON schemas to structured text format."""

    @classmethod
    def simplify(cls, schema: dict, indent: int = 0) -> str:
        """Convert JSON schema to structured text format (variant 3 - compact inline).

        Format: - field_name (required/optional, тип, ограничения): описание

        Args:
            schema: JSON schema dictionary from model_json_schema()
            indent: Current indentation level for nested structures

        Returns:
            Formatted text representation of schema
        """
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        defs = schema.get("$defs", {})

        if not properties:
            return ""

        required_fields = [(name, props) for name, props in properties.items() if name in required]
        optional_fields = [(name, props) for name, props in properties.items() if name not in required]
        sorted_fields = required_fields + optional_fields

        result_lines = []
        indent_str = "  " * indent

        for field_name, field_schema in sorted_fields:
            is_required = field_name in required
            req_text = "required" if is_required else "optional"

            field_type = cls._extract_type(field_schema, defs)
            constraints = cls._extract_constraints(field_schema)
            description = field_schema.get("description", "")

            # Format line: - field_name (required/optional, type, restrictions): description
            type_constraints = ", ".join([field_type, *constraints])
            line = f"{indent_str}- {field_name} ({req_text}, {type_constraints}): {description}"

            result_lines.append(line)

            # Handle anyOf with $ref to $defs - expand nested schemas
            if "anyOf" in field_schema and defs:
                for variant in field_schema["anyOf"]:
                    if "$ref" in variant:
                        ref_path = variant["$ref"]
                        if ref_path.startswith("#/$defs/"):
                            def_name = ref_path.replace("#/$defs/", "")
                            if def_name in defs:
                                def_schema = defs[def_name]
                                # Get schema name from title or def_name
                                schema_name = def_schema.get("title", def_name)
                                # Add schema name as header
                                nested_indent_str = "  " * (indent + 1)
                                result_lines.append(f"{nested_indent_str}Variant: {schema_name}")
                                # Recursively simplify the schema from $defs
                                nested = cls.simplify(def_schema, indent + 2)
                                if nested:
                                    result_lines.append(nested)

            # Handle nested objects recursively
            if field_schema.get("type") == "object" and "properties" in field_schema:
                nested = cls.simplify(field_schema, indent + 1)
                if nested:
                    result_lines.append(nested)

        return "\n".join(result_lines)

    @classmethod
    def _extract_type(cls, field_schema: dict, defs: dict | None = None) -> str:
        """Extract type string from field schema.

        Args:
            field_schema: Field schema dictionary
            defs: Definitions dictionary for resolving $ref (optional)

        Returns:
            Type string representation
        """
        if defs is None:
            defs = {}
        # Handle const
        if "const" in field_schema:
            base_type = field_schema.get("type", "string")
            const_value = field_schema["const"]
            return f"{base_type} (const: {json.dumps(const_value)})"

        # Handle enum (Literal)
        if "enum" in field_schema:
            enum_values = field_schema["enum"]
            enum_str = ", ".join(json.dumps(v) for v in enum_values)
            return f"Literal[{enum_str}]"

        # Handle anyOf (Union)
        if "anyOf" in field_schema:
            types = []
            const_values = []
            for variant in field_schema["anyOf"]:
                if "$ref" in variant:
                    # Resolve $ref
                    ref_path = variant["$ref"]
                    if ref_path.startswith("#/$defs/") and defs:
                        def_name = ref_path.replace("#/$defs/", "")
                        if def_name in defs:
                            # Use title or def_name from schema
                            def_schema = defs[def_name]
                            type_name = def_schema.get("title", def_name)
                            types.append(type_name)
                        else:
                            # Use def_name as-is if not in defs
                            types.append(def_name)
                    else:
                        types.append(ref_path)
                elif "const" in variant:
                    # Collect const values
                    const_values.append(variant["const"])
                else:
                    # Extract type from variant
                    variant_type = cls._extract_type(variant, defs)
                    types.append(variant_type)

            # If all variants are const values, format as const(value1 OR value2 OR value3)
            if const_values and not types:
                const_str = " OR ".join(json.dumps(v) for v in const_values)
                return f"const({const_str})"

            # Wrap Union types in Literal format
            if types:
                types_str = ", ".join(types)
                return f"Literal[{types_str}]"

            return "unknown"

        # Handle array
        if field_schema.get("type") == "array":
            items = field_schema.get("items", {})
            if isinstance(items, dict):
                element_type = cls._extract_type(items, defs)
                return f"list[{element_type}]"
            return "list"

        # Handle object
        if field_schema.get("type") == "object":
            if "properties" in field_schema:
                return "object"
            return "object"

        # Simple types
        field_type = field_schema.get("type", "unknown")
        return field_type

    @classmethod
    def _extract_constraints(cls, field_schema: dict) -> list[str]:
        """Extract constraints string from field schema.

        Args:
            field_schema: Field schema dictionary

        Returns:
            Constraints string (empty if no constraints)
        """
        constraints = []

        # Default value
        if "default" in field_schema:
            default_val = field_schema["default"]
            constraints.append(f"default: {json.dumps(default_val)}")

        # Numeric range
        if "minimum" in field_schema and "maximum" in field_schema:
            min_val = field_schema["minimum"]
            max_val = field_schema["maximum"]
            constraints.append(f"range: {min_val}-{max_val}")
        elif "minimum" in field_schema:
            constraints.append(f"min: {field_schema['minimum']}")
        elif "maximum" in field_schema:
            constraints.append(f"max: {field_schema['maximum']}")

        # String length
        if "minLength" in field_schema and "maxLength" in field_schema:
            min_len = field_schema["minLength"]
            max_len = field_schema["maxLength"]
            constraints.append(f"length: {min_len}-{max_len}")
        elif "minLength" in field_schema:
            constraints.append(f"min length: {field_schema['minLength']}")
        elif "maxLength" in field_schema:
            constraints.append(f"max length: {field_schema['maxLength']}")

        # Array items
        if "minItems" in field_schema and "maxItems" in field_schema:
            min_items = field_schema["minItems"]
            max_items = field_schema["maxItems"]
            constraints.append(f"{min_items}-{max_items} items")
        elif "minItems" in field_schema:
            constraints.append(f"min {field_schema['minItems']} items")
        elif "maxItems" in field_schema:
            constraints.append(f"max {field_schema['maxItems']} items")

        return constraints


# YESS im trying in SO inside a framework
class ToolInstantiator:
    """Structured Output like Service for formatting, parsing raw LLM context
    and building tool instances."""

    _FORMAT_PROMPT_TEMPLATE = (
        "CRITICAL: Generate a JSON OBJECT with actual data values, NOT the schema definition.\n\n"
        "================================================================================\n"
        "HOW TO READ THE SCHEMA (TEXT FORMAT):\n"
        "================================================================================\n\n"
        "  FORMAT: - field_name (required/optional, type, constraints): description\n\n"
        "  EXAMPLES:\n"
        "    - name (required, string, max length: 100): User's full name\n"
        "    - age (optional, integer, range: 18-120, default: 25): User's age\n"
        "    - tags (required, list[string], 1-5 items): List of tags\n"
        '    - status (required, const("active" OR "inactive")): Account status\n'
        "    - tool (required, Literal[ToolA, ToolB, ToolC]): Select one tool\n"
        "      Variant: ToolA\n"
        "        - param1 (required, string): Parameter 1\n"
        "        - param2 (optional, integer): Parameter 2\n"
        "      Variant: ToolB\n"
        "        - param3 (required, boolean): Parameter 3\n\n"
        "  KEY CONCEPTS:\n"
        "  - required/optional: Whether the field must be provided\n"
        "  - type: Data type (string, integer, boolean, list[type], Literal[...], etc.)\n"
        "  - constraints: Limits like 'range: 1-10', 'max length: 300', '2-3 items', 'default: value'\n"
        "  - Literal[...]: Union type - choose ONE of the listed options\n"
        "  - Variant: sections: For nested unions, select appropriate variant and fill its fields\n"
        "  - const(value): Field must have exactly this value (no other options)\n\n"
        "HOW TO GENERATE VALUES:\n"
        "- Use the conversation context above to understand what the user wants\n"
        "- Use the tool description to understand what this tool does\n"
        "- Fill each field with appropriate values based on its schema description, the context and tool purpose\n"
        "- Match the types and constraints shown in the schema\n"
        "- For Union types, choose the appropriate variant based on context\n\n"
        "REQUIREMENTS:\n"
        "- Output ONLY raw JSON object (no markdown, no code blocks, no explanations)\n"
        "- Fill fields with actual values matching the schema types\n"
        "- All strings must be quoted, arrays in [], objects in {}\n"
        "- Respect all constraints (min/max values, lengths, item counts, etc.)\n\n"
        "<GoodAnswerExample>\n"
        '{"name": "John Doe", "age": 30, "tags": ["tag1", "tag2"], '
        '"status": "active", "tool": "ToolA", "param1": "value1", "param2": 42}\n'
        "</GoodAnswerExample>\n\n"
        "<WrongAnswerExample>\n"
        '{"name": {"type": "string", "description": "User\'s full name"}, '
        '"age": {"type": "integer", "range": "18-120"}}\n'
        "</WrongAnswerExample>\n\n"
        "<WrongAnswerExample>\n"
        '```json\n{"name": "John Doe", "age": 30}\n```\n'
        "</WrongAnswerExample>\n\n"
        "The schema below shows the STRUCTURE in text format - provide VALUES in JSON that match it.\n\n"
    )

    def __init__(self, tool_class: type["BaseTool"]):
        """Initialize tool instantiator.

        Args:
            tool_class: Tool class to instantiate
        """
        self.tool_class = tool_class
        self.errors: list[str] = []
        self.instance: "BaseTool | None" = None
        self.input_content: str = ""

    def _clearing_context(self, content: str) -> str:
        """Extract JSON object from content by finding first { and last }.

        Args:
            content: Raw content that may contain JSON mixed with other text

        Returns:
            Extracted JSON string (from first { to last })
        """
        first_brace = content.find("{")
        if first_brace == -1:
            return content

        last_brace = content.rfind("}")
        if last_brace == -1 or last_brace < first_brace:
            return content

        return content[first_brace : last_brace + 1]

    def _format_json_error(self, error: JSONDecodeError, content: str) -> str:
        """Format JSON decode error with context around the error position.

        Args:
            error: JSONDecodeError exception
            content: Content that failed to parse

        Returns:
            Formatted error message with context
        """
        error_pos = getattr(error, "pos", None)
        if error_pos is None:
            return f"Failed to parse JSON: {error}"

        # Calculate context window (±20 characters)
        context_size = 20
        start = max(0, error_pos - context_size)
        end = min(len(content), error_pos + context_size)

        context_before = content[start:error_pos]
        context_after = content[error_pos:end]

        # Show position and context
        error_msg = (
            f"JSON parse error at position {error_pos}: {error.msg}\n"
            f"Context: ...{context_before}[Error here]{context_after}..."
        )

        return error_msg

    def generate_format_prompt(
        self,
        include_errors: bool = True,
    ) -> str:
        """Generate a prompt describing the expected format for LLM.

        Args:
            mode: Which parameters to include:
                - "all": Show all parameters (default)
                - "required": Show only required parameters
                - "unfilled": Show only parameters where value is PydanticUndefined
            include_errors: If True, include error messages for parameters with validation errors

        Returns:
            Format description string
        """
        simplified_schema = SchemaSimplifier.simplify(self.tool_class.model_json_schema())

        prompt = (
            f"<ToolInfo>\n"
            f"Tool name: {self.tool_class.tool_name}\n"
            f"Tool description: {self.tool_class.description}\n"
            f"</ToolInfo>\n\n"
            f"{self._FORMAT_PROMPT_TEMPLATE}"
            f"<Schema>\n"
            f"{simplified_schema}\n"
            f"</Schema>\n\n"
        )

        # Show errors at the end if requested
        if include_errors and self.errors:
            prompt += "PREVIOUS FILLING ITERATION ERRORS. AVOID OR FIX IT:\n"
            prompt += "fault content: \n" + self.input_content + "\n"
            for error in self.errors:
                prompt += f"  - {error}\n"

        return prompt

    def build_model(self, content: str) -> "BaseTool":
        """Build tool model instance from parsed parameters.

        Args:
            content: Raw content from LLM to parse

        Returns:
            Tool instance

        Raises:
            ValueError: If required parameters are missing or model creation fails
        """
        self.content = ""
        self.errors.clear()
        if not content:
            self.errors.append("No content provided")
            raise ValueError("No content provided")
        self.input_content = content

        try:
            cleaned_content = self._clearing_context(content)
            self.content = cleaned_content  # Save cleaned content for debugging
            self.instance = self.tool_class(**json.loads(cleaned_content))
            return self.instance
        except ValidationError as e:
            for err in e.errors():
                self.errors.append(
                    f"pydantic validation error - type: {err['type']} - " f"field: {err['loc']} - {err['msg']}"
                )
            raise ValueError("Failed to build model") from e
        except JSONDecodeError as e:
            error_content = cleaned_content if "cleaned_content" in locals() else self.content or content
            error_msg = self._format_json_error(e, error_content)
            self.errors.append(error_msg)
            raise ValueError("Failed to build model") from e
        except ValueError as e:
            self.errors.append(f"Failed to parse JSON: {e}")
            raise ValueError("Failed to build model") from e
