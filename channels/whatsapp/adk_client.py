import base64
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

    async def ensure_session(self, user_id: str, session_id: str) -> None:
        """Create session in ADK if it doesn't already exist."""
        url = f"{self.base_url}/apps/{self.app_name}/users/{user_id}/sessions"
        payload = {"session_id": session_id}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, json=payload)
                # 200/201 or 400 (if already exists) are fine
                if res.status_code in (200, 201):
                    logger.info("Session %s created successfully for user %s", session_id, user_id)
        except Exception as e:
            logger.debug("Attempted session creation (%s): %s", session_id, e)

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
        session_id = f"{self.user_prefix}{phone_number}"

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

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(run_url, json=run_payload)

            # If session not found (404), create session and retry
            if response.status_code == 404:
                logger.info("Session %s not found on runner, initializing...", session_id)
                await self.ensure_session(user_id, session_id)
                response = await client.post(run_url, json=run_payload)

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
