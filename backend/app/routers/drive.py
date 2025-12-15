from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from ..services.google.drive import DriveService, get_drive_service
from ..services.google.auth import GoogleAuthService

router = APIRouter(prefix="/drive", tags=["drive"])

class SyncRequest(BaseModel):
    limit: int = 10

class SyncResponse(BaseModel):
    processed: int
    errors: int
    total_found: int
    message: str

@router.get("/auth/status")
async def get_drive_auth_status():
    """Check if Drive access is authorized."""
    auth_service = GoogleAuthService()
    return {
        "authenticated": auth_service.is_authenticated(),
        "scopes": auth_service.SCOPES
    }

@router.post("/sync", response_model=SyncResponse)
async def sync_drive(
    request: SyncRequest,
    service: DriveService = Depends(get_drive_service)
):
    """
    Sync recent files from Google Drive.
    """
    try:
        stats = await service.sync_drive(limit=request.limit)
        return SyncResponse(
            **stats,
            message="Drive sync completed successfully"
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

