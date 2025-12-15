"""Google Integration API Routes."""

import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import RedirectResponse

from ..services.google.auth import GoogleAuthService, get_google_auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/google", tags=["google-auth"])


@router.get("/url")
async def get_auth_url(
    auth_service: GoogleAuthService = Depends(get_google_auth_service)
):
    """
    Get the Google Login URL.
    Frontend should redirect the user to this URL.
    """
    try:
        url = auth_service.get_authorization_url()
        return {"url": url}
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/callback")
async def auth_callback(
    code: str,
    error: str = None,
    auth_service: GoogleAuthService = Depends(get_google_auth_service)
):
    """
    Handle the redirect from Google.
    Exchanges code for tokens.
    """
    if error:
        raise HTTPException(status_code=400, detail=f"Auth error: {error}")
        
    try:
        auth_service.exchange_code_for_token(code)
        
        # Redirect to frontend success page
        # Adjust port/path as needed
        return RedirectResponse("http://localhost:3000?google_auth=success")
        
    except Exception as e:
        logger.error(f"Auth callback failed: {e}")
        raise HTTPException(status_code=500, detail="Authentication failed")


@router.get("/status")
async def get_auth_status(
    auth_service: GoogleAuthService = Depends(get_google_auth_service)
):
    """
    Check if we are connected to Google.
    """
    return {
        "authenticated": auth_service.is_authenticated()
    }


@router.post("/logout")
async def logout(
    auth_service: GoogleAuthService = Depends(get_google_auth_service)
):
    """
    Disconnect from Google.
    """
    auth_service.logout()
    return {"message": "Logged out"}

