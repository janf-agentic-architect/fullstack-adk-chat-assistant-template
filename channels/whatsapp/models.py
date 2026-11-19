from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class TextMessage(BaseModel):
    body: str


class MediaItem(BaseModel):
    id: str
    mime_type: Optional[str] = None
    sha256: Optional[str] = None
    caption: Optional[str] = None
    filename: Optional[str] = None


class IncomingMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(..., alias="from")
    id: str
    timestamp: str
    type: str  # "text", "image", "audio", "voice", "document", etc.
    text: Optional[TextMessage] = None
    image: Optional[MediaItem] = None
    audio: Optional[MediaItem] = None
    voice: Optional[MediaItem] = None
    document: Optional[MediaItem] = None


class Profile(BaseModel):
    name: Optional[str] = None


class Contact(BaseModel):
    profile: Optional[Profile] = None
    wa_id: str


class Metadata(BaseModel):
    display_phone_number: Optional[str] = None
    phone_number_id: Optional[str] = None


class Value(BaseModel):
    messaging_product: str
    metadata: Metadata
    contacts: Optional[List[Contact]] = None
    messages: Optional[List[IncomingMessage]] = None
    statuses: Optional[List[dict[str, Any]]] = None


class Change(BaseModel):
    field: str
    value: Value


class Entry(BaseModel):
    id: str
    changes: List[Change]


class WhatsAppWebhookPayload(BaseModel):
    object: str
    entry: List[Entry]
