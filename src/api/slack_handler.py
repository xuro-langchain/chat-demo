# Slack webhook handler for Jewels AI agent
import os
import logging
import hmac
import hashlib
import time
import uuid
import asyncio
import base64
from typing import Optional, List, Dict
import httpx
from fastapi import Request, HTTPException, status
from pydantic import BaseModel
from langgraph_sdk import get_client

from src.utils.trace_metadata import build_trace_metadata, extract_org_from_email

logger = logging.getLogger(__name__)

# Namespace UUID for generating deterministic thread IDs
# This is a fixed UUID that we use as the namespace for UUID v5 generation
SLACK_NAMESPACE_UUID = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')


class SlackEvent(BaseModel):
    """Slack event model."""
    type: str
    event: Optional[dict] = None
    challenge: Optional[str] = None


class SlackHandler:
    """Handles Slack webhook events."""

    def __init__(self):
        """Initialize the Slack handler."""
        self.bot_token = os.getenv("SLACK_BOT_TOKEN")
        self.signing_secret = os.getenv("SLACK_SIGNING_SECRET")

        if not self.bot_token or not self.signing_secret:
            logger.warning("SLACK_BOT_TOKEN or SLACK_SIGNING_SECRET not set")

        # Initialize LangGraph SDK client with service account auth
        graph_url = os.getenv("LANGGRAPH_DEPLOYMENT_URL") or os.getenv("LANGGRAPH_API_URL", "http://localhost:8123")

        # Use service account identity for Slack bot
        # This allows all Slack conversations to be owned by the service account
        slack_service_id = os.getenv("SLACK_SERVICE_USER_ID", "service_slack_bot")

        self.graph_client = get_client(
            url=graph_url,
            api_key=os.getenv("LANGSMITH_API_KEY"),
            headers={"Authorization": f"Bearer {slack_service_id}"}  # ← ADD THIS
        )
        logger.info(f"LangGraph client initialized with URL: {graph_url} and service account: {slack_service_id}")
        
        # Cache for user profiles to avoid repeated API calls
        self._user_profile_cache = {}

    async def _verify_slack_signature(self, request: Request, body: bytes) -> bool:
        """Verify Slack request signature using HMAC.

        Args:
            request: The incoming FastAPI request
            body: The raw request body bytes

        Returns:
            True if signature is valid, False otherwise
        """
        if not self.signing_secret:
            logger.warning("SLACK_SIGNING_SECRET not set, skipping signature verification")
            return True  # Allow for development/testing

        # Get signature and timestamp from headers
        slack_signature = request.headers.get("X-Slack-Signature")
        slack_timestamp = request.headers.get("X-Slack-Request-Timestamp")

        if not slack_signature or not slack_timestamp:
            logger.error("Missing Slack signature headers")
            return False

        # Verify timestamp to prevent replay attacks (must be within 5 minutes)
        try:
            timestamp = int(slack_timestamp)
            if abs(time.time() - timestamp) > 60 * 5:
                logger.error("Slack request timestamp too old")
                return False
        except ValueError:
            logger.error("Invalid timestamp format")
            return False

        # Compute expected signature
        sig_basestring = f"v0:{slack_timestamp}:{body.decode('utf-8')}"
        expected_signature = "v0=" + hmac.new(
            self.signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()

        # Compare signatures using constant-time comparison
        is_valid = hmac.compare_digest(expected_signature, slack_signature)

        if not is_valid:
            logger.error("Invalid Slack signature")

        return is_valid

    async def handle_event(self, request: Request, event_data: SlackEvent, body: bytes):
        """Handle Slack events.

        Args:
            request: The incoming FastAPI request
            event_data: The parsed Slack event data
            body: The raw request body for signature verification

        Returns:
            Response dictionary
        """
        try:
            # Handle URL verification challenge FIRST (before signature verification)
            # Slack's challenge doesn't include proper signatures during initial setup
            if event_data.challenge:
                logger.info("Responding to Slack URL verification challenge")
                return {"challenge": event_data.challenge}

            # Verify signature for all other events
            if not await self._verify_slack_signature(request, body):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid signature"
                )

            # Handle events
            if event_data.type == "event_callback":
                event = event_data.event
                event_type = event.get("type")

                logger.info(f"Received Slack event: {event_type}")

                # Handle app mentions and DMs
                if event_type in ["app_mention", "message"]:
                    # Ignore bot messages (check bot_id, subtype, and our own user_id)
                    if event.get("bot_id"):
                        logger.info("Ignoring message from another bot (bot_id present)")
                        return {"ok": True}

                    # Ignore bot_message subtype
                    if event.get("subtype") == "bot_message":
                        logger.info("Ignoring bot_message subtype")
                        return {"ok": True}

                    # Get user before checking
                    user = event.get("user")
                    bot_user_id = self._get_bot_user_id()

                    # Ignore our own messages to prevent infinite loops
                    if user and bot_user_id and user == bot_user_id:
                        logger.info(f"Ignoring message from self (bot user {bot_user_id})")
                        return {"ok": True}

                    # Get message text
                    text = event.get("text", "")
                    channel = event.get("channel")
                    thread_ts = event.get("thread_ts") or event.get("ts")

                    # Validate required fields
                    if not channel:
                        logger.error("Missing channel in event")
                        return {"ok": True}

                    if not thread_ts:
                        logger.error("Missing thread_ts and ts in event")
                        return {"ok": True}

                    # Remove bot mention from text
                    text = text.replace(f"<@{self._get_bot_user_id()}>", "").strip()

                    # Check if message is empty after removing mention
                    if not text:
                        logger.info("Ignoring empty message after removing bot mention")
                        return {"ok": True}

                    logger.info(f"Processing message: {text[:100]}...")

                    # Extract files from the event
                    files = await self._extract_files_from_event(event)
                    if files:
                        logger.info(f"Found {len(files)} file(s) in message")

                    # Generate deterministic UUID for this Slack thread
                    # Same channel + thread_ts = same UUID every time
                    thread_id = self._generate_thread_id(channel, thread_ts)
                    logger.info(f"Thread ID: {thread_id} (from {channel}/{thread_ts})")

                    # Process in background and return 200 immediately to avoid Slack retries
                    # Slack expects response within 3 seconds, but agent takes longer
                    asyncio.create_task(
                        self._process_message_async(
                            question=text,
                            thread_id=thread_id,
                            user_id=user,
                            channel=channel,
                            thread_ts=thread_ts,
                            files=files
                        )
                    )

                    # Return 200 immediately to prevent Slack from retrying
                    return {"ok": True}

            return {"ok": True}

        except Exception as e:
            logger.error(f"Error handling Slack event: {e}", exc_info=True)
            return {"error": str(e)}

    def _get_bot_user_id(self) -> str:
        """Get bot user ID from token."""
        # Extract from SLACK_BOT_TOKEN or use env var
        return os.getenv("SLACK_BOT_USER_ID", "")

    async def _get_user_profile(self, user_id: str) -> dict:
        """Get Slack user profile with caching.
        
        Args:
            user_id: Slack user ID
            
        Returns:
            User profile dict with real_name and email
        """
        # Check cache first
        if user_id in self._user_profile_cache:
            return self._user_profile_cache[user_id]
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://slack.com/api/users.info",
                    headers={"Authorization": f"Bearer {self.bot_token}"},
                    params={"user": user_id}
                )
                data = response.json()
                
                if data.get("ok"):
                    profile = {
                        "real_name": data.get("user", {}).get("real_name", "Unknown"),
                        "email": data.get("user", {}).get("profile", {}).get("email", f"slack_{user_id}")
                    }
                    # Cache for future use
                    self._user_profile_cache[user_id] = profile
                    logger.debug(f"Cached user profile for {user_id}: {profile.get('real_name')}")
                    return profile
                else:
                    logger.warning(f"Slack API error fetching user profile for {user_id}: {data.get('error')} - using fallback")
                    return {"real_name": "Unknown", "email": f"slack_{user_id}"}
        except Exception as e:
            logger.error(f"Exception fetching user profile for {user_id}: {e} - using fallback metadata")
            return {"real_name": "Unknown", "email": f"slack_{user_id}"}

    async def _process_message_async(
        self,
        question: str,
        thread_id: str,
        user_id: str,
        channel: str,
        thread_ts: str,
        files: List[Dict[str, str]] = None
    ) -> None:
        """Process message asynchronously in background.

        This allows the webhook to return 200 immediately to Slack,
        preventing retry/duplicate messages.

        Args:
            question: User's question
            thread_id: LangGraph thread UUID
            user_id: Slack user ID
            channel: Slack channel ID
            thread_ts: Slack thread timestamp
            files: Optional list of file attachments (images, code files, etc.)
        """
        try:
            logger.info(f"[Background] Processing message in thread {thread_id}")

            # Call agent with event data for metadata
            response = await self._call_agent(
                question=question,
                thread_id=thread_id,
                user_id=user_id,
                event_data={"channel": channel, "thread_ts": thread_ts},
                files=files
            )

            # Post response to Slack
            await self._post_message(
                channel=channel,
                text=response,
                thread_ts=thread_ts
            )

            logger.info(f"[Background] Successfully processed message in thread {thread_id}")

        except Exception as e:
            logger.error(f"[Background] Error processing message: {e}", exc_info=True)
            # Try to send error message to user
            try:
                await self._post_message(
                    channel=channel,
                    text="Sorry, I encountered an error processing your message. Please try again.",
                    thread_ts=thread_ts
                )
            except Exception as post_error:
                logger.error(f"[Background] Failed to post error message: {post_error}")

    def _generate_thread_id(self, channel: str, thread_ts: str) -> str:
        """Generate a deterministic UUID for a Slack thread.

        Uses UUID v5 (name-based, SHA-1) to create a consistent UUID from
        the Slack channel and thread timestamp. Same inputs = same UUID.

        Args:
            channel: Slack channel ID (e.g., "D09N4UCN7UK")
            thread_ts: Slack thread timestamp (e.g., "1761265021.661769")

        Returns:
            UUID string compatible with LangGraph Cloud
        """
        # Create a unique identifier from channel and thread
        # Format: "slack:{channel}:{thread_ts}"
        slack_identifier = f"slack:{channel}:{thread_ts}"

        # Generate deterministic UUID v5 from the identifier
        thread_uuid = uuid.uuid5(SLACK_NAMESPACE_UUID, slack_identifier)

        logger.debug(f"Generated UUID {thread_uuid} from {slack_identifier}")
        return str(thread_uuid)

    def _validate_thread_id(self, thread_id: str) -> bool:
        """Validate that thread ID is a valid UUID format.

        Args:
            thread_id: Thread ID to validate

        Returns:
            True if valid UUID, False otherwise
        """
        if not thread_id or not isinstance(thread_id, str):
            return False

        try:
            # Try to parse as UUID to validate format
            uuid.UUID(thread_id)
            return True
        except (ValueError, AttributeError):
            logger.error(f"Invalid UUID format for thread_id: {thread_id}")
            return False

    async def _call_agent(self, question: str, thread_id: str, user_id: str, event_data: dict, files: List[Dict[str, str]] = None) -> str:
        """Call the LangGraph docs agent.

        Args:
            question: User's question
            thread_id: Slack thread identifier
            user_id: Slack user ID
            event_data: Slack event data (for metadata)
            files: Optional list of file attachments (images, code files, etc.)

        Returns:
            Agent's response text
        """
        try:
            # Validate thread ID format
            if not self._validate_thread_id(thread_id):
                logger.error(f"Invalid thread_id: {thread_id}")
                return "Sorry, there was an issue processing your request. Please try again."
            # Get assistant ID from env var or use default graph ID
            # The graph_id is used instead of searching (which requires auth permissions)
            assistant_graph_id = os.getenv("SLACK_DOCS_AGENT_ID", "slack_docs_agent")

            # For LangGraph Cloud deployments, we use the graph_id directly as assistant_id
            # No need to search - just use the deployed graph name
            assistant_id = assistant_graph_id
            logger.info(f"Using assistant: {assistant_id}")

            # Create or get thread with retry logic for race conditions
            thread_exists = False
            max_retries = 3

            for attempt in range(max_retries):
                try:
                    await self.graph_client.threads.get(thread_id)
                    thread_exists = True
                    logger.info(f"Using existing thread {thread_id}")
                    break
                except Exception as get_error:
                    # Thread doesn't exist, try to create it
                    logger.debug(f"Thread not found (attempt {attempt + 1}): {get_error}")

                    try:
                        await self.graph_client.threads.create(thread_id=thread_id)
                        thread_exists = True
                        logger.info(f"Created new thread {thread_id}")
                        break
                    except Exception as create_error:
                        # Handle race condition: thread was created between get and create
                        if "already exists" in str(create_error).lower():
                            logger.info(f"Thread created by another request, retrying get")
                            continue

                        # If this is the last attempt, raise the error
                        if attempt == max_retries - 1:
                            logger.error(f"Failed to create/get thread after {max_retries} attempts: {create_error}")
                            raise

                        # Otherwise, retry
                        logger.warning(f"Thread creation failed (attempt {attempt + 1}), retrying: {create_error}")

            if not thread_exists:
                raise Exception(f"Failed to create or get thread {thread_id}")

            # Format message content - use multimodal format if files are present
            if files and len(files) > 0:
                message_content = [
                    {"type": "text", "text": question}
                ] + files
            else:
                message_content = question

            # Get user profile for metadata
            user_profile = await self._get_user_profile(user_id)
            user_name = user_profile.get("real_name", "Unknown") if user_profile else "Unknown"
            user_email = user_profile.get("email", f"slack_{user_id}") if user_profile else f"slack_{user_id}"
            
            # Log if we're using fallback values
            if user_name == "Unknown" or user_email.startswith("slack_"):
                logger.warning(f"Using fallback metadata for user {user_id}: name={user_name}, email={user_email}")
            else:
                logger.info(f"Extracted user metadata: {user_name} ({user_email})")
            
            # Create run with standardized metadata for LangSmith tracing
            run = await self.graph_client.runs.create(
                thread_id=thread_id,
                assistant_id=assistant_id,
                input={"messages": [{"role": "user", "content": message_content}]},
                metadata=build_trace_metadata(
                    # User context
                    user_id=user_id,
                    user_email=user_email,
                    user_name=user_name,
                    user_org=extract_org_from_email(user_email) if user_email else None,
                    # Source context
                    source_type="Slack",
                    channel_id=event_data.get("channel"),
                    # Additional Slack-specific context
                    thread_ts=event_data.get("thread_ts") or event_data.get("ts"),
                ),
            )

            logger.info(f"Created run {run['run_id']}")

            # Wait for completion
            await self.graph_client.runs.join(thread_id, run["run_id"])

            # Get response
            state = await self.graph_client.threads.get_state(thread_id)
            messages = state["values"].get("messages", [])

            # Extract AI response
            for msg in reversed(messages):
                if hasattr(msg, "content"):
                    return msg.content
                elif isinstance(msg, dict):
                    if msg.get("type") == "ai" or msg.get("role") == "assistant":
                        return msg.get("content", "")

            return "Sorry, I couldn't generate a response. Please try again."

        except Exception as e:
            logger.error(f"Error calling agent: {e}", exc_info=True)
            return "Sorry, I encountered an error processing your request. Please try again."

    async def _post_message(self, channel: str, text: str, thread_ts: str = None):
        """Post message to Slack.

        Args:
            channel: Slack channel ID
            text: Message text
            thread_ts: Thread timestamp for threading
        """
        try:
            url = "https://slack.com/api/chat.postMessage"
            headers = {
                "Authorization": f"Bearer {self.bot_token}",
                "Content-Type": "application/json"
            }
            payload = {
                "channel": channel,
                "text": text,
                "unfurl_links": False,  # Disable link previews
                "unfurl_media": False,  # Disable media previews
            }
            if thread_ts:
                payload["thread_ts"] = thread_ts

            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload)
                result = response.json()

                if not result.get("ok"):
                    logger.error(f"Failed to post to Slack: {result}")
                else:
                    logger.info(f"Posted message to Slack channel {channel}")

        except Exception as e:
            logger.error(f"Error posting to Slack: {e}", exc_info=True)

    async def _extract_files_from_event(self, event: dict) -> List[Dict[str, str]]:
        """Extract and download files from Slack event.

        Supports images, text files, code files, PDFs, and other common file types.

        Args:
            event: Slack event dictionary

        Returns:
            List of content dictionaries in multimodal format
        """
        content_blocks = []

        # Check for files in the event
        files = event.get("files", [])

        # Text-based mimetypes we can process as text
        TEXT_MIMETYPES = {
            'text/plain', 'text/markdown', 'text/x-python', 'text/x-java',
            'text/x-c', 'text/x-c++', 'text/javascript', 'text/typescript',
            'text/html', 'text/css', 'text/xml', 'application/json',
            'application/javascript', 'application/typescript',
            'application/x-python', 'application/x-python-code',
            'application/x-sh', 'text/x-sh'
        }

        for file in files:
            mimetype = file.get("mimetype", "")
            filename = file.get("name", "unnamed")

            # Get download URL (use url_private_download for better quality)
            url = file.get("url_private_download") or file.get("url_private")
            if not url:
                logger.warning(f"File missing URL: {file}")
                continue

            # Check file size (limit to 10MB to prevent huge files)
            file_size = file.get("size", 0)
            if file_size > 10 * 1024 * 1024:  # 10MB
                logger.warning(f"Skipping large file: {filename} ({file_size} bytes)")
                content_blocks.append({
                    "type": "text",
                    "text": f"[File '{filename}' is too large to process (max 10MB)]"
                })
                continue

            try:
                # Download the file using bot token for auth
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        url,
                        headers={"Authorization": f"Bearer {self.bot_token}"},
                        timeout=30.0
                    )
                    response.raise_for_status()

                    file_content = response.content

                    # Process based on mimetype
                    if mimetype.startswith("image/"):
                        # Handle images (base64 encode)
                        base64_data = base64.b64encode(file_content).decode('utf-8')
                        content_blocks.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mimetype};base64,{base64_data}"
                            }
                        })
                        logger.info(f"Downloaded image: {filename} ({mimetype})")

                    elif mimetype in TEXT_MIMETYPES or filename.endswith(('.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.cpp', '.c', '.h', '.cs', '.go', '.rs', '.rb', '.php', '.sh', '.bash', '.yaml', '.yml', '.json', '.xml', '.html', '.css', '.md', '.txt', '.log', '.sql', '.r', '.swift', '.kt', '.scala', '.graphql', '.har')):
                        # Handle text/code files (decode as text)
                        try:
                            text_content = file_content.decode('utf-8')
                            content_blocks.append({
                                "type": "text",
                                "text": f"**File: {filename}**\n```\n{text_content}\n```"
                            })
                            logger.info(f"Downloaded text file: {filename} ({mimetype})")
                        except UnicodeDecodeError:
                            logger.warning(f"Could not decode text file: {filename}")
                            content_blocks.append({
                                "type": "text",
                                "text": f"[File '{filename}' could not be decoded as text]"
                            })

                    elif mimetype == "application/pdf":
                        # For PDFs, note that we received it but can't process directly
                        # The agent would need PDF parsing capabilities
                        content_blocks.append({
                            "type": "text",
                            "text": f"[PDF file '{filename}' received but PDF parsing not yet implemented]"
                        })
                        logger.info(f"Received PDF file: {filename}")

                    else:
                        # Unknown file type
                        logger.warning(f"Unsupported file type: {filename} ({mimetype})")
                        content_blocks.append({
                            "type": "text",
                            "text": f"[File '{filename}' has unsupported type: {mimetype}]"
                        })

            except Exception as e:
                logger.error(f"Failed to download file from {url}: {e}")
                content_blocks.append({
                    "type": "text",
                    "text": f"[Failed to download file '{filename}']"
                })
                continue

        return content_blocks
