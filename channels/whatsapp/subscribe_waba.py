import asyncio
import sys
import httpx
from .config import settings

async def subscribe_waba():
    waba_id = settings.WHATSAPP_BUSINESS_ACCOUNT_ID.strip()
    token = settings.WHATSAPP_TOKEN.strip()
    api_version = settings.formatted_api_version

    if not waba_id:
        print("❌ Error: WHATSAPP_BUSINESS_ACCOUNT_ID no está configurado en channels/whatsapp/.env")
        sys.exit(1)

    if not token:
        print("❌ Error: WHATSAPP_TOKEN no está configurado en channels/whatsapp/.env")
        sys.exit(1)

    url = f"https://graph.facebook.com/{api_version}/{waba_id}/subscribed_apps"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    print(f"Subscribing WABA ID '{waba_id}' to Meta App via {api_version}...")
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, headers=headers)
        if resp.status_code == 200:
            print("✓ ¡Suscripción exitosa!")
            print(f"Respuesta de Meta: {resp.text}")
        else:
            print(f"❌ Error al suscribir (status={resp.status_code}): {resp.text}")
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(subscribe_waba())
