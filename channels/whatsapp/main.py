import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .router import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("whatsapp.main")

app = FastAPI(
    title="ADK WhatsApp Channel",
    description="WhatsApp Cloud API Multimodal Gateway for Google ADK Chat Assistant",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include webhook router (available at /webhook and /whatsapp/webhook)
app.include_router(router)
app.include_router(router, prefix="/whatsapp")


@app.get("/health")
async def health_check():
    """Healthcheck endpoint."""
    return {
        "status": "ok",
        "channel": "whatsapp",
        "adk_api_url": settings.ADK_API_URL,
        "adk_app_name": settings.ADK_APP_NAME,
        "whatsapp_configured": bool(settings.WHATSAPP_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID),
    }


def main():
    import uvicorn
    uvicorn.run("channels.whatsapp.main:app", host="0.0.0.0", port=8081, reload=True)


if __name__ == "__main__":
    main()
