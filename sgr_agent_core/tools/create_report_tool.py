from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING, Literal

from pydantic import Field

from sgr_agent_core.base_tool import SystemBaseTool

if TYPE_CHECKING:
    from sgr_agent_core.agent_definition import AgentConfig
    from sgr_agent_core.models import AgentContext

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class CreateReportTool(SystemBaseTool):
    """Create a comprehensive detailed report with citations as a final step of
    research.

    CRITICAL: Every factual claim in content MUST have inline citations [1], [2], [3].
    Citations must be integrated directly into sentences, not just listed at the end.
    """

    reasoning: str = Field(description="Why ready to create report now")
    title: str = Field(description="Report title")
    user_request_language_reference: str = Field(
        description="Copy of original user request to ensure language consistency"
    )
    content: str = Field(
        description="Write comprehensive research report following the REPORT CREATION GUIDELINES from system prompt. "
        "Use the SAME LANGUAGE as user_request_language_reference. "
        "MANDATORY: Include inline citations [1], [2], [3] after EVERY factual claim. "
        "Example: 'The system uses Vue.js [1] and Python [2].' NOT: 'The system uses Vue.js and Python.'"
    )
    confidence: Literal["high", "medium", "low"] = Field(description="Confidence in findings")

    async def __call__(self, context: AgentContext, config: AgentConfig, **_) -> str:
        # Save report
        reports_dir = config.execution.reports_dir
        os.makedirs(reports_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(c for c in self.title if c.isalnum() or c in (" ", "-", "_"))[:50]
        filename = f"{timestamp}_{safe_title}.md"
        filepath = os.path.join(reports_dir, filename)

        # Format a full report with sources
        full_content = f"# {self.title}\n\n"
        full_content += f"*Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
        full_content += self.content + "\n\n"

        # Add a sources reference section
        if context.sources:
            full_content += "---\n\n"
            full_content += "## Sources\n\n"
            full_content += "\n".join([str(source) for source in context.sources.values()])

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(full_content)

        report = {
            "title": self.title,
            "content": self.content,
            "confidence": self.confidence,
            "sources_count": len(context.sources),
            "word_count": len(self.content.split()),
            "filepath": filepath,
            "timestamp": datetime.now().isoformat(),
        }
        logger.info(
            "📝 CREATE REPORT FULL DEBUG:\n"
            f"   🌍 Language Reference: '{self.user_request_language_reference}'\n"
            f"   📊 Title: '{self.title}'\n"
            f"   🔍 Reasoning: '{self.reasoning[:150]}...'\n"
            f"   📈 Confidence: {self.confidence}\n"
            f"   📄 Content Preview: '{self.content[:200]}...'\n"
            f"   📊 Words: {report['word_count']}, Sources: {report['sources_count']}\n"
            f"   💾 Saved: {filepath}\n"
        )
        return json.dumps(report, indent=2, ensure_ascii=False)
