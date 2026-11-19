import hashlib
import hmac
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import PlainTextResponse

from .config import settings
from .models import WhatsAppWebhookPayload
from .service import WhatsAppService

logger = logging.getLogger("whatsapp.router")

router = APIRouter(prefix="", tags=["whatsapp"])
service = WhatsAppService()


def verify_signature(raw_body: bytes, signature_header: Optional[str]) -> bool:
    """Verify X-Hub-Signature-256 header using WHATSAPP_APP_SECRET."""
    secret = (settings.WHATSAPP_APP_SECRET or "").strip()
    if not secret or secret.startswith("opcional") or "placeholder" in secret.lower():
        # If secret is not set or is a placeholder, skip signature check
        return True

    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected_sig = signature_header.split("sha256=")[1]
    computed_sig = hmac.new(
        key=secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed_sig, expected_sig)


@router.get("/webhook")
@router.get("/webhooks")
@router.get("/webhooks/whatsapp")
@router.get("/webhook/whatsapp")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """WhatsApp Cloud API Webhook verification endpoint (GET handshake)."""
    logger.info("Webhook verification request: mode=%s, token=%s", hub_mode, hub_verify_token)

    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("Webhook verified successfully.")
        return PlainTextResponse(content=hub_challenge, status_code=status.HTTP_200_OK)

    logger.warning("Webhook verification failed: invalid token or mode")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification token mismatch")


@router.post("/webhook")
@router.post("/webhooks")
@router.post("/webhooks/whatsapp")
@router.post("/webhook/whatsapp")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
):
    """WhatsApp Cloud API incoming messages and events endpoint."""
    raw_body = await request.body()

    if not verify_signature(raw_body, x_hub_signature_256):
        logger.warning("Invalid payload signature received from Meta webhook.")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")

    try:
        json_data = await request.json()
        payload = WhatsAppWebhookPayload.model_validate(json_data)
    except Exception as e:
        logger.warning("Could not parse payload as standard WhatsAppWebhookPayload: %s", e)
        # Always return 200 to WhatsApp to avoid repeated retries
        return {"status": "ignored"}

    # Extract all incoming messages from payload
    for entry in payload.entry:
        for change in entry.changes:
            if change.field == "messages" and change.value.messages:
                for message in change.value.messages:
                    # Enqueue background processing so HTTP response returns immediately (<3s)
                    background_tasks.add_task(service.process_incoming_message, message)

    return {"status": "ok"}
