import httpx

async def send_message(phone: str, text: str, phone_number_id: str, access_token: str):
    api_url = f"https://graph.facebook.com/v21.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone,
        "type": "text",
        "text": {"preview_url": False, "body": text}
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(api_url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()

async def send_reply_buttons(phone: str, body: str, buttons: list[dict], phone_number_id: str, access_token: str):
    api_url = f"https://graph.facebook.com/v21.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
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
        response = await client.post(api_url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()

async def send_list(phone: str, body: str, button_text: str, sections: list[dict], phone_number_id: str, access_token: str):
    api_url = f"https://graph.facebook.com/v21.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
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
        response = await client.post(api_url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()

async def send_template_message(
    phone: str,
    template_name: str,
    language_code: str,
    components: list[dict],
    phone_number_id: str,
    access_token: str
):
    """
    Envía un mensaje de plantilla aprobada por Meta.
    Los components son el mapeo de variables para header, body, etc.
    """
    api_url = f"https://graph.facebook.com/v21.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {
                "code": language_code
            },
            "components": components
        }
    }
    
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(api_url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
