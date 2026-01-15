# Simplified subagent for KB retrieval demo
import logging
from langchain.agents import create_agent

from src.tools.kb_retrieval_tools import search_kb_tool, get_topic_details, list_topics
from src.prompts.subagents.kb_specialist_prompt import kb_specialist_prompt
from src.agent.config import (
    configurable_model as configurable_subagent_model,
    model_retry_middleware,
    model_fallback_middleware,
)

# Set up logging for this module
logger = logging.getLogger(__name__)
logger.info("Subagents module loaded")

# KB Specialist Subagent Definition
kb_specialist_subagent = {
    "name": "kb-specialist",
    "description": "Knowledge base expert. Searches customer support KB covering banking, credit cards, payments, disputes, fraud, rewards, and account management. Use for all customer support questions.",
    "system_prompt": kb_specialist_prompt,
    "tools": [search_kb_tool, get_topic_details, list_topics],
}

# Standalone KB Specialist Agent
kb_specialist_agent = create_agent(
    model=configurable_subagent_model,
    tools=[search_kb_tool, get_topic_details, list_topics],
    system_prompt=kb_specialist_prompt,
    middleware=[
        model_retry_middleware,
        model_fallback_middleware,
    ],
)

logger.info("KB specialist agent created")

# Exports
__all__ = [
    # Subagent definition
    "kb_specialist_subagent",
    # Standalone implementation
    "kb_specialist_agent",
    # Shared config
    "configurable_subagent_model",
]