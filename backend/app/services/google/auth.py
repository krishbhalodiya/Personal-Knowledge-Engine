"""
Google Authentication Service - Handles OAuth 2.0 Flow.

================================================================================
OAUTH 2.0 FLOW EXPLAINED
================================================================================

1. USER ACTION
   User clicks "Connect Google" in frontend.

2. REDIRECT (get_authorization_url)
   Backend generates a Google URL with:
   - Client ID
   - Scopes (what we want to access: Gmail read, Drive read)
   - Redirect URI (where to come back)
   User is redirected there.

3. CONSENT
   User logs in to Google and clicks "Allow".

4. CALLBACK (exchange_code_for_token)
   Google redirects user back to:
   http://localhost:8000/api/auth/google/callback?code=AUTH_CODE
   
   Backend takes this `code` and swaps it for TOKENS:
   - Access Token: Short-lived (1 hour), used for API calls.
   - Refresh Token: Long-lived, used to get new access tokens.

5. STORAGE
   Backend saves these tokens securely.
   
================================================================================
"""

import logging
import json
from pathlib import Path
from typing import Optional, Dict, Any

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from ...config import settings

logger = logging.getLogger(__name__)

# Scopes we need
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "openid",
    "email",
    "profile"
]

class GoogleAuthService:
    """
    Service for handling Google OAuth 2.0 authentication.
    """
    
    def __init__(self):
        self.client_id = settings.google_client_id
        self.client_secret = settings.google_client_secret
        self.redirect_uri = settings.google_redirect_uri
        self.token_path = settings.data_dir / "google_tokens.json"
        
        # Expose scopes
        self.SCOPES = SCOPES
        
        if not self.client_id or not self.client_secret:
            logger.warning("Google Client ID/Secret not configured.")
    
    def get_authorization_url(self) -> str:
        """
        Generate the URL to redirect the user to Google.
        """
        if not self.client_id:
            raise ValueError("Google Client ID not configured")
            
        # Create flow instance
        flow = Flow.from_client_config(
            client_config=self._get_client_config(),
            scopes=SCOPES,
            redirect_uri=self.redirect_uri
        )
        
        # Generate URL
        # access_type='offline' gives us a Refresh Token (crucial!)
        # include_granted_scopes='true' enables incremental auth
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'  # Force consent screen to ensure we get refresh token
        )
        
        return auth_url
    
    def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        Exchange the authorization code for credentials.
        """
        if not self.client_id:
            raise ValueError("Google Client ID not configured")
            
        flow = Flow.from_client_config(
            client_config=self._get_client_config(),
            scopes=SCOPES,
            redirect_uri=self.redirect_uri
        )
        
        # Exchange code
        flow.fetch_token(code=code)
        creds = flow.credentials
        
        # Save credentials
        self._save_credentials(creds)
        
        return {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "scopes": creds.scopes,
            "expiry": creds.expiry.isoformat() if creds.expiry else None
        }
    
    def get_credentials(self) -> Optional[Credentials]:
        """
        Get valid user credentials. Refreshes if expired.
        """
        creds = self._load_credentials()
        
        if not creds:
            return None
            
        # Refresh if expired
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                self._save_credentials(creds)
                logger.info("Refreshed Google access token")
            except Exception as e:
                logger.error(f"Failed to refresh token: {e}")
                return None
                
        return creds
    
    def is_authenticated(self) -> bool:
        """Check if we have valid credentials."""
        creds = self.get_credentials()
        return creds is not None and creds.valid
    
    def logout(self):
        """Remove stored credentials."""
        if self.token_path.exists():
            self.token_path.unlink()
            logger.info("Logged out from Google (tokens deleted)")
    
    # =========================================================================
    # HELPERS
    # =========================================================================
    
    def _get_client_config(self) -> Dict[str, Any]:
        """Construct the client config dictionary expected by google-auth."""
        return {
            "web": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }
    
    def _save_credentials(self, creds: Credentials):
        """Save credentials to file."""
        data = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": creds.scopes
        }
        
        with open(self.token_path, 'w') as f:
            json.dump(data, f)
            
        logger.info(f"Saved Google credentials to {self.token_path}")
        
    def _load_credentials(self) -> Optional[Credentials]:
        """Load credentials from file."""
        if not self.token_path.exists():
            return None
            
        try:
            with open(self.token_path, 'r') as f:
                data = json.load(f)
                
            return Credentials(
                token=data.get("token"),
                refresh_token=data.get("refresh_token"),
                token_uri=data.get("token_uri"),
                client_id=data.get("client_id"),
                client_secret=data.get("client_secret"),
                scopes=data.get("scopes")
            )
        except Exception as e:
            logger.error(f"Failed to load credentials: {e}")
            return None


# Singleton
_auth_service: Optional[GoogleAuthService] = None

def get_google_auth_service() -> GoogleAuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = GoogleAuthService()
    return _auth_service

