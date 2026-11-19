import base64
import os
import pytest
from fastapi.testclient import TestClient

# Configure environment before imports
os.environ["WHATSAPP_TOKEN"] = "test_token"
os.environ["WHATSAPP_PHONE_NUMBER_ID"] = "12345"
os.environ["WHATSAPP_VERIFY_TOKEN"] = "secret_verify_token"
os.environ["ADK_API_URL"] = "http://localhost:8000"
os.environ["ADK_APP_NAME"] = "chat_assistant"

from whatsapp.main import app
from whatsapp.adk_client import AdkAgentClient
from whatsapp.client import WhatsAppCloudApiClient, normalize_phone_number


@pytest.fixture
def client():
    return TestClient(app)


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["channel"] == "whatsapp"


def test_webhook_handshake_success(client):
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": "secret_verify_token",
        "hub.challenge": "123456789",
    }
    # Test both /webhook and /webhooks/whatsapp
    response = client.get("/webhook", params=params)
    assert response.status_code == 200
    assert response.text == "123456789"

    response_custom = client.get("/webhooks/whatsapp", params=params)
    assert response_custom.status_code == 200
    assert response_custom.text == "123456789"


def test_webhook_handshake_failure(client):
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": "wrong_token",
        "hub.challenge": "123456789",
    }
    response = client.get("/webhook", params=params)
    assert response.status_code == 403


def test_webhook_post_returns_immediate_200(client):
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "12345",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "123456",
                                "phone_number_id": "12345",
                            },
                            "contacts": [
                                {
                                    "wa_id": "1234567890",
                                    "profile": {"name": "Test User"},
                                }
                            ],
                            "messages": [
                                {
                                    "from": "1234567890",
                                    "id": "wamid.TEST1234",
                                    "timestamp": "1700000000",
                                    "type": "text",
                                    "text": {"body": "Hello ADK"},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }

    response = client.post("/webhook", json=payload)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_adk_client_build_multimodal_message():
    adk_client = AdkAgentClient("http://localhost:8000", "chat_assistant")

    # 1. Text only
    text_content = adk_client.build_multimodal_message(text="Hola")
    assert text_content["role"] == "user"
    assert len(text_content["parts"]) == 1
    assert text_content["parts"][0] == {"text": "Hola"}

    # 2. Text + Image
    fake_img = b"fake_png_data"
    img_content = adk_client.build_multimodal_message(
        text="Mira esto",
        media_bytes=fake_img,
        mime_type="image/jpeg",
    )
    assert len(img_content["parts"]) == 2
    assert {"text": "Mira esto"} in img_content["parts"]
    assert {
        "inline_data": {
            "mime_type": "image/jpeg",
            "data": base64.b64encode(fake_img).decode("utf-8"),
        }
    } in img_content["parts"]

    # 3. Audio with codec stripping
    fake_audio = b"fake_audio_data"
    audio_content = adk_client.build_multimodal_message(
        media_bytes=fake_audio,
        mime_type="audio/ogg; codecs=opus",
    )
    assert len(audio_content["parts"]) == 1
    assert audio_content["parts"][0]["inline_data"]["mime_type"] == "audio/ogg"


@pytest.mark.anyio
async def test_service_multimodal_image_flow(monkeypatch):
    from unittest.mock import AsyncMock
    from whatsapp.service import WhatsAppService
    from whatsapp.client import WhatsAppCloudApiClient
    from whatsapp.models import IncomingMessage, MediaItem

    mock_wa = AsyncMock(spec=WhatsAppCloudApiClient)
    mock_wa.download_media.return_value = (b"fake_image_bytes", "image/png")
    mock_wa.mark_as_read.return_value = True
    mock_wa.send_text_message.return_value = {"messages": [{"id": "res_123"}]}

    mock_adk = AsyncMock(spec=AdkAgentClient)
    mock_adk.send_message.return_value = "Veo una imagen de un gato."

    service = WhatsAppService(mock_wa, mock_adk)

    msg = IncomingMessage(
        from_="5215512345678",
        id="wamid.IMG999",
        timestamp="1700000000",
        type="image",
        image=MediaItem(id="meta_media_id_123", caption="¿Qué hay aquí?"),
    )

    await service.process_incoming_message(msg)

    # Verify flow
    mock_wa.mark_as_read.assert_awaited_once_with("wamid.IMG999")
    mock_wa.download_media.assert_awaited_once_with("meta_media_id_123")
    mock_adk.send_message.assert_awaited_once_with(
        phone_number="525512345678",
        text="¿Qué hay aquí?",
        media_bytes=b"fake_image_bytes",
        mime_type="image/png",
    )
    mock_wa.send_text_message.assert_awaited_once_with(
        to="525512345678",
        text="Veo una imagen de un gato.",
    )


def test_normalize_phone_number_mexico_guadalajara():
    # Guadalajara (33) with extra '1' between 52 and 33
    assert normalize_phone_number("5213312345678") == "523312345678"
    assert normalize_phone_number("+52 1 33 1234 5678") == "523312345678"
    # Already normalized
    assert normalize_phone_number("523312345678") == "523312345678"
    # Other Mexican states (e.g. CDMX 55)
    assert normalize_phone_number("5215512345678") == "525512345678"


def test_whatsapp_client_api_version_v25():
    client_v25 = WhatsAppCloudApiClient(api_version="v25")
    assert client_v25.api_version == "v25.0"
    assert client_v25.base_url == "https://graph.facebook.com/v25.0"

    client_25_raw = WhatsAppCloudApiClient(api_version="25")
    assert client_25_raw.api_version == "v25.0"
    assert client_25_raw.base_url == "https://graph.facebook.com/v25.0"


def test_adk_client_auth_headers_local():
    adk = AdkAgentClient(base_url="http://localhost:8000")
    assert adk._get_auth_headers() == {}


def test_adk_client_auth_headers_remote_with_mock(monkeypatch):
    class MockCredentials:
        valid = True
        token = "test_gcp_bearer_token"

        def refresh(self, request):
            pass

    import google.auth
    monkeypatch.setattr(google.auth, "default", lambda scopes: (MockCredentials(), "test-project"))

    adk = AdkAgentClient(base_url="https://us-east1-aiplatform.googleapis.com/reasoningEngines/v1/projects/123/locations/us-east1/reasoningEngines/456/api")
    headers = adk._get_auth_headers()
    assert headers.get("Authorization") == "Bearer test_gcp_bearer_token"


