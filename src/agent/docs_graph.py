# Deep Docs Agent - Demo of deep agent pattern with KB retrieval
import logging
from deepagents import create_deep_agent

# Import subagent from centralized subagents module
from src.agent.subagents import kb_specialist_subagent

# Import KB retrieval tools
from src.tools.kb_retrieval_tools import search_kb_tool, get_topic_details, list_topics

# Import prompts
from src.prompts.deep_agent_prompt import research_instructions
from src.agent.config import configurable_model

# Set up logging for this module
logger = logging.getLogger(__name__)
logger.info("Deep docs agent module loaded")

# Deep agent with subagent orchestration
# This is a demo showing how to build a deep agent that orchestrates a specialist subagent
# The KB specialist searches a unified knowledge base (ground truth + synthetic data)
docs_agent = create_deep_agent(
    tools=[
        search_kb_tool,  # Main KB search tool
        get_topic_details,  # Detailed topic retrieval
        list_topics,  # Topic discovery
    ],
    system_prompt=research_instructions,
    subagents=[
        kb_specialist_subagent,  # KB specialist for retrieval
    ],
    model=configurable_model,
)

logger.info("Deep docs agent created with KB retrieval")
