# FastAPI server for Jewels Pylon and Slack integration
import asyncio
import json
import logging
import os
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError

from src.api.pylon_handler import PylonHandler, PylonRequest
from src.api.slack_handler import SlackHandler, SlackEvent
from src.api.title_generator import generate_title
from src.api.langsmith_routes import router as langsmith_router
from src.tools.docs_tools import get_cache_stats, clear_cache

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# CORS Configuration
# =============================================================================

# Default allowed origins (development + production)
DEFAULT_CORS_ORIGINS: List[str] = [
    # Local development
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    # LangSmith Studio
    "https://smith.langchain.com",
    # Production frontends
    "https://chat.langchain.com",
    "https://support.langchain.com",
    "https://jewel-frontend.vercel.app",
    "https://chat-lang-chain-v2.vercel.app",
    "https://chat-langchain-internal.vercel.app",
]


def _get_cors_origins() -> List[str]:
    """Get CORS allowed origins from defaults + environment."""
    origins = DEFAULT_CORS_ORIGINS.copy()
    additional = os.getenv("ALLOWED_ORIGINS", "")
    if additional:
        origins.extend([o.strip() for o in additional.split(",") if o.strip()])
    return origins


# =============================================================================
# FastAPI App
# =============================================================================

app = FastAPI(
    title="Deep Agent Demo API",
    description="Demo API showcasing deep agent pattern with subagent orchestration. Includes webhook endpoints for Pylon and Slack integrations."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include LangSmith routes
app.include_router(langsmith_router)

# Lazy initialization - handlers created on first request
_pylon_handler = None
_slack_handler = None


class TitleGenerationRequest(BaseModel):
    """Request model for title generation."""
    userMessage: str
    assistantResponse: Optional[str] = None
    maxLength: Optional[int] = 60


class TitleGenerationResponse(BaseModel):
    """Response model for title generation."""
    title: str


def get_pylon_handler() -> PylonHandler:
    """Get or create PylonHandler instance (lazy initialization)."""
    global _pylon_handler
    if _pylon_handler is None:
        _pylon_handler = PylonHandler()
    return _pylon_handler


def get_slack_handler() -> SlackHandler:
    """Get or create SlackHandler instance (lazy initialization)."""
    global _slack_handler
    if _slack_handler is None:
        _slack_handler = SlackHandler()
    return _slack_handler


@app.post("/pylon/jewels")
async def handle_jewels_webhook(request: Request, pylon_request: PylonRequest):
    """Handle Jewels AI webhook from Pylon.

    Receives customer questions, calls LangGraph agent, and posts replies back to Pylon.
    """
    logger.info("=" * 60)
    logger.info("[WEBHOOK] HIT: /pylon/jewels endpoint called")
    logger.info(f"Request headers: {dict(request.headers)}")
    logger.info(f"Request body: {pylon_request.dict()}")
    logger.info("=" * 60)

    handler = get_pylon_handler()
    return await handler.handle_jewels_request(request, pylon_request)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "jewels",
    }


@app.post("/generate-title", response_model=TitleGenerationResponse)
async def generate_conversation_title(request: TitleGenerationRequest):
    """Generate a smart title for a conversation thread.

    Uses OpenAI GPT-4o-mini to create concise, descriptive titles.
    Falls back to truncated user message if API is unavailable.

    Args:
        request: Title generation request containing user message and optional assistant response

    Returns:
        Generated title for the conversation
    """
    logger.info(f"Generating title for message: {request.userMessage[:50]}...")

    from src.api.title_generator import truncate_title

    try:
        title = await generate_title(
            user_message=request.userMessage,
            assistant_response=request.assistantResponse,
            max_length=request.maxLength or 60
        )
        logger.info(f"Generated title: {title}")
        return TitleGenerationResponse(title=title)

    except (TimeoutError, asyncio.TimeoutError) as e:
        logger.warning(f"Title generation timed out: {e}")
        fallback = truncate_title(request.userMessage, request.maxLength or 60)
        return TitleGenerationResponse(title=fallback)
    except ValueError as e:
        logger.error(f"Invalid input for title generation: {e}")
        fallback = truncate_title(request.userMessage, request.maxLength or 60)
        return TitleGenerationResponse(title=fallback)


# =============================================================================
# K8s Triage Endpoints (Removed for Simplified Demo)
# =============================================================================
# The following K8s-specific endpoints were removed as part of simplification:
# - POST /k8s/upload
# - GET /k8s/sandbox/{sandbox_id}/file
# - GET /k8s/sandbox/{sandbox_id}/files
# - POST /k8s/sandbox/{sandbox_id}/upload
# - DELETE /k8s/sandbox/{sandbox_id}
# =============================================================================


@app.post("/slack/events")
async def handle_slack_events(request: Request):
    """Handle Slack events webhook.

    Receives Slack events (app mentions, DMs), calls LangGraph agent,
    and posts replies back to Slack.
    """
    body = await request.body()

    try:
        event_data = json.loads(body)
        event = SlackEvent(**event_data)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in Slack event: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    except ValidationError as e:
        logger.error(f"Slack event validation failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid Slack event structure")

    logger.info("=" * 60)
    logger.info("[WEBHOOK] HIT: /slack/events endpoint called")
    logger.info(f"Event type: {event.type}")
    logger.info("=" * 60)

    handler = get_slack_handler()
    return await handler.handle_event(request, event, body)


@app.get("/metrics/cache")
async def get_cache_metrics():
    """Get Mintlify API cache statistics.

    Returns real-time metrics about the documentation search cache:
    - Total cache entries
    - Hit/miss counts
    - Cache hit rate percentage
    - Configuration (TTL, fuzzy threshold)

    Use this to monitor cache performance and API cost savings.
    """
    stats = get_cache_stats()

    # Calculate API cost savings (assuming cache saves API calls)
    total_hits = stats['hits_exact'] + stats['hits_fuzzy']
    total_requests = stats['total_requests']

    # Add derived metrics
    stats['api_calls_saved'] = total_hits
    stats['api_calls_made'] = stats['misses']  # Cache misses (may include retries)
    # api_requests_total is already in stats (includes all retries)

    if total_requests > 0:
        stats['cost_reduction_percent'] = round((total_hits / total_requests) * 100, 1)
    else:
        stats['cost_reduction_percent'] = 0.0

    logger.info(f"Cache metrics requested: {stats['hit_rate_percent']}% hit rate")

    return {
        "status": "success",
        "cache_metrics": stats,
        "description": "Mintlify API documentation search cache statistics"
    }


@app.post("/metrics/cache/clear")
async def clear_cache_endpoint():
    """Clear the Mintlify API cache and reset metrics.

    Use this endpoint to:
    - Force refresh of cached documentation
    - Reset cache statistics
    - Clear memory after documentation updates

    Warning: This will cause the next searches to hit the API directly.
    """
    # Get stats before clearing to capture entry count
    stats_before = get_cache_stats()
    old_entries = stats_before.get('total_entries', 0)
    
    clear_cache()

    logger.warning(f"Cache manually cleared via API: {old_entries} entries removed")

    return {
        "status": "success",
        "message": f"Cache cleared successfully",
        "entries_removed": old_entries,
        "cache_stats": get_cache_stats()
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Jewels API Server",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "generate_title": "/generate-title",
            "pylon_jewels": "/pylon/jewels",
            "slack_events": "/slack/events",
            "cache_metrics": "/metrics/cache",
            "cache_clear": "/metrics/cache/clear (POST)"
        }
    }
