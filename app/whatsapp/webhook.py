import hmac
import hashlib
import json
import logging
from fastapi import APIRouter, Request, HTTPException, Query, BackgroundTasks
from app.config import WA_VERIFY_TOKEN, WA_APP_SECRET
from app.database import SessionLocal
from app.whatsapp.conversation import handle_message

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge")
):
    if hub_mode == "subscribe" and hub_verify_token == WA_VERIFY_TOKEN:
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")

@router.post("/webhook")
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    body_bytes = await request.body()
    
    if WA_APP_SECRET:
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not signature.startswith("sha256="):
            raise HTTPException(status_code=403, detail="Invalid signature")
        
        expected_sig = hmac.new(
            WA_APP_SECRET.encode("utf-8"),
            body_bytes,
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(f"sha256={expected_sig}", signature):
            raise HTTPException(status_code=403, detail="Invalid signature")
            
    try:
        body_json = json.loads(body_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
        
    msg_data = parse_message(body_json)
    if msg_data:
        background_tasks.add_task(
            process_message,
            msg_data["phone"],
            msg_data["name"],
            msg_data["text"],
            msg_data["message_id"]
        )
        
    return {"status": "ok"}

def parse_message(body: dict) -> dict | None:
    try:
        entry = body.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        
        if "messages" not in value:
            return None
            
        message = value["messages"][0]
        contact = value.get("contacts", [{}])[0]
        
        phone = message.get("from")
        # ARGENTINA BUG FIX: Meta test numbers strip the '9', but real messages include it.
        # We strip the '9' here so the bot can reply successfully in test mode.
        if phone and phone.startswith("549") and len(phone) == 13:
            phone = "54" + phone[3:]
            
        name = contact.get("profile", {}).get("name", "")
        message_id = message.get("id")
        
        msg_type = message.get("type")
        text = ""
        
        if msg_type == "text":
            text = message.get("text", {}).get("body", "")
        elif msg_type == "interactive":
            interactive = message.get("interactive", {})
            int_type = interactive.get("type")
            if int_type == "button_reply":
                text = interactive.get("button_reply", {}).get("title", "")
            elif int_type == "list_reply":
                text = interactive.get("list_reply", {}).get("title", "")
                
        if phone and text:
            return {
                "phone": phone,
                "name": name,
                "text": text,
                "message_id": message_id
            }
    except (IndexError, KeyError, TypeError):
        pass
    return None

async def process_message(phone: str, name: str, text: str, message_id: str):
    db = SessionLocal()
    try:
        await handle_message(phone, name, text, message_id, db)
    except Exception as e:
        logger.error(f"Error processing message for {phone}: {e}")
    finally:
        db.close()
