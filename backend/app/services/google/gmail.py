import logging
import base64
from typing import List, Optional, Dict, Any
from datetime import datetime

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .auth import GoogleAuthService
from ..ingestion import get_ingestion_service
from ...models.documents import Document, DocumentType

logger = logging.getLogger(__name__)

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

    def list_messages(self, max_results: int = 10, query: str = "") -> List[Dict[str, Any]]:
        """List messages from Gmail."""
        try:
            service = self._get_service()
            results = service.users().messages().list(
                userId='me',
                maxResults=max_results,
                q=query
            ).execute()
            messages = results.get('messages', [])
            return messages
        except HttpError as error:
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

    async def sync_emails(self, max_results: int = 50) -> Dict[str, int]:
        """
        Fetch recent emails and ingest them into the vector store.
        Returns stats on processed emails.
        """
        messages = self.list_messages(max_results=max_results)
        logger.info(f"Found {len(messages)} emails to process")
        
        count = 0
        errors = 0
        
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
                
                body = self._parse_email_body(payload)
                
                if not body.strip():
                    continue
                
                # Create content for indexing
                # We add metadata to the text content to help the model understand context
                content = f"""
Email Subject: {subject}
From: {sender}
Date: {date_str}

Content:
{body}
"""
                
                # Ingest as a document
                # We use a custom filename format to identify it as an email
                filename = f"email_{msg['id']}.txt"
                
                # Check if already exists (optional optimization)
                # For now, we rely on ingestion service deduplication or updates
                
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
                
        return {"processed": count, "errors": errors, "total_found": len(messages)}

# Singleton
_gmail_service = None

def get_gmail_service():
    global _gmail_service
    if _gmail_service is None:
        _gmail_service = GmailService()
    return _gmail_service

