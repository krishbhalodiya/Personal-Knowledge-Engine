import logging
import io
from typing import List, Optional, Dict, Any
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError

from .auth import GoogleAuthService
from ..ingestion import get_ingestion_service

logger = logging.getLogger(__name__)

class DriveService:
    """Service for interacting with Google Drive API."""
    
    def __init__(self):
        self.auth_service = GoogleAuthService()
        self.ingestion_service = get_ingestion_service()
        
    def _get_service(self):
        """Get authenticated Drive service."""
        creds = self.auth_service.get_credentials()
        if not creds:
            raise ValueError("User not authenticated with Google")
        return build('drive', 'v3', credentials=creds)

    def list_files(self, page_size: int = 10) -> List[Dict[str, Any]]:
        """List recent files from Drive."""
        try:
            service = self._get_service()
            # Filter out folders, trash, and shortcuts
            q = (
                "mimeType != 'application/vnd.google-apps.folder' and "
                "trashed = false"
            )
            
            results = service.files().list(
                pageSize=page_size,
                fields="nextPageToken, files(id, name, mimeType, createdTime, description)",
                q=q
            ).execute()
            
            return results.get('files', [])
        except HttpError as error:
            if error.resp.status == 403 and "accessNotConfigured" in str(error):
                logger.error("Drive API not enabled. Please enable it in Google Cloud Console.")
                raise ValueError("Google Drive API not enabled in Google Cloud Console.")
            logger.error(f"An error occurred: {error}")
            return []

    def download_file(self, file_id: str, mime_type: str) -> Optional[bytes]:
        """
        Download file content.
        - Google Docs/Sheets: Export to PDF/Text
        - Binary files: Download directly
        """
        try:
            service = self._get_service()
            request = None
            
            # Google Workspace Documents need exporting
            if mime_type == 'application/vnd.google-apps.document':
                # Export Google Doc to plain text
                request = service.files().export_media(
                    fileId=file_id,
                    mimeType='text/plain'
                )
            elif mime_type == 'application/vnd.google-apps.spreadsheet':
                # Export Sheets to PDF (parsing CSV is messy without structure)
                request = service.files().export_media(
                    fileId=file_id,
                    mimeType='application/pdf'
                )
            elif mime_type == 'application/vnd.google-apps.presentation':
                # Export Slides to PDF
                request = service.files().export_media(
                    fileId=file_id,
                    mimeType='application/pdf'
                )
            elif mime_type.startswith('application/vnd.google-apps.'):
                # Other Google apps (Forms, Drawings, etc) - skip for now
                logger.info(f"Skipping unsupported Google App file: {mime_type}")
                return None
            else:
                # Binary files (PDF, DOCX, TXT uploaded to Drive)
                request = service.files().get_media(fileId=file_id)
                
            # Execute download
            file_content = io.BytesIO()
            downloader = MediaIoBaseDownload(file_content, request)
            
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                
            return file_content.getvalue()
            
        except HttpError as error:
            logger.error(f"An error occurred downloading file {file_id}: {error}")
            return None

    async def sync_drive(self, limit: int = 10) -> Dict[str, int]:
        """
        Fetch recent Drive files and ingest them.
        """
        files = self.list_files(page_size=limit)
        logger.info(f"Found {len(files)} Drive files to process")
        
        count = 0
        errors = 0
        
        for file in files:
            try:
                content = self.download_file(file['id'], file['mimeType'])
                
                if not content:
                    continue
                
                # Determine extension for filename if needed
                filename = file['name']
                mime_type = file['mimeType']
                
                # Append extension if missing, based on what we downloaded as
                if mime_type == 'application/vnd.google-apps.document':
                    if not filename.endswith('.txt'):
                        filename += '.txt'
                elif mime_type == 'application/vnd.google-apps.spreadsheet':
                    if not filename.endswith('.pdf'):
                        filename += '.pdf'
                elif mime_type == 'application/vnd.google-apps.presentation':
                    if not filename.endswith('.pdf'):
                        filename += '.pdf'
                
                # Ingest
                await self.ingestion_service.ingest_bytes(
                    content=content,
                    filename=filename,
                    metadata={
                        "source": "google_drive",
                        "file_id": file['id'],
                        "mime_type": file['mimeType'],
                        "created_time": file.get('createdTime'),
                        "description": file.get('description', "")
                    }
                )
                count += 1
                
            except Exception as e:
                logger.error(f"Failed to process Drive file {file['id']}: {e}")
                errors += 1
                
        return {"processed": count, "errors": errors, "total_found": len(files)}

# Singleton
_drive_service = None

def get_drive_service():
    global _drive_service
    if _drive_service is None:
        _drive_service = DriveService()
    return _drive_service

