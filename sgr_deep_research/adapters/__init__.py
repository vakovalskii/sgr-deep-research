"""Open-WebUI adapter for SGR Agent Core.

This module provides seamless integration between SGR Agent Core and Open-WebUI frontend.

Key components:
- OpenWebUIToolCallingAgent: Main adapter class
- OpenWebUIStreamingGenerator: HTML details tag streaming
- extract_conversation_history: Clean history extraction
- ReasoningToolOWUI: Reasoning tool with clean fields
- FinalAnswerToolOWUI: Final answer trigger tool
"""

from sgr_deep_research.adapters.conversation_history import extract_conversation_history
from sgr_deep_research.adapters.openwebui_agent import OpenWebUIToolCallingAgent
from sgr_deep_research.adapters.streaming import OpenWebUIStreamingGenerator
from sgr_deep_research.adapters.tools import FinalAnswerToolOWUI, ReasoningToolOWUI

__all__ = [
    "OpenWebUIToolCallingAgent",
    "OpenWebUIStreamingGenerator",
    "extract_conversation_history",
    "ReasoningToolOWUI",
    "FinalAnswerToolOWUI",
]
