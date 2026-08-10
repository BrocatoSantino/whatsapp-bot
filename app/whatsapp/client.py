import httpx
from app.config import WA_PHONE_NUMBER_ID, WA_ACCESS_TOKEN

API_URL = f"https://graph.facebook.com/v21.0/{WA_PHONE_NUMBER_ID}/messages"
HEADERS = {
    "Authorization": f"Bearer {WA_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}

async def send_message(phone: str, text: str):
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone,
        "type": "text",
        "text": {"preview_url": False, "body": text}
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(API_URL, json=payload, headers=HEADERS)
        response.raise_for_status()
        return response.json()

async def send_reply_buttons(phone: str, body: str, buttons: list[dict]):
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body},
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {
                            "id": str(btn["id"]),
                            "title": str(btn["title"])
                        }
                    }
                    for btn in buttons[:3]
                ]
            }
        }
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(API_URL, json=payload, headers=HEADERS)
        response.raise_for_status()
        return response.json()

async def send_list(phone: str, body: str, button_text: str, sections: list[dict]):
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": body},
            "action": {
                "button": button_text,
                "sections": sections
            }
        }
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(API_URL, json=payload, headers=HEADERS)
        response.raise_for_status()
        return response.json()
