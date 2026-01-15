# Pylon webhook handler for Jewels AI agent
import os
import logging
from typing import Optional
from fastapi import Request, HTTPException, status
from pydantic import BaseModel
import markdown
from langgraph_sdk import get_client

from src.api.pylon_client import PylonClient
from src.utils.trace_metadata import build_trace_metadata, extract_org_from_email

logger = logging.getLogger(__name__)


class PylonRequest(BaseModel):
    """Pylon webhook request payload."""
    issue_id: str
    issue_body: Optional[str] = ""
    requester_email: Optional[str] = ""


class PylonResponse(BaseModel):
    """Pylon webhook response."""
    status: str  # success, error, skipped
    issue_id: str
    reply_posted: bool
    error: Optional[str] = None


def _sanitize_customer_name(name: str) -> str:
    """Sanitize customer name, handling Pylon's placeholder values.

    Pylon uses "Without Name" as a placeholder when contact has no name set.

    Args:
        name: Raw name from Pylon API

    Returns:
        Sanitized name or empty string (for "Hi," greeting)
    """
    if not name or name == "Without Name":
        return ""
    return name


class PylonHandler:
    """Handles Pylon webhook requests and orchestrates AI responses."""

    def __init__(self):
        """Initialize handler with LangGraph and Pylon clients."""
        # Auth config
        self.require_auth = os.getenv("JEWELS_REQUIRE_AUTH", "false").lower() in {"1", "true", "yes"}
        self.api_key = os.getenv("JEWELS_API_KEY")

        if self.require_auth and not self.api_key:
            logger.warning("JEWELS_API_KEY not set - auth disabled")

        # LangGraph client with service account auth
        graph_url = os.getenv("LANGGRAPH_DEPLOYMENT_URL") or os.getenv("LANGGRAPH_API_URL", "http://localhost:8123")

        # Use service account identity for Pylon bot
        pylon_service_id = os.getenv("PYLON_SERVICE_USER_ID", "service_pylon_bot")

        self.graph_client = get_client(
            url=graph_url,
            api_key=os.getenv("LANGSMITH_API_KEY"),
            headers={"Authorization": f"Bearer {pylon_service_id}"}  # ← ADD THIS
        )
        logger.info(f"LangGraph client: {graph_url} with service account: {pylon_service_id}")

        # Pylon client
        self.pylon_client = PylonClient()

        # Prevent duplicate processing
        self._processing_tickets = set()

    def _validate_api_key(self, request: Request) -> bool:
        """Validate webhook API key from request headers."""
        if not self.require_auth or not self.api_key:
            return True

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.error("Invalid/missing Authorization header")
            return False

        provided_key = auth_header[7:]  # Remove "Bearer " prefix
        return provided_key == self.api_key

    def _find_most_recent_customer_message_id(self, messages: list) -> Optional[str]:
        """Find the most recent customer message ID for threading."""
        for msg in reversed(messages):
            if msg.get("is_private"):
                continue
            is_customer = bool(msg.get("author", {}).get("contact"))
            if is_customer:
                return msg.get("id")
        return None

    def _format_html_response(self, markdown_text: str) -> str:
        """Convert markdown to styled HTML for email clients using inline styles."""
        from html.parser import HTMLParser

        html_content = markdown.markdown(
            markdown_text,
            extensions=['fenced_code', 'tables', 'nl2br']
        )

        # Post-process HTML to add inline styles (email-friendly)
        class InlineStyler(HTMLParser):
            def __init__(self):
                super().__init__()
                self.output = []
                self.in_pre = False

            def handle_starttag(self, tag, attrs):
                style = ""
                if tag == "h1":
                    style = "font-size: 24px; font-weight: 600; margin: 24px 0 12px 0; color: #1a1a1a; border-bottom: 2px solid #e5e7eb; padding-bottom: 8px;"
                elif tag == "h2":
                    style = "font-size: 20px; font-weight: 600; margin: 20px 0 10px 0; color: #1a1a1a;"
                elif tag == "h3":
                    style = "font-size: 18px; font-weight: 600; margin: 16px 0 8px 0; color: #374151;"
                elif tag == "p":
                    style = "margin: 14px 0; color: #374151; line-height: 1.6;"
                elif tag == "pre":
                    style = "background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 16px; margin: 16px 0; font-family: 'Courier New', monospace; font-size: 14px; overflow-x: auto; color: #212529;"
                    self.in_pre = True
                elif tag == "code" and not self.in_pre:
                    style = "background: #f8f9fa; padding: 2px 6px; border-radius: 3px; font-family: 'Courier New', monospace; font-size: 14px; color: #dc3545; border: 1px solid #dee2e6;"
                elif tag == "ul":
                    style = "margin: 14px 0; padding-left: 28px; color: #374151;"
                elif tag == "ol":
                    style = "margin: 14px 0; padding-left: 28px; color: #374151;"
                elif tag == "li":
                    style = "margin: 8px 0; color: #374151; line-height: 1.6;"
                elif tag == "table":
                    style = "border-collapse: collapse; width: 100%; margin: 20px 0; border: 1px solid #dee2e6;"
                elif tag == "th":
                    style = "background: #f8f9fa; border: 1px solid #dee2e6; padding: 12px; text-align: left; font-weight: 600; color: #212529;"
                elif tag == "td":
                    style = "border: 1px solid #dee2e6; padding: 12px; color: #374151;"
                elif tag == "a":
                    style = "color: #0d6efd; text-decoration: underline;"
                elif tag == "strong":
                    style = "font-weight: 600; color: #1a1a1a;"
                elif tag == "em":
                    style = "font-style: italic; color: #374151;"
                elif tag == "blockquote":
                    style = "border-left: 4px solid #0d6efd; padding-left: 16px; margin: 16px 0; color: #6c757d; font-style: italic;"

                attrs_str = ""
                for name, value in attrs:
                    if name == "style" and style:
                        # Merge existing style with new style
                        attrs_str += f' style="{value}; {style}"'
                    else:
                        attrs_str += f' {name}="{value if value else ""}"'

                if style and "style=" not in attrs_str:
                    attrs_str += f' style="{style}"'

                self.output.append(f"<{tag}{attrs_str}>")

            def handle_endtag(self, tag):
                if tag == "pre":
                    self.in_pre = False
                self.output.append(f"</{tag}>")

            def handle_data(self, data):
                self.output.append(data)

            def get_output(self):
                return "".join(self.output)

        styler = InlineStyler()
        styler.feed(html_content)
        styled_html = styler.get_output()

        # Wrap in email-safe container with ai-response class for bot detection
        return f"""
        <div class="ai-response" style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #374151; max-width: 700px;">
            {styled_html}
        </div>
        """

    async def handle_jewels_request(self, request: Request, pylon_request: PylonRequest) -> PylonResponse:
        """Handle Pylon webhook request and generate AI response.

        Flow:
        1. Validate API key
        2. Check for duplicate/bot messages
        3. Fetch ticket context and messages
        4. Call LangGraph agent
        5. Post response to Pylon

        Args:
            request: FastAPI request object
            pylon_request: Parsed Pylon webhook data

        Returns:
            PylonResponse with status and result
        """
        try:
            # Validate API key
            if not self._validate_api_key(request):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

            # Prevent duplicate processing
            if pylon_request.issue_id in self._processing_tickets:
                logger.warning(f"Already processing {pylon_request.issue_id}, skipping duplicate")
                return PylonResponse(
                    status="skipped",
                    issue_id=pylon_request.issue_id,
                    reply_posted=False,
                    error="Already processing"
                )

            # Mark as processing
            self._processing_tickets.add(pylon_request.issue_id)

            # Log webhook trigger
            logger.info("=" * 80)
            logger.info("PYLON WEBHOOK TRIGGERED")
            logger.info(f"Issue: {pylon_request.issue_id}")
            logger.info(f"Requester: {pylon_request.requester_email}")
            logger.info(f"Body: {pylon_request.issue_body[:100] if pylon_request.issue_body else '(empty)'}")
            logger.info("=" * 80)

            # Fetch ticket details (metadata)
            ticket_details = await self.pylon_client.get_ticket_details(pylon_request.issue_id)
            custom_fields = ticket_details.get("custom_fields", {})

            # Extract metadata
            def get_field(name, default=""):
                field = custom_fields.get(name)
                return field.get("value", default) if field else default

            title = ticket_details.get("title", "")
            team_id = (ticket_details.get("team") or {}).get("id", "")
            support_tier = get_field("support_tier", "unknown")
            plan_type = get_field("plan_type", "unknown")
            sla_group = get_field("sla_group", "unknown")
            ticket_type = get_field("ticket_type", "unknown")
            org_id = get_field("org_id", "")

            # Fetch messages
            pylon_messages = await self.pylon_client.get_ticket_messages(pylon_request.issue_id)
            logger.info(f"Fetched {len(pylon_messages)} messages")

            # CRITICAL: Only respond to customer messages, never to bot/AI messages
            # This prevents infinite loops where the bot responds to its own messages
            # Skip private messages (internal notes from bots like Blu) when checking
            if pylon_messages:
                # Find the most recent non-private message
                most_recent_public = None
                for msg in reversed(pylon_messages):
                    if not msg.get("is_private"):
                        most_recent_public = msg
                        break

                if not most_recent_public:
                    logger.warning("No public messages found - skipping")
                    return PylonResponse(
                        status="skipped",
                        issue_id=pylon_request.issue_id,
                        reply_posted=False,
                        error="No public messages found"
                    )

                author = most_recent_public.get("author", {})

                # Customer messages have 'contact' field, bot messages have 'user' field
                is_customer = bool(author.get("contact"))
                is_bot = bool(author.get("user"))

                if not is_customer:
                    author_name = author.get("name", "unknown")
                    logger.warning(f"Most recent public message is NOT from a customer (author: {author_name}, is_bot: {is_bot}) - skipping to prevent bot loop")
                    return PylonResponse(
                        status="skipped",
                        issue_id=pylon_request.issue_id,
                        reply_posted=False,
                        error=f"Non-customer message detected (from: {author_name})"
                    )

                logger.info(f"Most recent public message is from customer: {author.get('name', 'unknown')} - proceeding to process")

            # Build ticket context for agent
            context = f"""Ticket Context:
- Title: {title}
- Type: {ticket_type}
- Team: {team_id}
- Tier: {support_tier}
- SLA: {sla_group}
- Plan: {plan_type}
- Org: {org_id}"""

            # Find most recent customer question
            current_question = None
            for msg in reversed(pylon_messages):
                if msg.get("is_private"):
                    continue
                content = msg.get("message_html", "")
                is_customer = bool(msg.get("author", {}).get("contact"))
                if is_customer:
                    current_question = content
                    logger.info(f"Found customer message: {msg.get('id')}")
                    break

            if not current_question:
                current_question = pylon_request.issue_body or title or "Follow-up question"
                logger.info("No customer message, using fallback")

            logger.info(f"Question: {current_question[:100]}...")

            # Extract files from customer messages
            customer_files = await self.pylon_client.extract_files_from_messages(pylon_messages)
            if customer_files:
                logger.info(f"Found {len(customer_files)} file(s) in messages")

            # Extract customer info for metadata
            customer_name = "Unknown"
            customer_email = pylon_request.requester_email or "unknown@pylon.com"
            if pylon_messages:
                first_msg = pylon_messages[0]
                author = first_msg.get("author", {})
                contact = author.get("contact", {})
                if contact:
                    customer_name = _sanitize_customer_name(author.get("name", "")) or "Unknown"
                    customer_email = contact.get("email", customer_email)
                    logger.info(f"Extracted customer metadata: {customer_name} ({customer_email})")
                else:
                    logger.warning(f"No contact info in first message, using fallback: requester_email={pylon_request.requester_email}")
            else:
                logger.warning(f"No messages found, using fallback metadata: {customer_email}")
            
            # Final warning if still using defaults
            if customer_name == "Unknown" or customer_email == "unknown@pylon.com":
                logger.warning(f"Using incomplete customer metadata for ticket {pylon_request.issue_id}: name={customer_name}, email={customer_email}")

            # Detect if this is email or chat widget to select appropriate agent
            first_message = pylon_messages[0] if pylon_messages else {}
            source = first_message.get("source", "")
            is_chat = source == "pylon_chat_widget"
            is_email = not is_chat  # If not chat, assume email

            # Select agent based on ticket source
            if is_email:
                graph_id = "email_docs_agent"
                logger.info("📧 EMAIL ticket detected - using email_docs_agent")
            else:
                graph_id = "pylon_chat_docs_agent"
                logger.info("💬 CHAT WIDGET ticket detected - using pylon_chat_docs_agent")

            # Get LangGraph assistant
            thread_id = pylon_request.issue_id
            logger.info(f"Thread: {thread_id}")

            # Use graph_id directly as assistant_id (avoids auth-filtered search)
            # For LangGraph Cloud deployments, graph_id == assistant_id
            assistant_id = graph_id
            logger.info(f"Assistant: {assistant_id}")

            # Check if thread exists
            thread_exists = False
            try:
                await self.graph_client.threads.get(thread_id)
                thread_exists = True
                logger.info("EXISTING thread - reusing conversation history")
            except Exception:
                await self.graph_client.threads.create(thread_id=thread_id)
                logger.info("NEW thread - starting fresh")

            # Build messages (only include system context for NEW threads to avoid Anthropic error)
            # Format user message content - use multimodal format if files are present
            if customer_files:
                user_content = [
                    {"type": "text", "text": current_question}
                ] + customer_files
            else:
                user_content = current_question

            if not thread_exists:
                agent_messages = [
                    {"role": "system", "content": context},
                    {"role": "user", "content": user_content}
                ]
                logger.info(f"Sending: [system + user] (with {len(customer_files)} files)")
            else:
                agent_messages = [
                    {"role": "user", "content": user_content}
                ]
                logger.info(f"Sending: [user only] (history from checkpoint, with {len(customer_files)} files)")

            # Create LangGraph run with standardized metadata for tracing
            # Pylon is the source for both email and chat widget interactions
            pylon_channel = "chat" if is_chat else "email"

            run = await self.graph_client.runs.create(
                thread_id=thread_id,
                assistant_id=assistant_id,
                input={"messages": agent_messages},
                metadata=build_trace_metadata(
                    # User context
                    user_id=customer_email,
                    user_email=customer_email,
                    user_name=customer_name,
                    user_org=extract_org_from_email(customer_email),
                    # Source context
                    source_type="Pylon",
                    pylon_channel=pylon_channel,  # "chat" or "email"
                    # Ticket context
                    ticket_id=pylon_request.issue_id,
                    ticket_number=ticket_details.get("number"),
                    ticket_status=ticket_details.get("status"),
                    ticket_priority=ticket_details.get("priority"),
                    ticket_category=ticket_details.get("category"),
                    # Agent context
                    graph_id=graph_id,
                ),
            )

            logger.info(f"Run: {run['run_id']}")
            await self.graph_client.runs.join(thread_id, run["run_id"])
            logger.info("Run completed")

            # Extract AI response and check for escalation
            state = await self.graph_client.threads.get_state(thread_id)
            state_values = state["values"]
            messages = state_values.get("messages", [])

            # Check if agent detected escalation request
            escalation_requested = state_values.get("escalation_requested", False)

            if escalation_requested:
                logger.info("🚨 ESCALATION DETECTED by agent - handling escalation")

                # Update escalation field in Pylon
                try:
                    await self.pylon_client.update_custom_field(
                        ticket_id=pylon_request.issue_id,
                        field_name="escalator_to_human",
                        field_value="true"
                    )
                    logger.info("Set escalator_to_human field to true")
                except Exception as e:
                    logger.warning(f"Could not update escalator_to_human field: {e}")

                # Extract customer name for escalation greeting
                customer_name = ""
                if pylon_messages:
                    first_msg = pylon_messages[0]
                    author = first_msg.get("author", {})
                    contact = author.get("contact", {})
                    if contact:
                        customer_name = _sanitize_customer_name(author.get("name", ""))

                # Send escalation confirmation message
                greeting = f"Hi {customer_name}," if customer_name else "Hi,"
                escalation_message = f"{greeting}\n\nI've escalated your request to our human support team. A team member will reach out to you shortly to assist with your question.\n\nThank you for your patience!\n\nBest,\nLangChain AI Support Agent"

                body_html = self._format_html_response(escalation_message)
                reply_to_msg_id = self._find_most_recent_customer_message_id(pylon_messages)

                if not reply_to_msg_id and pylon_messages:
                    reply_to_msg_id = pylon_messages[0].get("id")

                await self.pylon_client.post_reply(
                    ticket_id=pylon_request.issue_id,
                    body_html=body_html,
                    message_id=reply_to_msg_id,
                    cached_messages=pylon_messages
                )

                logger.info("Sent escalation confirmation to customer")

                return PylonResponse(
                    status="success",
                    issue_id=pylon_request.issue_id,
                    reply_posted=True,
                )

            # Normal flow: extract AI response
            ai_response = None
            for msg in reversed(messages):
                if hasattr(msg, "content"):
                    ai_response = msg.content
                    break
                elif isinstance(msg, dict) and msg.get("type") == "ai":
                    ai_response = msg.get("content", "")
                    break

            if not ai_response:
                raise ValueError("No AI response generated")

            logger.info(f"Response: {len(ai_response)} chars")

            # Add personalized greeting and signature for email tickets
            if is_email:
                # Extract customer name from the first message
                customer_name = ""
                if pylon_messages:
                    first_msg = pylon_messages[0]
                    author = first_msg.get("author", {})
                    contact = author.get("contact", {})
                    if contact:
                        customer_name = _sanitize_customer_name(author.get("name", ""))

                # Wrap response with greeting and signature
                greeting = f"Hi {customer_name}," if customer_name else "Hi,"
                ai_response = f"{greeting}\n\n{ai_response}\n\nBest,\nLangChain Support Agent"
                logger.info(f"Added email greeting for: {customer_name or '(no name)'}")

            # Convert to HTML and post to Pylon
            body_html = self._format_html_response(ai_response)
            reply_to_msg_id = self._find_most_recent_customer_message_id(pylon_messages)

            if not reply_to_msg_id and pylon_messages:
                reply_to_msg_id = pylon_messages[0].get("id")

            logger.info(f"Posting to Pylon (reply_to: {reply_to_msg_id})")

            await self.pylon_client.post_reply(
                ticket_id=pylon_request.issue_id,
                body_html=body_html,
                message_id=reply_to_msg_id,
                cached_messages=pylon_messages
            )

            logger.info("=" * 80)
            logger.info(f"SUCCESS: {pylon_request.issue_id}")
            logger.info(f"   Source: {'EMAIL' if is_email else 'CHAT'}")
            logger.info(f"   Agent: {graph_id}")
            logger.info(f"   Thread: {thread_id} ({'new' if not thread_exists else 'existing'})")
            logger.info(f"   Messages: {len(messages)}")
            logger.info("=" * 80)

            return PylonResponse(
                status="success",
                issue_id=pylon_request.issue_id,
                reply_posted=True,
            )

        except HTTPException:
            raise

        except Exception as e:
            logger.error(f"Error processing ticket {pylon_request.issue_id}: {e}", exc_info=True)

            # Don't send error messages to customers - just log and let human support handle it
            return PylonResponse(
                status="error",
                issue_id=pylon_request.issue_id,
                reply_posted=False,
                error=str(e),
            )

        finally:
            # Always cleanup processing lock
            self._processing_tickets.discard(pylon_request.issue_id)
