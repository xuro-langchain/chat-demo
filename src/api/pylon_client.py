# Pylon API client for posting replies to tickets
import os
import logging
import re
from typing import Optional, List, Dict, Any
from urllib.parse import unquote
from io import BytesIO
import httpx
import base64

logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

# Maximum file size for processing (10MB)
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

# Text-based MIME types that can be processed as text
TEXT_MIMETYPES = {
    # Plain text
    'text/plain',
    'text/markdown',

    # Programming languages
    'text/x-python',
    'text/x-java',
    'text/x-c',
    'text/x-c++',
    'text/javascript',
    'text/typescript',

    # Web
    'text/html',
    'text/css',
    'text/xml',

    # Data formats
    'application/json',
    'text/csv',
    'application/csv',

    # Scripts
    'application/javascript',
    'application/typescript',
    'application/x-python',
    'application/x-python-code',
    'application/x-sh',
    'text/x-sh',

    # Logs
    'text/x-log',
}

# File extensions for text-based files
TEXT_FILE_EXTENSIONS = (
    # Code files
    '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.cpp', '.c', '.h',
    '.cs', '.go', '.rs', '.rb', '.php', '.sh', '.bash',

    # Config/Data files
    '.yaml', '.yml', '.json', '.xml', '.html', '.css', '.md',
    '.csv',

    # Text/Log files
    '.txt', '.log', '.sql', '.graphql',

    # Other languages
    '.r', '.swift', '.kt', '.scala',

    # Network/Debug files
    '.har',
)


# ============================================================================
# Helper Functions
# ============================================================================

def _extract_filename_from_url(url: str) -> str:
    """Extract and clean filename from a Pylon asset URL.

    Args:
        url: The full URL to the file

    Returns:
        Cleaned filename without UUID prefix
    """
    # Get the path component (before query params)
    url_path = url.split('?')[0]

    # URL decode
    url_path = unquote(url_path)

    # Get just the filename (last part after /)
    filename = url_path.split('/')[-1]

    # Remove UUID prefix (format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx-filename)
    filename = re.sub(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}-',
        '',
        filename
    )

    return filename


def _is_text_file(content_type: str, filename: str) -> bool:
    """Check if a file should be treated as text based on content type or extension.

    Args:
        content_type: MIME type from response headers
        filename: Name of the file

    Returns:
        True if file should be processed as text
    """
    return content_type in TEXT_MIMETYPES or filename.lower().endswith(TEXT_FILE_EXTENSIONS)


def _format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def _extract_text_from_pdf(pdf_content: bytes, filename: str) -> Optional[str]:
    """Extract text from a PDF file.

    Args:
        pdf_content: Raw PDF bytes
        filename: Name of the PDF file

    Returns:
        Extracted text or None if extraction fails
    """
    try:
        from pypdf import PdfReader

        # Create PDF reader from bytes
        pdf_file = BytesIO(pdf_content)
        reader = PdfReader(pdf_file)

        # Check if PDF is encrypted
        if reader.is_encrypted:
            logger.warning(f"PDF '{filename}' is encrypted")
            return None

        # Extract text from all pages
        text_parts = []
        num_pages = len(reader.pages)

        for page_num, page in enumerate(reader.pages, start=1):
            try:
                page_text = page.extract_text()
                if page_text.strip():
                    text_parts.append(f"--- Page {page_num}/{num_pages} ---\n{page_text}")
            except Exception as e:
                logger.warning(f"Could not extract text from page {page_num} of '{filename}': {e}")
                text_parts.append(f"--- Page {page_num}/{num_pages} ---\n[Could not extract text]")

        if not text_parts:
            return None

        return "\n\n".join(text_parts)

    except Exception as e:
        logger.error(f"Failed to extract text from PDF '{filename}': {e}")
        return None


# ============================================================================
# Pylon Client
# ============================================================================

class PylonClient:
    """Client for interacting with Pylon API."""

    def __init__(self):
        """Initialize Pylon API client."""
        self.api_key = os.getenv("PYLON_API_KEY")
        if not self.api_key:
            raise ValueError("PYLON_API_KEY environment variable not set")

        self.base_url = "https://api.usepylon.com"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    # ========================================================================
    # Ticket Operations
    # ========================================================================

    async def get_ticket_details(self, ticket_id: str) -> dict:
        """Get ticket details including title, support tier, plan type, etc.

        Args:
            ticket_id: The Pylon ticket ID

        Returns:
            Ticket details dictionary
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/issues/{ticket_id}",
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", {})

    async def get_ticket_messages(self, ticket_id: str) -> list:
        """Get all messages for a ticket.

        Args:
            ticket_id: The Pylon ticket ID

        Returns:
            List of messages
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/issues/{ticket_id}/messages",
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])

    async def create_thread(
        self,
        ticket_id: str,
        thread_name: str = "AI Agent Notes"
    ) -> str:
        """Create a new thread for a ticket.

        Args:
            ticket_id: The Pylon ticket ID
            thread_name: Name for the thread

        Returns:
            The thread ID
        """
        payload = {"name": thread_name}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/issues/{ticket_id}/threads",
                headers=self.headers,
                json=payload,
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            thread_id = data.get("data", {}).get("id")

            if not thread_id:
                raise ValueError(f"Failed to create thread for ticket {ticket_id}")

            logger.info(f"Created thread {thread_id} for ticket {ticket_id}")
            return thread_id

    async def post_reply(
        self,
        ticket_id: str,
        body_html: str,
        message_id: Optional[str] = None,
        cached_messages: Optional[list] = None
    ) -> dict:
        """Post a reply to a Pylon ticket (handles both email and chat).

        Args:
            ticket_id: The Pylon ticket ID
            body_html: HTML content of the reply
            message_id: Optional message ID to reply to (will fetch if not provided)
            cached_messages: Optional cached messages list to avoid duplicate API call

        Returns:
            API response
        """
        try:
            # Use cached messages if provided, otherwise fetch
            if cached_messages:
                messages = cached_messages
                logger.info(f"Using cached messages for ticket {ticket_id}")
            else:
                logger.info(f"Fetching messages for ticket {ticket_id}")
                messages = await self.get_ticket_messages(ticket_id)

            if not messages:
                raise ValueError(f"No messages found for ticket {ticket_id}")

            first_message = messages[0]

            if not message_id:
                message_id = first_message.get("id")
                if not message_id:
                    raise ValueError(f"No message ID found in ticket {ticket_id}")
                logger.info(f"Found message_id: {message_id}")

            # Detect if chat or email based on source field
            source = first_message.get("source", "")
            is_chat = source == "pylon_chat_widget"

            # Build payload based on issue type
            payload = {
                "message_id": message_id,
                "body_html": body_html
            }

            if is_chat:
                # Chat widget uses destination_metadata
                payload["destination_metadata"] = {"type": "in_app_chat"}
                logger.info("Detected chat widget issue, using destination_metadata")
            else:
                # Email uses email_info
                email_info = first_message.get("email_info", {})
                from_email = email_info.get("from_email")

                if not from_email:
                    raise ValueError(f"No from_email found in ticket {ticket_id}")

                payload["email_info"] = {
                    "to_emails": [from_email],
                    "cc_emails": [],
                    "bcc_emails": []
                }
                logger.info("Detected email issue, using email_info")

            logger.info(f"Payload: {payload}")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/issues/{ticket_id}/reply",
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()

                logger.info(f"Successfully posted reply to ticket {ticket_id}")
                return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error posting reply to ticket {ticket_id}: {e}")
            logger.error(f"Response: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error posting reply to ticket {ticket_id}: {e}")
            raise

    async def update_custom_field(
        self,
        ticket_id: str,
        field_name: str,
        field_value: Any
    ) -> dict:
        """Update a custom field on a Pylon ticket.

        Args:
            ticket_id: The Pylon ticket ID
            field_name: Name of the custom field (e.g., "escalate_to_human")
            field_value: Value to set (e.g., "true", "false", string, number)
                        Note: Pylon expects string values, not booleans

        Returns:
            API response
        """
        try:
            payload = {
                "custom_fields": [
                    {
                        "slug": field_name,
                        "value": field_value
                    }
                ]
            }

            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{self.base_url}/issues/{ticket_id}",
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()

                logger.info(f"Successfully updated {field_name}={field_value} on ticket {ticket_id}")
                return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error updating custom field on ticket {ticket_id}: {e}")
            logger.error(f"Response: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error updating custom field on ticket {ticket_id}: {e}")
            raise

    # ========================================================================
    # File Extraction
    # ========================================================================

    async def extract_files_from_messages(
        self,
        messages: List[dict]
    ) -> List[Dict[str, Any]]:
        """Extract and download files from Pylon messages.

        Supports:
        - Images (PNG, JPEG, GIF, WebP, etc.)
        - Text/code files (Python, JavaScript, TypeScript, etc.)
        - Logs and config files (JSON, YAML, CSV, etc.)
        - Network debug files (HAR)

        Args:
            messages: List of Pylon message objects

        Returns:
            List of content blocks in multimodal format for AI processing
        """
        content_blocks = []
        processed_urls = set()

        for msg in messages:
            # Only process customer messages (skip bot/agent messages)
            author = msg.get("author", {})
            is_customer = bool(author.get("contact")) or bool(author.get("user"))
            if not is_customer:
                continue

            # Extract from file_urls field (contains all attachments + inline images)
            file_urls = msg.get("file_urls", [])
            for file_url in file_urls:
                if file_url in processed_urls:
                    continue
                processed_urls.add(file_url)

                filename = _extract_filename_from_url(file_url)

                try:
                    # Download the file
                    async with httpx.AsyncClient() as client:
                        response = await client.get(file_url, timeout=30.0)
                        response.raise_for_status()

                        file_content = response.content
                        content_type = response.headers.get('content-type', 'application/octet-stream')
                        file_size = len(file_content)

                        # Check file size limit
                        if file_size > MAX_FILE_SIZE_BYTES:
                            size_str = _format_file_size(file_size)
                            max_str = _format_file_size(MAX_FILE_SIZE_BYTES)
                            logger.warning(f"Skipping large file: {filename} ({size_str})")
                            content_blocks.append({
                                "type": "text",
                                "text": f"[File '{filename}' is too large to process ({size_str}, max {max_str})]"
                            })
                            continue

                        # Process the file content
                        processed_block = await self._process_file_content(
                            filename=filename,
                            content=file_content,
                            content_type=content_type
                        )

                        if processed_block:
                            content_blocks.append(processed_block)

                except Exception as e:
                    logger.error(f"Failed to download file from {file_url}: {e}")
                    content_blocks.append({
                        "type": "text",
                        "text": f"[Failed to download file '{filename}']"
                    })
                    continue

            # Fallback: check attachments field if file_urls is empty
            if not file_urls:
                attachments = msg.get("attachments", [])
                for attachment in attachments:
                    attachment_url = attachment.get("url")
                    if not attachment_url or attachment_url in processed_urls:
                        continue

                    processed_urls.add(attachment_url)
                    filename = attachment.get("name", "unnamed")
                    content_type = attachment.get("content_type", "")
                    file_size = attachment.get("size", 0)

                    # Check file size
                    if file_size > MAX_FILE_SIZE_BYTES:
                        size_str = _format_file_size(file_size)
                        max_str = _format_file_size(MAX_FILE_SIZE_BYTES)
                        logger.warning(f"Skipping large attachment: {filename} ({size_str})")
                        content_blocks.append({
                            "type": "text",
                            "text": f"[File '{filename}' is too large ({size_str}, max {max_str})]"
                        })
                        continue

                    try:
                        async with httpx.AsyncClient() as client:
                            response = await client.get(
                                attachment_url,
                                headers={"Authorization": f"Bearer {self.api_key}"},
                                timeout=30.0
                            )
                            response.raise_for_status()
                            file_content = response.content

                            processed_block = await self._process_file_content(
                                filename=filename,
                                content=file_content,
                                content_type=content_type
                            )

                            if processed_block:
                                content_blocks.append(processed_block)

                    except Exception as e:
                        logger.error(f"Failed to download attachment {attachment_url}: {e}")
                        content_blocks.append({
                            "type": "text",
                            "text": f"[Failed to download file '{filename}']"
                        })
                        continue

        return content_blocks

    async def _process_file_content(
        self,
        filename: str,
        content: bytes,
        content_type: str
    ) -> Optional[Dict[str, Any]]:
        """Process file content based on its type.

        Args:
            filename: Name of the file
            content: Raw file content
            content_type: MIME type

        Returns:
            Content block dictionary or None if unsupported
        """
        # Handle images
        if content_type.startswith("image/"):
            base64_data = base64.b64encode(content).decode('utf-8')
            logger.info(f"Processed image: {filename} ({content_type})")
            return {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{content_type};base64,{base64_data}"
                }
            }

        # Handle text-based files (code, logs, configs, CSV, etc.)
        if _is_text_file(content_type, filename):
            try:
                text_content = content.decode('utf-8')
                logger.info(f"Processed text file: {filename} ({content_type})")
                return {
                    "type": "text",
                    "text": f"**File: {filename}**\n```\n{text_content}\n```"
                }
            except UnicodeDecodeError:
                logger.warning(f"Could not decode text file: {filename}")
                return {
                    "type": "text",
                    "text": f"[File '{filename}' could not be decoded as text]"
                }

        # Handle PDFs
        if content_type == "application/pdf":
            logger.info(f"Processing PDF file: {filename}")
            pdf_text = _extract_text_from_pdf(content, filename)

            if pdf_text:
                logger.info(f"Successfully extracted text from PDF: {filename}")
                return {
                    "type": "text",
                    "text": f"**PDF File: {filename}**\n```\n{pdf_text}\n```"
                }
            else:
                # Could be encrypted, scanned image, or empty
                logger.warning(f"Could not extract text from PDF: {filename}")
                return {
                    "type": "text",
                    "text": f"[PDF file '{filename}' could not be parsed - it may be encrypted, image-based, or empty]"
                }

        # Unsupported file type
        logger.warning(f"Unsupported file type: {filename} ({content_type})")
        return {
            "type": "text",
            "text": f"[File '{filename}' has unsupported type: {content_type}]"
        }
