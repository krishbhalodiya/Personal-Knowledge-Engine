from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from ..services.google.gmail import GmailService, get_gmail_service
from ..services.google.auth import GoogleAuthService

router = APIRouter(prefix="/gmail", tags=["gmail"])

class SyncRequest(BaseModel):
    max_results: int = 50

class SyncResponse(BaseModel):
    processed: int
    errors: int
    total_found: int
    message: str

@router.get("/auth/status")
async def get_gmail_auth_status():
    """Check if Gmail access is authorized."""
    auth_service = GoogleAuthService()
    return {
        "authenticated": auth_service.is_authenticated(),
        "scopes": auth_service.SCOPES
    }

@router.post("/sync", response_model=SyncResponse)
async def sync_gmail(
    request: SyncRequest,
    service: GmailService = Depends(get_gmail_service)
):
    """
    Sync recent emails from Gmail.
    
    Fetches emails, parses them, and ingests them into the vector store.
    """
    try:
        stats = await service.sync_emails(max_results=request.max_results)
        return SyncResponse(
            **stats,
            message="Gmail sync completed successfully"
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

