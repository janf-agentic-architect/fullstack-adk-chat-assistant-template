import base64
import json
import logging
from typing import Any, List, Optional
import httpx

from .config import settings

logger = logging.getLogger("whatsapp.adk_client")


class AdkAgentClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        app_name: Optional[str] = None,
        user_prefix: Optional[str] = None,
    ):
        self.base_url = (base_url or settings.ADK_API_URL).rstrip("/")
        self.app_name = app_name or settings.ADK_APP_NAME
        self.user_prefix = user_prefix or settings.ADK_USER_PREFIX
        self._credentials = None
        self._user_sessions: dict[str, str] = {}

    def _get_auth_headers(self) -> dict[str, str]:
        """Obtain authorization headers for Google Cloud if calling Agent Runtime."""
        headers: dict[str, str] = {}
        # Only inject Bearer token if connecting to Google Cloud / Vertex AI Agent Runtime
        if "googleapis.com" in self.base_url or settings.GCP_SA_KEY_JSON:
            try:
                import google.auth
                from google.auth.transport.requests import Request

                if self._credentials is None:
                    if settings.GCP_SA_KEY_JSON:
                        from google.oauth2 import service_account
                        sa_info = json.loads(settings.GCP_SA_KEY_JSON)
                        self._credentials = service_account.Credentials.from_service_account_info(
                            sa_info,
                            scopes=["https://www.googleapis.com/auth/cloud-platform"],
                        )
                    else:
                        # Uses Cloud Run Application Default Credentials (ADC)
                        self._credentials, _ = google.auth.default(
                            scopes=["https://www.googleapis.com/auth/cloud-platform"]
                        )

                if not self._credentials.valid:
                    self._credentials.refresh(Request())

                if self._credentials.token:
                    headers["Authorization"] = f"Bearer {self._credentials.token}"
            except Exception as e:
                logger.warning("Could not obtain GCP OAuth2 token for Agent Runtime: %s", e)
        return headers

    async def get_or_create_session(self, user_id: str) -> str:
        """Get an existing session or create a new session for user."""
        if user_id in self._user_sessions:
            return self._user_sessions[user_id]

        headers = self._get_auth_headers()
        url = f"{self.base_url}/apps/{self.app_name}/users/{user_id}/sessions"

        # Try to find existing session first
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, headers=headers)
                if res.status_code == 200:
                    sessions = res.json()
                    if isinstance(sessions, list) and sessions:
                        latest = sessions[-1]
                        session_id = latest.get("id")
                        if session_id:
                            self._user_sessions[user_id] = str(session_id)
                            logger.info("Found existing session %s for user %s", session_id, user_id)
                            return str(session_id)
        except Exception as e:
            logger.debug("Failed to list sessions for user %s: %s", user_id, e)

        # Create new session
        return await self.create_session(user_id)

    async def create_session(self, user_id: str) -> str:
        """Create a new session in ADK."""
        headers = self._get_auth_headers()
        url = f"{self.base_url}/apps/{self.app_name}/users/{user_id}/sessions"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, json={}, headers=headers)
                if res.status_code in (200, 201):
                    data = res.json()
                    session_id = str(data.get("id") or "")
                    if session_id:
                        self._user_sessions[user_id] = session_id
                        logger.info("Created new session %s for user %s", session_id, user_id)
                        return session_id
        except Exception as e:
            logger.error("Failed to create session for user %s: %s", user_id, e)

        # Fallback
        fallback_id = f"{self.user_prefix}{user_id}"
        self._user_sessions[user_id] = fallback_id
        return fallback_id

    async def ensure_session(self, user_id: str, session_id: str) -> None:
        """Create session in ADK if it doesn't already exist."""
        await self.get_or_create_session(user_id)

    def build_multimodal_message(
        self,
        text: Optional[str] = None,
        media_bytes: Optional[bytes] = None,
        mime_type: Optional[str] = None,
    ) -> dict[str, Any]:
        """Build ADK types.Content compatible dictionary for multimodal input."""
        parts: List[dict[str, Any]] = []

        if text and text.strip():
            parts.append({"text": text.strip()})

        if media_bytes and mime_type:
            # Clean mime-type: e.g. "audio/ogg; codecs=opus" -> "audio/ogg"
            clean_mime = mime_type.split(";")[0].strip()
            # If WhatsApp sends voice as audio/ogg with opus, clean to audio/ogg
            b64_data = base64.b64encode(media_bytes).decode("utf-8")
            parts.append({
                "inline_data": {
                    "mime_type": clean_mime,
                    "data": b64_data,
                }
            })

        if not parts:
            parts.append({"text": "Hello"})

        return {
            "role": "user",
            "parts": parts,
        }

    async def send_message(
        self,
        phone_number: str,
        text: Optional[str] = None,
        media_bytes: Optional[bytes] = None,
        mime_type: Optional[str] = None,
    ) -> str:
        """Send multimodal message to the ADK Agent and return the response text."""
        user_id = f"{self.user_prefix}{phone_number}"
        session_id = await self.get_or_create_session(user_id)

        new_message = self.build_multimodal_message(
            text=text,
            media_bytes=media_bytes,
            mime_type=mime_type,
        )

        run_payload = {
            "app_name": self.app_name,
            "user_id": user_id,
            "session_id": session_id,
            "new_message": new_message,
        }

        run_url = f"{self.base_url}/run"
        headers = self._get_auth_headers()

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(run_url, json=run_payload, headers=headers)

            # If session not found or expired (404), create fresh session and retry
            if response.status_code == 404:
                logger.info("Session %s not found on runner, recreating...", session_id)
                session_id = await self.create_session(user_id)
                run_payload["session_id"] = session_id
                response = await client.post(run_url, json=run_payload, headers=headers)

            if response.status_code >= 400:
                logger.error("ADK Agent error: %d %s", response.status_code, response.text)
                return "Disculpa, ha ocurrido un error al procesar tu solicitud con el asistente."

            events = response.json()
            return self._extract_response_text(events)

    def _extract_response_text(self, events: List[dict[str, Any]]) -> str:
        """Extract final text message from ADK returned events."""
        text_parts: List[str] = []

        for event in events:
            # Check content parts
            content = event.get("content") or {}
            parts = content.get("parts") or []
            for part in parts:
                # Exclude internal reasoning/thought parts
                if part.get("thought"):
                    continue
                text = part.get("text")
                if text:
                    text_parts.append(text)

        if not text_parts:
            # If no text was accumulated, check if there was any message attribute
            for event in reversed(events):
                msg = event.get("message")
                if msg and isinstance(msg, str):
                    return msg
            return "Listo."

        return "".join(text_parts).strip()
