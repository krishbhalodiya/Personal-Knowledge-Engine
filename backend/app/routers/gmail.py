from typing import Dict, Any, Literal
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from ..services.google.gmail import GmailService, get_gmail_service
from ..services.google.auth import GoogleAuthService

router = APIRouter(prefix="/gmail", tags=["gmail"])

class SyncRequest(BaseModel):
    max_results: int = Field(50, description="Maximum number of emails to sync", ge=1, le=200)
    filter_type: Literal["all", "primary", "important", "unread"] = Field(
        "primary",
        description="Filter type: 'all' (everything), 'primary' (excludes promotions), 'important', 'unread'"
    )
    skip_promotional: bool = Field(
        True,
        description="Additional filter to skip promotional-looking emails based on sender/subject patterns"
    )

class SyncResponse(BaseModel):
    processed: int
    errors: int
    skipped: int = 0
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
    
    **Filter Types:**
    - `all`: Sync all emails (not recommended - includes spam/promotions)
    - `primary`: Only primary inbox emails (default, excludes promotions/social/updates)
    - `important`: Only emails marked as important
    - `unread`: Only unread emails
    
    **Additional Filtering:**
    - `skip_promotional`: When true, also skips emails that look promotional based on
      sender patterns (noreply@, newsletter@, etc.) and subject keywords (sale, discount, etc.)
    """
    try:
        stats = await service.sync_emails(
            max_results=request.max_results,
            filter_type=request.filter_type,
            skip_promotional=request.skip_promotional
        )
        
        filter_desc = f"filter={request.filter_type}"
        if request.skip_promotional:
            filter_desc += ", promotional emails skipped"
            
        return SyncResponse(
            **stats,
            message=f"Gmail sync completed ({filter_desc})"
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

