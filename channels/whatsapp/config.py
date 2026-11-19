import os
from pathlib import Path
from dotenv import load_dotenv

# Search and load .env files in order of precedence:
# 1. channels/whatsapp/.env
# 2. channels/.env
# 3. agents/chat-assistant/.env
# 4. root .env
current_dir = Path(__file__).resolve().parent
search_paths = [
    current_dir / ".env",
    current_dir.parent / ".env",
    current_dir.parent.parent / "agents" / "chat-assistant" / ".env",
    current_dir.parent.parent / ".env",
]
for env_path in search_paths:
    if env_path.exists():
        load_dotenv(env_path, override=False)


class Settings:
    # Meta / WhatsApp Cloud API credentials
    WHATSAPP_TOKEN: str = os.getenv("WHATSAPP_TOKEN") or os.getenv("WHATSAPP_ACCESS_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    WHATSAPP_VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
    WHATSAPP_APP_SECRET: str = os.getenv("WHATSAPP_APP_SECRET", "")
    WHATSAPP_API_VERSION: str = os.getenv("WHATSAPP_API_VERSION", "v25.0")

    @property
    def formatted_api_version(self) -> str:
        ver = self.WHATSAPP_API_VERSION.strip()
        if not ver.startswith("v"):
            ver = f"v{ver}"
        if "." not in ver:
            ver = f"{ver}.0"
        return ver

    # ADK Agent Server Configuration
    ADK_API_URL: str = (
        os.getenv("ADK_API_URL")
        or os.getenv("AGENT_RUNTIME_API_URL")
        or "http://localhost:8000"
    ).rstrip("/")
    ADK_APP_NAME: str = os.getenv("ADK_APP_NAME", "chat_assistant")
    ADK_USER_PREFIX: str = os.getenv("ADK_USER_PREFIX", "wa_")

    # Optional GCP service account credentials for remote agent runtime
    GCP_SA_KEY_JSON: str = os.getenv("GCP_SA_KEY_JSON", "")


settings = Settings()
