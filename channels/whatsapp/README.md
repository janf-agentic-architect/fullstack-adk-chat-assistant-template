# Canal WhatsApp Cloud API (Multimodal) para Google ADK

Este microservicio conecta **WhatsApp Cloud API (Meta)** con el asistente conversacional basado en **Google Agent Development Kit (ADK)**, permitiendo a los usuarios interactuar a través de WhatsApp mediante:

- 💬 **Texto**: Conversación estándar por chat.
- 🖼️ **Imágenes**: Fotos y capturas con análisis visual de Gemini (con o sin pie de foto/caption).
- 🎙️ **Notas de voz y Audios**: Transcripción y comprensión auditiva nativa (`audio/ogg`, `audio/mp4`, `audio/mpeg`, etc.).
- 📄 **Documentos**: Documentos compatibles procesados como entrada multimodal.

---

## 🏗️ Arquitectura y Flujo

```
                    ┌─────────────────────────┐
                    │    WhatsApp Client      │
                    │   (iOS / Android / Web) │
                    └────────────┬────────────┘
                                 │
                                 ▼
                     Meta WhatsApp Cloud API
                                 │
                 Webhook POST    │
                 (JSON Payload)  ▼
                    ┌─────────────────────────┐
                    │  channels/whatsapp      │
                    │  (FastAPI Microservice) │
                    │                         │
                    │  1. Responde 200 OK     │
                    │  2. Descarga Media      │
                    │     (Meta Graph API)    │
                    │  3. Formatea Multimodal │
                    │     (Base64 inline_data)│
                    └────────────┬────────────┘
                                 │
                                 ▼ HTTP POST /run (ADK API Server)
                    ┌─────────────────────────┐
                    │ Google ADK Agent Server │
                    │ (chat_assistant/Gemini) │
                    └────────────┬────────────┘
                                 │
                                 ▼ Respuesta texto
                    ┌─────────────────────────┐
                    │ WhatsApp Cloud API      │
                    │ POST /messages          │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │    WhatsApp Client      │
                    └─────────────────────────┘
```

1. **Meta Webhook Handshake**: Implementa el endpoint `GET /webhook` validando `hub.verify_token` y devolviendo el challenge exigido por Meta.
2. **Recepción Asíncrona Inmediata**: Al recibir un `POST /webhook`, responde de inmediato con `HTTP 200 OK` y procesa la descarga de medios e inferencia en `BackgroundTasks` para evitar timeouts o reintentos de Meta.
3. **Descarga de Medios**: Si el mensaje contiene imagen o audio, obtiene la URL de descarga autenticada desde Graph API y descarga los bytes.
4. **Conversión a ADK Multimodal**: Transforma los datos binarios en objetos `types.Content` de ADK (`{"inline_data": {"mime_type": "...", "data": "<base64>"}}`).
5. **Sesiones Persistentes**: Mapea automáticamente el número de teléfono del usuario a una sesión de ADK (`wa_{phone_number}`), manteniendo el contexto de la conversación.

---

## ⚙️ Requisitos Previos

1. Cuenta de desarrollador en [Meta for Developers](https://developers.facebook.com/).
2. Una aplicación de WhatsApp Cloud API configurada en Meta con:
   - **Access Token** temporal o permanente (System User).
   - **Phone Number ID**.
   - Un **Verify Token** configurado a tu elección.
3. El servidor de ADK corriendo (por defecto en `http://localhost:8000`).

---

## 🚀 Puesta en Marcha

### 1. Instalar Dependencias
Desde la raíz o dentro del directorio `channels`:

```bash
cd channels
uv sync
```

### 2. Configurar Variables de Entorno
Copia el archivo de ejemplo a `.env` (puede estar en la raíz del proyecto o en `channels/.env`):

```bash
cp channels/whatsapp/.env.example channels/whatsapp/.env
```

Edita `channels/whatsapp/.env`:
```env
WHATSAPP_TOKEN=EAAG...
WHATSAPP_PHONE_NUMBER_ID=123456789012345
WHATSAPP_VERIFY_TOKEN=mi_token_secreto_adk
WHATSAPP_APP_SECRET=opcional_para_verificacion_sha256

ADK_API_URL=http://localhost:8000
ADK_APP_NAME=chat_assistant
```

### 3. Iniciar los Servicios

**Terminal 1: Iniciar el backend de ADK**
```bash
# Desde la raíz del proyecto:
uv run adk api_server
```

**Terminal 2: Iniciar el canal de WhatsApp**
```bash
# Desde el directorio channels:
cd channels
uv run uvicorn whatsapp.main:app --host 0.0.0.0 --port 8001 --reload
```

---

## 🌐 Configuración del Webhook en Meta

Meta requiere una URL pública con HTTPS. Para desarrollo local, puedes usar **ngrok** o **cloudflared**:

```bash
ngrok http 8001
```

En el panel de **Meta for Developers**:
1. Dirígete a **WhatsApp** > **Configuración** > **Webhook**.
2. Haz clic en **Editar**.
3. **URL de devolución de llamada**: `https://tu-dominio-ngrok.app/webhook` (también se admiten `/webhooks/whatsapp`, `/webhook/whatsapp` o `/whatsapp/webhook`).
4. **Identificador de verificación (Verify Token)**: El mismo valor que pusiste en `WHATSAPP_VERIFY_TOKEN`.
5. Haz clic en **Verificar y guardar**.
6. En los campos de suscripción de Webhook, activa **`messages`**.

---

## 🧪 Pruebas Locales (Curl)

### Probar Handshake de Verificación (GET):
```bash
curl -X GET "http://localhost:8001/webhook?hub.mode=subscribe&hub.verify_token=mi_token_secreto_adk&hub.challenge=1158201444"
```
Debe responder con `1158201444` y código 200.

### Probar Mensaje de Texto (POST Simulado):
```bash
curl -X POST "http://localhost:8001/webhook" \
  -H "Content-Type: application/json" \
  -d '{
    "object": "whatsapp_business_account",
    "entry": [{
      "id": "12345",
      "changes": [{
        "value": {
          "messaging_product": "whatsapp",
          "metadata": {"display_phone_number": "123456", "phone_number_id": "123456789012345"},
          "contacts": [{"wa_id": "5215512345678", "profile": {"name": "Usuario"}}],
          "messages": [{
            "from": "5215512345678",
            "id": "wamid.HBgL...",
            "timestamp": "1700000000",
            "type": "text",
            "text": {"body": "Hola, ¿cómo estás?"}
          }]
        },
        "field": "messages"
      }]
    }]
  }'
```
Debe responder inmediatamente `{"status": "ok"}` con código 200.
