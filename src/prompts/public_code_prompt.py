# Prompt variant for PUBLIC CODE agent (OSS repos only)
from .deep_agent_prompt import (
    mission_section,
    docs_specialist_section,
    kb_specialist_section,
    public_code_specialist_section,
    workflow_section,
    public_code_workflow,
    synthesis_section,
    final_response_format,
    research_instructions  # Keep for backward compatibility
)

# Compose the public code agent prompt using sections
public_code_instructions = (
    "You are an expert LangChain customer service agent with deep research capabilities.\n\n"
    + mission_section
    + docs_specialist_section
    + kb_specialist_section
    + public_code_specialist_section
    + workflow_section
    + public_code_workflow
    + synthesis_section
    + final_response_format
)
