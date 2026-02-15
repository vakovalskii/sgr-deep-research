from __future__ import annotations

import re
from typing import TYPE_CHECKING

from rank_bm25 import BM25Okapi

if TYPE_CHECKING:
    from sgr_agent_core.base_tool import BaseTool


class ToolFilterService:
    """Stateless service for filtering tools by relevance to a query.

    Uses BM25 ranking + regex keyword overlap to find tools matching a
    query.
    """

    @classmethod
    def filter_tools(
        cls,
        query: str,
        tools: list[type[BaseTool]],
        bm25_threshold: float = 0.1,
    ) -> list[type[BaseTool]]:
        """Filter tools by relevance to query using BM25 + regex.

        Args:
            query: Natural language description of needed capability.
            tools: Full list of available tool classes.
            bm25_threshold: Minimum BM25 score to consider a tool relevant.

        Returns:
            List of tool classes matching the query.
        """
        if not query or not query.strip() or not tools:
            return list(tools)

        query_lower = query.strip().lower()

        tool_documents = []
        for tool in tools:
            tool_name = (tool.tool_name or tool.__name__).lower()
            tool_description = (tool.description or "").lower()
            tool_documents.append(f"{tool_name} {tool_description}")

        tokenized_docs = [doc.split() for doc in tool_documents]
        bm25 = BM25Okapi(tokenized_docs)

        query_tokens = query_lower.split()
        scores = bm25.get_scores(query_tokens)

        query_words = set(re.findall(r"\b\w+\b", query_lower))

        filtered = []
        for i, tool in enumerate(tools):
            bm25_score = scores[i]

            tool_words = set(re.findall(r"\b\w+\b", tool_documents[i]))
            has_regex_match = bool(query_words & tool_words)

            if bm25_score > bm25_threshold or has_regex_match:
                filtered.append(tool)

        return filtered

    @classmethod
    def get_tool_summaries(cls, tools: list[type[BaseTool]]) -> str:
        """Format tool list for LLM output.

        Args:
            tools: List of tool classes to summarize.

        Returns:
            Formatted string with tool names and descriptions.
        """
        lines = []
        for i, tool in enumerate(tools, start=1):
            name = tool.tool_name or tool.__name__
            desc = tool.description or ""
            lines.append(f"{i}. {name}: {desc}")
        return "\n".join(lines)
