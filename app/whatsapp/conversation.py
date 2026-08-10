import datetime
import logging
from sqlalchemy.orm import Session
from app.whatsapp.client import send_message
from app.services.appointment import (
    get_or_create_client,
    create_appointment,
    get_client_appointments,
    cancel_appointment,
    get_all_services
)
from app.services.availability import get_available_dates, get_available_slots

logger = logging.getLogger(__name__)

conversations: dict[str, dict] = {}

STATES = {
    "IDLE": "IDLE",
    "MENU": "MENU",
    "CHOOSING_SERVICE": "CHOOSING_SERVICE",
    "CHOOSING_DATE": "CHOOSING_DATE",
    "CHOOSING_TIME": "CHOOSING_TIME",
    "CANCEL_CHOOSING": "CANCEL_CHOOSING",
}

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

def format_date(d: datetime.date) -> str:
    dia_sem = DIAS[d.weekday()]
    mes = MESES[d.month - 1]
    return f"{dia_sem} {d.day} {mes}"

def format_time(t: datetime.time) -> str:
    return t.strftime("%H:%M")

def get_conversation(phone: str) -> dict:
    now = datetime.datetime.now()
    if phone in conversations:
        conv = conversations[phone]
        if now - conv["last_activity"] > datetime.timedelta(minutes=10):
            reset_conversation(phone)
    if phone not in conversations:
        conversations[phone] = {
            "state": STATES["IDLE"],
            "data": {},
            "last_activity": now
        }
    conversations[phone]["last_activity"] = now
    return conversations[phone]

def update_conversation(phone: str, state: str, data: dict = None):
    if phone in conversations:
        conversations[phone]["state"] = state
        if data is not None:
            conversations[phone]["data"] = data
        conversations[phone]["last_activity"] = datetime.datetime.now()

def reset_conversation(phone: str):
    if phone in conversations:
        conversations[phone]["state"] = STATES["IDLE"]
        conversations[phone]["data"] = {}
        conversations[phone]["last_activity"] = datetime.datetime.now()

async def handle_message(phone: str, name: str, message: str, message_id: str, db: Session):
    try:
        msg_lower = message.strip().lower()
        if msg_lower in ['menu', 'hola', 'inicio', 'volver']:
            reset_conversation(phone)
            
        conv = get_conversation(phone)
        state = conv["state"]
        
        get_or_create_client(db, phone, name)
        
        if state == STATES["IDLE"]:
            await _handle_idle(phone, name, db)
        elif state == STATES["MENU"]:
            await _handle_menu(phone, msg_lower, conv, db)
        elif state == STATES["CHOOSING_SERVICE"]:
            await _handle_choosing_service(phone, msg_lower, conv, db)
        elif state == STATES["CHOOSING_DATE"]:
            await _handle_choosing_date(phone, msg_lower, conv, db)
        elif state == STATES["CHOOSING_TIME"]:
            await _handle_choosing_time(phone, name, msg_lower, conv, db)
        elif state == STATES["CANCEL_CHOOSING"]:
            await _handle_cancel(phone, msg_lower, conv, db)
        else:
            reset_conversation(phone)
            await _handle_idle(phone, name, db)
            
    except Exception as e:
        logger.error(f"Error handling message for {phone}: {e}")
        try:
            await send_message(phone, "❌ ¡Ups! Hubo un error. Escribí *menu* para volver a empezar.")
        except Exception:
            logger.error(f"No se pudo enviar mensaje de error a {phone}")
        reset_conversation(phone)

async def _handle_idle(phone: str, name: str, db: Session):
    greeting = f"👋 ¡Hola {name}! " if name else "👋 ¡Hola! "
    msg = (f"{greeting}Soy el bot de *puerto.barberr*\n\n"
           "¿Qué querés hacer?\n\n"
           "1️⃣ Agendar turno\n"
           "2️⃣ Ver mis turnos\n"
           "3️⃣ Cancelar un turno\n\n"
           "📝 _Escribí el número de la opción_")
    await send_message(phone, msg)
    update_conversation(phone, STATES["MENU"])

async def _handle_menu(phone: str, message: str, conv: dict, db: Session):
    if message == "1":
        services = get_all_services(db)
        if not services:
            await send_message(phone, "No hay servicios disponibles en este momento. Escribí *menu* para volver.")
            reset_conversation(phone)
            return
            
        msg_lines = ["✂️ *Elegí un servicio:*\n"]
        services_data = []
        for i, s in enumerate(services, 1):
            price_formatted = f"${s.price:,.0f}".replace(",", ".")
            msg_lines.append(f"{i}️⃣ {s.name} - {price_formatted} ({s.duration_minutes} min)")
            services_data.append((s.id, s.name))
            
        msg_lines.append("\n📝 _Escribí el número de la opción_")
        await send_message(phone, "\n".join(msg_lines))
        
        update_conversation(phone, STATES["CHOOSING_SERVICE"], {"services": services_data})
        
    elif message == "2":
        appointments = get_client_appointments(db, phone)
        if not appointments:
            await send_message(phone, "No tenés turnos agendados.\n\n_Escribí *menu* para volver._")
        else:
            msg_lines = ["📅 *Tus próximos turnos:*\n"]
            for apt in appointments:
                msg_lines.append(f"• {format_date(apt.date)} a las {format_time(apt.time)} - {apt.service.name}")
            msg_lines.append("\n_Escribí *menu* para volver._")
            await send_message(phone, "\n".join(msg_lines))
            
        reset_conversation(phone)
        
    elif message == "3":
        appointments = get_client_appointments(db, phone)
        if not appointments:
            await send_message(phone, "No tenés turnos para cancelar.\n\n_Escribí *menu* para volver._")
            reset_conversation(phone)
            return
            
        msg_lines = ["❌ *Elegí el turno que querés cancelar:*\n"]
        cancel_data = []
        for i, apt in enumerate(appointments, 1):
            msg_lines.append(f"{i}️⃣ {format_date(apt.date)} a las {format_time(apt.time)} - {apt.service.name}")
            cancel_data.append(apt.id)
            
        msg_lines.append(f"\n{len(appointments) + 1}️⃣ Volver al menú principal\n")
        msg_lines.append("📝 _Escribí el número de la opción_")
        
        await send_message(phone, "\n".join(msg_lines))
        update_conversation(phone, STATES["CANCEL_CHOOSING"], {"appointments": cancel_data})
        
    else:
        await send_message(phone, "No entendí, escribí 1, 2 o 3.")

async def _handle_choosing_service(phone: str, message: str, conv: dict, db: Session):
    try:
        idx = int(message) - 1
        services = conv["data"].get("services", [])
        if idx < 0 or idx >= len(services):
            raise ValueError()
    except ValueError:
        await send_message(phone, "Opción inválida. Escribí un número de la lista (o *menu* para cancelar).")
        return
        
    service_id, service_name = services[idx]
    
    dates = get_available_dates(days_ahead=7)
    if not dates:
        await send_message(phone, "No hay fechas disponibles en los próximos días. Escribí *menu* para volver.")
        reset_conversation(phone)
        return
        
    msg_lines = [f"Elegiste *{service_name}*. ¿Qué día preferís?\n"]
    dates_data = []
    
    today = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)
    
    for i, d in enumerate(dates, 1):
        if d == today:
            d_str = "Hoy"
        elif d == tomorrow:
            d_str = "Mañana"
        else:
            d_str = format_date(d)
            
        msg_lines.append(f"{i}️⃣ {d_str}")
        dates_data.append(d.isoformat())
        
    msg_lines.append("\n📝 _Escribí el número de la opción_")
    
    data = conv["data"].copy()
    data.update({
        "service_id": service_id,
        "service_name": service_name,
        "dates": dates_data
    })
    
    await send_message(phone, "\n".join(msg_lines))
    update_conversation(phone, STATES["CHOOSING_DATE"], data)

async def _handle_choosing_date(phone: str, message: str, conv: dict, db: Session):
    try:
        idx = int(message) - 1
        dates_data = conv["data"].get("dates", [])
        if idx < 0 or idx >= len(dates_data):
            raise ValueError()
    except ValueError:
        await send_message(phone, "Opción inválida. Escribí un número de la lista (o *menu* para cancelar).")
        return
        
    chosen_date_iso = dates_data[idx]
    chosen_date = datetime.date.fromisoformat(chosen_date_iso)
    service_id = conv["data"]["service_id"]
    
    slots = get_available_slots(db, chosen_date, service_id)
    if not slots:
        await send_message(phone, "No hay horarios disponibles para ese día. Escribí otro número para elegir otra fecha o *menu* para volver.")
        return
        
    msg_lines = [f"📅 Horarios para el {format_date(chosen_date)}:\n"]
    slots_data = []
    
    for i, t in enumerate(slots, 1):
        msg_lines.append(f"{i}️⃣ {format_time(t)}")
        slots_data.append(t.isoformat())
        
    msg_lines.append("\n📝 _Escribí el número de la opción_")
    
    data = conv["data"].copy()
    data.update({
        "chosen_date": chosen_date_iso,
        "slots": slots_data
    })
    
    await send_message(phone, "\n".join(msg_lines))
    update_conversation(phone, STATES["CHOOSING_TIME"], data)

async def _handle_choosing_time(phone: str, name: str, message: str, conv: dict, db: Session):
    try:
        idx = int(message) - 1
        slots_data = conv["data"].get("slots", [])
        if idx < 0 or idx >= len(slots_data):
            raise ValueError()
    except ValueError:
        await send_message(phone, "Opción inválida. Escribí un número de la lista (o *menu* para cancelar).")
        return
        
    chosen_time_iso = slots_data[idx]
    chosen_time = datetime.time.fromisoformat(chosen_time_iso)
    chosen_date = datetime.date.fromisoformat(conv["data"]["chosen_date"])
    service_id = conv["data"]["service_id"]
    service_name = conv["data"]["service_name"]
    
    appointment = create_appointment(db, phone, name, service_id, chosen_date, chosen_time)
    
    if appointment:
        msg = (f"✅ *¡Turno confirmado!*\n\n"
               f"📅 {format_date(chosen_date)}\n"
               f"🕐 {format_time(chosen_time)}\n"
               f"✂️ {service_name}\n\n"
               f"Te esperamos en *puerto.barberr* 💈\n\n"
               f"_Escribí *menu* en cualquier momento para ver o cancelar tus turnos._")
        await send_message(phone, msg)
        reset_conversation(phone)
    else:
        await send_message(phone, "Ups, parece que el horario ya no está disponible. Escribí *menu* para intentar de nuevo.")
        reset_conversation(phone)

async def _handle_cancel(phone: str, message: str, conv: dict, db: Session):
    appointments = conv["data"].get("appointments", [])
    
    try:
        idx = int(message) - 1
        if idx == len(appointments):
            reset_conversation(phone)
            await _handle_idle(phone, "", db)
            return
        if idx < 0 or idx > len(appointments):
            raise ValueError()
    except ValueError:
        await send_message(phone, "Opción inválida. Escribí un número de la lista.")
        return
        
    apt_id = appointments[idx]
    success = cancel_appointment(db, apt_id, phone)
    
    if success:
        await send_message(phone, "❌ Turno cancelado.\n\n_Escribí *menu* si querés sacar otro._")
    else:
        await send_message(phone, "No se pudo cancelar el turno. Escribí *menu* para volver.")
        
    reset_conversation(phone)
