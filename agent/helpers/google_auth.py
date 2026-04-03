"""
Google OAuth2 Manager — handles authentication for Gmail and Calendar APIs.

First-time setup:
1. Create a project in Google Cloud Console
2. Enable Gmail API and Google Calendar API
3. Create OAuth 2.0 credentials (Desktop app)
4. Download credentials JSON → save as agent/data/google_credentials.json
5. Run this module directly: `python -m helpers.google_auth` to complete the OAuth flow
"""

import logging
import os
from pathlib import Path

from config import Config

logger = logging.getLogger("mira.helpers.google_auth")

# Google API scopes
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar.events",
]

# Paths
CREDENTIALS_PATH = Config.DATA_DIR / "google_credentials.json"
TOKEN_PATH = Config.DATA_DIR / "google_token.json"


class GoogleAuthManager:
    """Manages Google OAuth2 credentials for Gmail and Calendar access."""

    def __init__(
        self,
        credentials_path: Path = None,
        token_path: Path = None,
    ):
        self.credentials_path = credentials_path or CREDENTIALS_PATH
        self.token_path = token_path or TOKEN_PATH
        self._credentials = None

    def get_credentials(self):
        """Return valid Google OAuth2 credentials.

        - If a saved token exists and is valid, return it.
        - If the token is expired, refresh it.
        - If no token exists, run the interactive OAuth flow (first-time setup).

        Returns:
            google.oauth2.credentials.Credentials or None on failure.
        """
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError:
            logger.error(
                "Google auth libraries not installed. Run: "
                "pip install google-auth google-auth-oauthlib google-api-python-client"
            )
            return None

        creds = None

        # 1. Try loading existing token
        if self.token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(
                    str(self.token_path), SCOPES
                )
                logger.debug("Loaded existing Google token")
            except Exception as e:
                logger.warning(f"Failed to load token: {e}")
                creds = None

        # 2. Refresh if expired
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                self._save_token(creds)
                logger.info("Google token refreshed successfully")
            except Exception as e:
                logger.warning(f"Token refresh failed: {e}")
                creds = None

        # 3. Interactive OAuth flow (first-time setup)
        if not creds or not creds.valid:
            if not self.credentials_path.exists():
                logger.error(
                    f"Google credentials file not found at {self.credentials_path}. "
                    "Download from Google Cloud Console → OAuth 2.0 Client IDs."
                )
                return None

            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_path), SCOPES
                )
                creds = flow.run_local_server(port=0)
                self._save_token(creds)
                logger.info("Google OAuth flow completed — token saved")
            except Exception as e:
                logger.error(f"OAuth flow failed: {e}")
                return None

        self._credentials = creds
        return creds

    def _save_token(self, creds):
        """Persist token to disk for next startup."""
        Config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(creds.to_json())
        logger.debug(f"Token saved to {self.token_path}")

    def get_gmail_service(self):
        """Build and return a Gmail API service object.

        Returns:
            googleapiclient.discovery.Resource for Gmail, or None.
        """
        try:
            from googleapiclient.discovery import build
        except ImportError:
            logger.error("google-api-python-client not installed")
            return None

        creds = self.get_credentials()
        if not creds:
            return None

        try:
            service = build("gmail", "v1", credentials=creds)
            logger.info("Gmail service created")
            return service
        except Exception as e:
            logger.error(f"Failed to build Gmail service: {e}")
            return None

    def get_calendar_service(self):
        """Build and return a Google Calendar API service object.

        Returns:
            googleapiclient.discovery.Resource for Calendar, or None.
        """
        try:
            from googleapiclient.discovery import build
        except ImportError:
            logger.error("google-api-python-client not installed")
            return None

        creds = self.get_credentials()
        if not creds:
            return None

        try:
            service = build("calendar", "v3", credentials=creds)
            logger.info("Calendar service created")
            return service
        except Exception as e:
            logger.error(f"Failed to build Calendar service: {e}")
            return None


    @staticmethod
    def get_service_for_account(credentials_path: Path, token_path: Path):
        """Build a Gmail service for a specific account's credential/token pair.

        Each account has its own credentials.json and token.json under
        Config.EMAIL_CREDS_DIR. The OAuth flow runs per-account on first setup.

        Returns:
            googleapiclient.discovery.Resource for Gmail, or None.
        """
        manager = GoogleAuthManager(
            credentials_path=credentials_path,
            token_path=token_path,
        )
        return manager.get_gmail_service()


# ── CLI entry point for first-time auth ─────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    manager = GoogleAuthManager()
    creds = manager.get_credentials()
    if creds:
        print("Google OAuth setup complete. Token saved.")
        print(f"  Token path: {TOKEN_PATH}")
        print(f"  Scopes: {SCOPES}")
    else:
        print("OAuth setup failed. Check the logs above.")
