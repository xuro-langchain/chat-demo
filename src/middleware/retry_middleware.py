# Retry middleware for model calls with exponential backoff
import time
import logging
from typing import TYPE_CHECKING, Callable, Awaitable
import asyncio

from langchain.agents.middleware.types import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
    ModelCallResult,
)

if TYPE_CHECKING:
    from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)


class ModelRetryMiddleware(AgentMiddleware):
    def __init__(
        self,
        max_retries: int = 2,
        initial_delay: float = 0.5,
        backoff_factor: float = 2.0,
    ):
        super().__init__()
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.backoff_factor = backoff_factor

    # NOTE: Removed sync wrap_model_call - create_agent is async-only
    # Using time.sleep() in async context causes event loop blocking
    # Only awrap_model_call should be used

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelCallResult:
        last_exception: Exception | None = None

        for attempt in range(self.max_retries + 1):  # +1 for initial attempt
            try:
                return await handler(request)
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = self.initial_delay * (self.backoff_factor ** attempt)
                    logger.warning(
                        f"Model call failed (attempt {attempt + 1}/{self.max_retries + 1}): {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Model call failed after {self.max_retries + 1} attempts: {e}"
                    )

        # Re-raise the last exception to allow fallback middleware to handle it
        raise last_exception  # type: ignore[misc]


__all__ = ["ModelRetryMiddleware"]
