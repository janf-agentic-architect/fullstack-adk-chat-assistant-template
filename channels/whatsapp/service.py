import collections
import logging
import time
from typing import Optional

from .adk_client import AdkAgentClient
from .client import WhatsAppCloudApiClient, normalize_phone_number
from .models import IncomingMessage

logger = logging.getLogger("whatsapp.service")


class WhatsAppService:
    def __init__(
        self,
        wa_client: Optional[WhatsAppCloudApiClient] = None,
        adk_client: Optional[AdkAgentClient] = None,
        cache_size: int = 1000,
    ):
        self.wa_client = wa_client or WhatsAppCloudApiClient()
        self.adk_client = adk_client or AdkAgentClient()
        self._processed_messages: collections.OrderedDict[str, float] = collections.OrderedDict()
        self._cache_size = cache_size

    def _is_duplicate(self, message_id: str) -> bool:
        """Check and record message ID to prevent duplicate webhook processing."""
        now = time.time()
        # Clean older than 1 hour if size exceeds
        if message_id in self._processed_messages:
            return True

        self._processed_messages[message_id] = now
        while len(self._processed_messages) > self._cache_size:
            self._processed_messages.popitem(last=False)
        return False

    async def process_incoming_message(self, message: IncomingMessage) -> None:
        """Process an incoming WhatsApp message (text, image, audio, voice)."""
        msg_id = message.id
        from_phone = normalize_phone_number(message.from_)

        if self._is_duplicate(msg_id):
            logger.info("Ignoring duplicate message %s from %s", msg_id, from_phone)
            return

        # Mark message as read
        await self.wa_client.mark_as_read(msg_id)

        try:
            msg_type = message.type
            logger.info("Processing message %s of type '%s' from %s", msg_id, msg_type, from_phone)

            if msg_type == "text" and message.text:
                user_text = message.text.body
                reply = await self.adk_client.send_message(
                    phone_number=from_phone,
                    text=user_text,
                )
                await self.wa_client.send_text_message(to=from_phone, text=reply)

            elif msg_type == "image" and message.image:
                image_item = message.image
                caption = image_item.caption or "Analiza esta imagen."
                media_bytes, mime_type = await self.wa_client.download_media(image_item.id)
                reply = await self.adk_client.send_message(
                    phone_number=from_phone,
                    text=caption,
                    media_bytes=media_bytes,
                    mime_type=image_item.mime_type or mime_type,
                )
                await self.wa_client.send_text_message(to=from_phone, text=reply)

            elif (msg_type in ("audio", "voice")) and (message.audio or message.voice):
                audio_item = message.audio or message.voice
                media_bytes, mime_type = await self.wa_client.download_media(audio_item.id)
                reply = await self.adk_client.send_message(
                    phone_number=from_phone,
                    text="Escucha y responde a este audio/nota de voz.",
                    media_bytes=media_bytes,
                    mime_type=audio_item.mime_type or mime_type,
                )
                await self.wa_client.send_text_message(to=from_phone, text=reply)

            elif msg_type == "document" and message.document:
                doc_item = message.document
                caption = doc_item.caption or f"Documento adjunto: {doc_item.filename or 'archivo'}"
                media_bytes, mime_type = await self.wa_client.download_media(doc_item.id)
                reply = await self.adk_client.send_message(
                    phone_number=from_phone,
                    text=caption,
                    media_bytes=media_bytes,
                    mime_type=doc_item.mime_type or mime_type,
                )
                await self.wa_client.send_text_message(to=from_phone, text=reply)

            else:
                logger.info("Received unhandled message type: %s", msg_type)
                await self.wa_client.send_text_message(
                    to=from_phone,
                    text="Recibí tu mensaje, pero actualmente solo puedo procesar texto, imágenes, audios y documentos.",
                )

        except Exception as e:
            logger.exception("Error processing message %s from %s: %s", msg_id, from_phone, e)
            try:
                await self.wa_client.send_text_message(
                    to=from_phone,
                    text="Ocurrió un error al procesar tu mensaje. Por favor intenta nuevamente.",
                )
            except Exception as notify_err:
                logger.error("Failed to notify user about error: %s", notify_err)
