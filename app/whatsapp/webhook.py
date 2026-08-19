import hmac
import hashlib
import json
import logging
from fastapi import APIRouter, Request, HTTPException, Query, BackgroundTasks
from app.config import WA_VERIFY_TOKEN, WA_APP_SECRET
from app.database import SessionLocal
from app.whatsapp.conversation import handle_message
from app.models import Tenant

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
async def webhook_post(request: Request, background_tasks: BackgroundTasks):
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
        body = json.loads(body_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    # 2. Parse the incoming message
    msg_data = parse_message(body)
    
    if msg_data:
        # Buscar la empresa (Tenant) correspondiente al número que recibió el mensaje
        db = SessionLocal()
        try:
            tenant = db.query(Tenant).filter(Tenant.wa_phone_number_id == msg_data["bot_phone_number_id"]).first()
            if not tenant:
                print(f"Warning: No se encontró un Tenant para el número de bot: {msg_data['bot_phone_number_id']}")
                return {"status": "ignored"}
        finally:
            db.close()

        await process_message(
            msg_data["phone"],
            msg_data["name"],
            msg_data["text"],
            msg_data["message_id"],
            tenant
        )
        
    return {"status": "ok"}

def parse_message(body: dict) -> dict | None:
    try:
        entry = body.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        
        if "messages" not in value:
            return None
            
        bot_phone_number_id = value.get("metadata", {}).get("phone_number_id", "")
            
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
                text = interactive.get("button_reply", {}).get("id", "")
            elif int_type == "list_reply":
                text = interactive.get("list_reply", {}).get("id", "")
        elif msg_type in ["audio", "image", "video", "sticker", "document"]:
            text = "UNSUPPORTED_MEDIA"
                
        if phone and text and bot_phone_number_id:
            return {
                "phone": phone,
                "name": name,
                "text": text,
                "message_id": message_id,
                "bot_phone_number_id": bot_phone_number_id
            }
    except Exception as e:
        print(f"Error parsing message: {e}")
        return None

async def process_message(phone: str, name: str, text: str, message_id: str, tenant: Tenant):
    db = SessionLocal()
    try:
        await handle_message(phone, name, text, message_id, db, tenant)
    except Exception as e:
        logger.error(f"Error processing message for {phone}: {e}")
    finally:
        db.close()

@router.get("/api/cron/reminders")
async def trigger_reminders(background_tasks: BackgroundTasks):
    from app.services.reminders import send_tomorrow_reminders
    background_tasks.add_task(send_tomorrow_reminders)
    return {"status": "reminders_queued"}

@router.get("/api/cron/reengagement")
async def trigger_reengagement(background_tasks: BackgroundTasks):
    from app.services.reengagement import send_reengagement_messages
    background_tasks.add_task(send_reengagement_messages)
    return {"status": "reengagement_queued"}
