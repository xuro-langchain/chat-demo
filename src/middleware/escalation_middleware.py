# Escalation detection middleware for handling human escalation requests
import logging
from typing import Any
from typing_extensions import NotRequired
from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)


class EscalationState(AgentState):
    """Extended state schema with escalation flag."""
    escalation_requested: NotRequired[bool]


_ESCALATION_SYSTEM_PROMPT = """
You are an escalation detector for a customer service system.

Your goal is to decide whether a customer message indicates that they want to speak with a human agent or escalate the issue beyond automated support.

Respond with ONLY:
- "YES" if the customer explicitly asks to talk to a human, real person, or team, or directly requests escalation.
- "NO" for all other cases — including polite or urgent requests for help, clarification, or technical support.

### Guidelines
- Escalation means the customer wants or expects a *human* to take over.
- Do NOT treat urgency ("please respond soon") or politeness ("thank you!") as escalation.
- Do NOT flag normal help or support requests.
- Do flag messages with clear and explicit intent to contact a human, escalate, or reach the support team directly.

### Examples

**YES (escalation):**
- "I need to talk to a human."
- "Please escalate this to your team."
- "Can I speak with a real person?"
- "Connect me to support."
- "Get me a live agent."

**NO (not escalation):**
- "I need help changing my account settings."
- "Can you explain how this works?"
- "This is confusing, can someone help?"
- "Please reply soon."
- "I’d like to reach out for help understanding something."
- "I was wondering if I could get some help with this setup."
- "Could you clarify how to move my deployment to a different repo?"

Output must be exactly one word: **YES** or **NO**
"""


class EscalationMiddleware(AgentMiddleware[EscalationState]):
    state_schema = EscalationState

    def __init__(self, model: str = "gpt-5-nano"):
        super().__init__()
        self.llm = ChatOpenAI(model=model, temperature=0)

    def _get_last_message_content(self, state: EscalationState) -> str | None:
        """Extract content from the most recent user message."""
        messages = state.get("messages", [])
        if not messages:
            return None

        last_message = messages[-1]
        if not hasattr(last_message, "content"):
            return None

        return last_message.content

    @hook_config(can_jump_to=["end"])
    async def abefore_agent(self, state: EscalationState, runtime: Runtime) -> dict[str, Any] | None:
        """Check if customer wants to escalate before agent processing."""
        content = self._get_last_message_content(state)
        if not content:
            return None

        prompt = [
            SystemMessage(content=_ESCALATION_SYSTEM_PROMPT),
            HumanMessage(content=f"Customer message: {content}")
        ]

        try:
            response = await self.llm.ainvoke(prompt)
            wants_escalation = "YES" in response.content.upper()

            if wants_escalation:
                logger.info(f"Escalation detected: {content[:100]}...")
                return {
                    "escalation_requested": True,
                    "jump_to": "end",
                }
        except Exception as e:
            logger.error(f"Error detecting escalation: {e}")

        return None


__all__ = ["EscalationMiddleware"]
