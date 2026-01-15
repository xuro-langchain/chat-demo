# Prompt variant for FULL ACCESS agent (OSS + private repos)
from .deep_agent_prompt import (
    mission_section,
    docs_specialist_section,
    kb_specialist_section,
    full_code_specialist_section,
    workflow_section,
    full_code_workflow,
    synthesis_section,
    final_response_format,
)

# Compose the full access agent prompt using sections
full_code_instructions = (
    "You are an expert LangChain customer service agent with deep research capabilities.\n\n"
    + mission_section
    + docs_specialist_section
    + kb_specialist_section
    + full_code_specialist_section
    + workflow_section
    + full_code_workflow
    + synthesis_section
    + final_response_format
)
