import logging
import base64
import re
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .auth import GoogleAuthService
from ..ingestion import get_ingestion_service
from ...models.documents import Document, DocumentType

logger = logging.getLogger(__name__)

# Common promotional/spam sender patterns to filter out
SPAM_SENDER_PATTERNS = [
    r'noreply@',
    r'no-reply@',
    r'notifications@',
    r'newsletter@',
    r'marketing@',
    r'promo@',
    r'promotions@',
    r'deals@',
    r'offers@',
    r'info@.*\.shopify\.com',
    r'@email\..*\.com',  # Many marketing emails use subdomains like email.company.com
]

# Subjects that indicate promotional content
SPAM_SUBJECT_PATTERNS = [
    r'unsubscribe',
    r'\b(sale|discount|off|deal|offer|promo|coupon|save)\b',
    r'\b(free shipping|limited time|act now|don\'t miss)\b',
    r'weekly digest',
    r'newsletter',
]


class GmailService:
    """Service for interacting with Gmail API."""
    
    def __init__(self):
        self.auth_service = GoogleAuthService()
        self.ingestion_service = get_ingestion_service()
        
    def _get_service(self):
        """Get authenticated Gmail service."""
        creds = self.auth_service.get_credentials()
        if not creds:
            raise ValueError("User not authenticated with Google")
        return build('gmail', 'v1', credentials=creds)

    def _build_filter_query(
        self, 
        filter_type: Literal["all", "primary", "important", "unread"] = "primary",
        custom_query: str = ""
    ) -> str:
        """
        Build Gmail search query to filter emails.
        
        Filter types:
        - all: All emails (no filter)
        - primary: Primary inbox only (excludes promotions, social, updates, forums)
        - important: Only emails marked as important
        - unread: Only unread emails
        """
        queries = []
        
        if filter_type == "primary":
            # Exclude promotional categories
            queries.append("category:primary")
            # Also exclude common promotional senders
            queries.append("-category:promotions")
            queries.append("-category:social")
            queries.append("-category:updates")
            queries.append("-category:forums")
        elif filter_type == "important":
            queries.append("is:important")
        elif filter_type == "unread":
            queries.append("is:unread")
        
        if custom_query:
            queries.append(custom_query)
            
        return " ".join(queries)

    def _is_likely_spam(self, sender: str, subject: str) -> bool:
        """Check if email is likely spam/promotional based on sender and subject."""
        sender_lower = sender.lower()
        subject_lower = subject.lower()
        
        # Check sender patterns
        for pattern in SPAM_SENDER_PATTERNS:
            if re.search(pattern, sender_lower):
                logger.debug(f"Skipping promotional email from: {sender}")
                return True
        
        # Check subject patterns
        for pattern in SPAM_SUBJECT_PATTERNS:
            if re.search(pattern, subject_lower, re.IGNORECASE):
                logger.debug(f"Skipping promotional email with subject: {subject[:50]}")
                return True
        
        return False

    def list_messages(
        self, 
        max_results: int = 10, 
        query: str = "",
        filter_type: Literal["all", "primary", "important", "unread"] = "primary"
    ) -> List[Dict[str, Any]]:
        """List messages from Gmail with optional filtering."""
        try:
            service = self._get_service()
            
            # Build the query with filters
            full_query = self._build_filter_query(filter_type, query)
            logger.info(f"Gmail query: {full_query}")
            
            results = service.users().messages().list(
                userId='me',
                maxResults=max_results,
                q=full_query
            ).execute()
            messages = results.get('messages', [])
            return messages
        except HttpError as error:
            if error.resp.status == 403 and "accessNotConfigured" in str(error):
                logger.error("Gmail API not enabled. Please enable it in Google Cloud Console.")
                raise ValueError("Gmail API not enabled in Google Cloud Console.")
            logger.error(f"An error occurred: {error}")
            return []

    def get_message_detail(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Get full details of a specific message."""
        try:
            service = self._get_service()
            message = service.users().messages().get(
                userId='me', 
                id=message_id,
                format='full'
            ).execute()
            return message
        except HttpError as error:
            logger.error(f"An error occurred fetching message {message_id}: {error}")
            return None

    def _parse_email_body(self, payload: Dict[str, Any]) -> str:
        """Recursively extract text body from email payload."""
        body = ""
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    if 'data' in part['body']:
                        data = part['body']['data']
                        body += base64.urlsafe_b64decode(data).decode('utf-8')
                elif part['mimeType'] == 'text/html':
                    # Skip HTML for now, or use BeautifulSoup to strip tags if needed
                    # prioritizing plain text
                    pass
                elif 'parts' in part:
                    body += self._parse_email_body(part)
        elif 'body' in payload and 'data' in payload['body']:
            data = payload['body']['data']
            body += base64.urlsafe_b64decode(data).decode('utf-8')
            
        return body

    def _extract_header(self, headers: List[Dict[str, str]], name: str) -> str:
        """Extract a specific header value."""
        for header in headers:
            if header['name'].lower() == name.lower():
                return header['value']
        return ""

    async def sync_emails(
        self, 
        max_results: int = 50,
        filter_type: Literal["all", "primary", "important", "unread"] = "primary",
        skip_promotional: bool = True
    ) -> Dict[str, int]:
        """
        Fetch recent emails and ingest them into the vector store.
        
        Args:
            max_results: Maximum number of emails to fetch
            filter_type: Type of filter to apply:
                - "all": All emails
                - "primary": Primary inbox only (default, excludes promotions/social)
                - "important": Only important emails
                - "unread": Only unread emails
            skip_promotional: Additional check to skip promotional-looking emails
        
        Returns stats on processed emails.
        """
        messages = self.list_messages(max_results=max_results, filter_type=filter_type)
        logger.info(f"Found {len(messages)} emails to process (filter: {filter_type})")
        
        count = 0
        errors = 0
        skipped = 0
        
        for msg in messages:
            try:
                full_msg = self.get_message_detail(msg['id'])
                if not full_msg:
                    continue
                
                payload = full_msg['payload']
                headers = payload.get('headers', [])
                
                subject = self._extract_header(headers, 'Subject') or "(No Subject)"
                sender = self._extract_header(headers, 'From')
                date_str = self._extract_header(headers, 'Date')
                
                # Additional spam check
                if skip_promotional and self._is_likely_spam(sender, subject):
                    skipped += 1
                    continue
                
                body = self._parse_email_body(payload)
                
                if not body.strip():
                    skipped += 1
                    continue
                
                # Skip emails with very short bodies (likely automated)
                if len(body.strip()) < 50:
                    skipped += 1
                    continue
                
                # Create content for indexing
                content = f"""Email Subject: {subject}
From: {sender}
Date: {date_str}

Content:
{body}
"""
                
                # Ingest as a document
                filename = f"email_{msg['id']}.txt"
                
                await self.ingestion_service.ingest_text(
                    text=content,
                    filename=filename,
                    metadata={
                        "source": "gmail",
                        "message_id": msg['id'],
                        "sender": sender,
                        "subject": subject,
                        "date": date_str,
                        "type": "email"
                    }
                )
                count += 1
                
            except Exception as e:
                logger.error(f"Failed to process email {msg['id']}: {e}")
                errors += 1
        
        logger.info(f"Gmail sync complete: {count} processed, {skipped} skipped, {errors} errors")
        return {
            "processed": count, 
            "errors": errors, 
            "skipped": skipped,
            "total_found": len(messages)
        }

# Singleton
_gmail_service = None

def get_gmail_service():
    global _gmail_service
    if _gmail_service is None:
        _gmail_service = GmailService()
    return _gmail_service

