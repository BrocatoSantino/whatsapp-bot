import re
import datetime
import logging
from sqlalchemy.orm import Session
from app.whatsapp.client import send_message, send_reply_buttons, send_list
from app.services.appointment import (
    get_or_create_client,
    create_appointment,
    get_client_appointments,
    cancel_appointment,
    get_all_services
)
from app.services.availability import get_available_dates, get_available_slots
from app.config import OWNER_PHONE, BUSINESS_NAME

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Estado de conversaciones en memoria
# ---------------------------------------------------------------------------
conversations: dict[str, dict] = {}

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

HUMAN_KEYWORDS = {'humano', 'persona', 'hablar', 'ayuda', 'recepcion', 'dueño', 'encargado'}
MENU_KEYWORDS = {'menu', 'menú', 'hola', 'inicio', 'volver', 'empezar'}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def format_date(d: datetime.date) -> str:
    return f"{DIAS[d.weekday()]} {d.day} {MESES[d.month - 1]}"

def format_time(t: datetime.time) -> str:
    return t.strftime("%H:%M")

def parse_user_time(text: str) -> datetime.time | None:
    """Interpreta texto libre del usuario como un horario.
    Soporta: '16', '16:30', '16.30', 'a las 16 hs', etc."""
    text = text.strip().lower()
    text = re.sub(r'\b(a las|hs|horas|hrs|h)\b', '', text).strip()

    # HH:MM o HH.MM
    match = re.match(r'^(\d{1,2})[:\.](\d{2})$', text)
    if match:
        h, m = int(match.group(1)), int(match.group(2))
        if 0 <= h <= 23 and 0 <= m <= 59:
            return datetime.time(h, m)

    # Solo HH
    match = re.match(r'^(\d{1,2})$', text)
    if match:
        h = int(match.group(1))
        if 0 <= h <= 23:
            return datetime.time(h, 0)

    return None

# ---------------------------------------------------------------------------
# Gestión de estado
# ---------------------------------------------------------------------------

def get_conversation(phone: str) -> dict:
    now = datetime.datetime.now()
    if phone in conversations:
        conv = conversations[phone]
        # Timeout de 10 minutos sin actividad
        if now - conv["last_activity"] > datetime.timedelta(minutes=10):
            reset_conversation(phone)
    if phone not in conversations:
        conversations[phone] = {
            "state": "IDLE",
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
        conversations[phone]["state"] = "IDLE"
        conversations[phone]["data"] = {}
        conversations[phone]["last_activity"] = datetime.datetime.now()

# ---------------------------------------------------------------------------
# Handler principal
# ---------------------------------------------------------------------------

async def handle_message(phone: str, name: str, message: str, message_id: str, db: Session):
    try:
        msg = message.strip().lower()

        # --- Hablar con humano (funciona desde cualquier estado) ---
        if msg in HUMAN_KEYWORDS:
            await _handle_human_handoff(phone, name)
            return

        # --- Volver al menú (funciona desde cualquier estado) ---
        if msg in MENU_KEYWORDS:
            reset_conversation(phone)

        conv = get_conversation(phone)
        state = conv["state"]

        get_or_create_client(db, phone, name)

        if state == "IDLE":
            # Aceptar acciones directas desde botones de confirmación previos
            if msg in ("sacar_turno", "1"):
                update_conversation(phone, "MENU")
                await _handle_menu(phone, msg, get_conversation(phone), db)
            elif msg in ("mis_turnos", "2"):
                update_conversation(phone, "MENU")
                await _handle_menu(phone, msg, get_conversation(phone), db)
            elif msg in ("cancelar_turno", "cancelar", "3"):
                update_conversation(phone, "MENU")
                await _handle_menu(phone, msg, get_conversation(phone), db)
            else:
                await _handle_idle(phone, name, db)

        elif state == "MENU":
            await _handle_menu(phone, msg, conv, db)
        elif state == "CHOOSING_SERVICE":
            await _handle_choosing_service(phone, msg, conv, db)
        elif state == "CHOOSING_DATE":
            await _handle_choosing_date(phone, msg, conv, db)
        elif state == "CHOOSING_TIME":
            await _handle_choosing_time(phone, name, msg, conv, db)
        elif state == "CANCEL_CHOOSING":
            await _handle_cancel(phone, msg, conv, db)
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

# ---------------------------------------------------------------------------
# IDLE → Mostrar menú con botones
# ---------------------------------------------------------------------------

async def _handle_idle(phone: str, name: str, db: Session):
    greeting = f"¡Hola {name}!" if name else "¡Hola!"
    body = (f"💈 {greeting} Soy el asistente de *{BUSINESS_NAME}*\n\n"
            f"¿Qué necesitás?")
    buttons = [
        {"id": "sacar_turno", "title": "📅 Sacar turno"},
        {"id": "mis_turnos", "title": "📋 Mis turnos"},
        {"id": "cancelar_turno", "title": "❌ Cancelar"},
    ]
    await send_reply_buttons(phone, body, buttons)
    update_conversation(phone, "MENU")

# ---------------------------------------------------------------------------
# MENU → Elegir acción
# ---------------------------------------------------------------------------

async def _handle_menu(phone: str, message: str, conv: dict, db: Session):

    # ---- SACAR TURNO ----
    if message in ("sacar_turno", "1"):
        services = get_all_services(db)
        if not services:
            await send_message(phone, "No hay servicios disponibles ahora mismo 😕\nEscribí *menu* para volver.")
            reset_conversation(phone)
            return

        rows = []
        services_data = []
        for s in services:
            price_fmt = f"${s.price:,.0f}".replace(",", ".")
            rows.append({
                "id": f"service_{s.id}",
                "title": s.name,
                "description": f"{price_fmt} - {s.duration_minutes} min"
            })
            services_data.append((s.id, s.name, price_fmt))

        sections = [{"title": "Servicios", "rows": rows}]
        await send_list(phone, "✂️ ¿Qué servicio te hacés?", "Ver servicios", sections)
        update_conversation(phone, "CHOOSING_SERVICE", {"services": services_data})

    # ---- MIS TURNOS ----
    elif message in ("mis_turnos", "2"):
        appointments = get_client_appointments(db, phone)
        if not appointments:
            await send_message(phone, "No tenés turnos agendados 📭\n\n_Escribí *menu* para volver._")
        else:
            lines = ["📅 *Tus próximos turnos:*\n"]
            for apt in appointments:
                lines.append(f"• {format_date(apt.date)} a las {format_time(apt.time)} - {apt.service.name}")
            lines.append("\n_Escribí *menu* para volver._")
            await send_message(phone, "\n".join(lines))
        reset_conversation(phone)

    # ---- CANCELAR ----
    elif message in ("cancelar_turno", "cancelar", "3"):
        appointments = get_client_appointments(db, phone)
        if not appointments:
            await send_message(phone, "No tenés turnos para cancelar 📭\n\n_Escribí *menu* para volver._")
            reset_conversation(phone)
            return

        rows = []
        cancel_data = []
        for apt in appointments:
            title = f"{apt.date.day} {MESES[apt.date.month - 1]} - {format_time(apt.time)}"
            rows.append({
                "id": f"apt_{apt.id}",
                "title": title,
                "description": apt.service.name if apt.service else ""
            })
            cancel_data.append(apt.id)

        sections = [{"title": "Tus turnos", "rows": rows}]
        await send_list(phone, "❌ *¿Cuál turno querés cancelar?*", "Ver turnos", sections)
        update_conversation(phone, "CANCEL_CHOOSING", {"appointments": cancel_data})

    else:
        await send_message(phone, "No entendí 🤔 Tocá un botón o escribí *menu* para ver las opciones.")

# ---------------------------------------------------------------------------
# CHOOSING_SERVICE → Elegir servicio
# ---------------------------------------------------------------------------

async def _handle_choosing_service(phone: str, message: str, conv: dict, db: Session):
    services = conv["data"].get("services", [])
    service_id = None
    service_name = None
    service_price = None

    # Intentar por ID interactivo (service_X)
    if message.startswith("service_"):
        try:
            sid = int(message.split("_")[1])
            for s_id, s_name, s_price in services:
                if s_id == sid:
                    service_id, service_name, service_price = s_id, s_name, s_price
                    break
        except (ValueError, IndexError):
            pass

    # Fallback: por número de posición
    if service_id is None:
        try:
            idx = int(message) - 1
            if 0 <= idx < len(services):
                service_id, service_name, service_price = services[idx]
        except ValueError:
            pass

    if service_id is None:
        await send_message(phone, "No entendí 🤔 Elegí un servicio de la lista o escribí *menu* para volver.")
        return

    # Mostrar fechas disponibles
    dates = get_available_dates(days_ahead=7)
    if not dates:
        await send_message(phone, "No hay fechas disponibles en los próximos días 😕\nEscribí *menu* para volver.")
        reset_conversation(phone)
        return

    today = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)

    rows = []
    dates_data = []
    for d in dates:
        if d == today:
            title = "Hoy"
        elif d == tomorrow:
            title = "Mañana"
        else:
            title = format_date(d)

        rows.append({
            "id": f"date_{d.isoformat()}",
            "title": title,
            "description": f"{d.day}/{d.month}/{d.year}"
        })
        dates_data.append(d.isoformat())

    sections = [{"title": "Días disponibles", "rows": rows}]
    await send_list(
        phone,
        f"Elegiste *{service_name}* ✂️\n\n📅 ¿Qué día te queda bien?",
        "Ver días",
        sections
    )

    data = {
        "service_id": service_id,
        "service_name": service_name,
        "service_price": service_price,
        "dates": dates_data,
        "services": services,
    }
    update_conversation(phone, "CHOOSING_DATE", data)

# ---------------------------------------------------------------------------
# CHOOSING_DATE → Elegir día
# ---------------------------------------------------------------------------

async def _handle_choosing_date(phone: str, message: str, conv: dict, db: Session):
    dates_data = conv["data"].get("dates", [])
    chosen_date_iso = None

    # Intentar por ID interactivo (date_YYYY-MM-DD)
    if message.startswith("date_"):
        date_str = message[5:]
        if date_str in dates_data:
            chosen_date_iso = date_str

    # Fallback: por número de posición
    if chosen_date_iso is None:
        try:
            idx = int(message) - 1
            if 0 <= idx < len(dates_data):
                chosen_date_iso = dates_data[idx]
        except ValueError:
            pass

    if chosen_date_iso is None:
        await send_message(phone, "No entendí 🤔 Elegí un día de la lista o escribí *menu* para volver.")
        return

    chosen_date = datetime.date.fromisoformat(chosen_date_iso)
    service_id = conv["data"]["service_id"]

    slots = get_available_slots(db, chosen_date, service_id)
    if not slots:
        await send_message(phone,
            f"No hay horarios disponibles para el {format_date(chosen_date)} 😕\n"
            f"Elegí otro día o escribí *menu* para volver.")
        return

    # Armar filas de horarios
    rows = []
    slots_data = []
    for t in slots:
        time_str = format_time(t)
        rows.append({"id": f"time_{time_str}", "title": time_str})
        slots_data.append(t.isoformat())

    # Dividir en secciones si hay más de 10 horarios
    if len(rows) <= 10:
        sections = [{"title": "Horarios", "rows": rows}]
    else:
        morning = [r for r in rows if int(r["title"].split(":")[0]) < 13]
        afternoon = [r for r in rows if int(r["title"].split(":")[0]) >= 13]
        sections = []
        if morning:
            sections.append({"title": "☀️ Mañana", "rows": morning[:10]})
        if afternoon:
            sections.append({"title": "🌆 Tarde", "rows": afternoon[:10]})

    body = (f"🕐 Horarios para el *{format_date(chosen_date)}*\n\n"
            f"Tocá el botón para elegir, o escribí la hora directamente (ej: _16:30_)")

    await send_list(phone, body, "Ver horarios", sections)

    data = conv["data"].copy()
    data.update({
        "chosen_date": chosen_date_iso,
        "slots": slots_data
    })
    update_conversation(phone, "CHOOSING_TIME", data)

# ---------------------------------------------------------------------------
# CHOOSING_TIME → Elegir horario (lista interactiva O texto libre)
# ---------------------------------------------------------------------------

async def _handle_choosing_time(phone: str, name: str, message: str, conv: dict, db: Session):
    slots_data = conv["data"].get("slots", [])
    chosen_time = None

    # 1) Intentar por ID interactivo (time_HH:MM)
    if message.startswith("time_"):
        time_str = message[5:]
        for slot_iso in slots_data:
            slot_time = datetime.time.fromisoformat(slot_iso)
            if format_time(slot_time) == time_str:
                chosen_time = slot_time
                break

    # 2) Intentar parsear texto libre (ej: "16:30", "16", "a las 16 hs")
    if chosen_time is None:
        parsed = parse_user_time(message)
        if parsed:
            for slot_iso in slots_data:
                slot_time = datetime.time.fromisoformat(slot_iso)
                if slot_time.hour == parsed.hour and slot_time.minute == parsed.minute:
                    chosen_time = slot_time
                    break
            if chosen_time is None:
                await send_message(phone,
                    f"El horario {format_time(parsed)} no está disponible 😕\n"
                    f"Elegí uno de la lista o escribí otra hora.")
                return

    # 3) Fallback: por número de posición
    if chosen_time is None:
        try:
            idx = int(message) - 1
            if 0 <= idx < len(slots_data):
                chosen_time = datetime.time.fromisoformat(slots_data[idx])
        except ValueError:
            pass

    if chosen_time is None:
        await send_message(phone, "No entendí la hora 🤔\nElegí de la lista o escribí la hora (ej: _16:30_ o _16_)")
        return

    # --- Crear el turno ---
    chosen_date = datetime.date.fromisoformat(conv["data"]["chosen_date"])
    service_id = conv["data"]["service_id"]
    service_name = conv["data"]["service_name"]
    service_price = conv["data"].get("service_price", "")

    appointment = create_appointment(db, phone, name, service_id, chosen_date, chosen_time)

    if appointment:
        price_line = f"\n💰 {service_price}" if service_price else ""
        msg = (f"✅ *¡Listo, turno confirmado!*\n\n"
               f"📅 {format_date(chosen_date)}\n"
               f"🕐 {format_time(chosen_time)}\n"
               f"✂️ {service_name}{price_line}\n\n"
               f"Te esperamos en *{BUSINESS_NAME}* 💈")

        buttons = [
            {"id": "sacar_turno", "title": "📅 Sacar otro"},
            {"id": "mis_turnos", "title": "📋 Mis turnos"},
        ]
        await send_reply_buttons(phone, msg, buttons)
        reset_conversation(phone)
    else:
        await send_message(phone, "Ups, ese horario ya no está disponible 😕\nEscribí *menu* para intentar de nuevo.")
        reset_conversation(phone)

# ---------------------------------------------------------------------------
# CANCEL_CHOOSING → Cancelar un turno
# ---------------------------------------------------------------------------

async def _handle_cancel(phone: str, message: str, conv: dict, db: Session):
    appointments_ids = conv["data"].get("appointments", [])
    apt_id = None

    # Intentar por ID interactivo (apt_X)
    if message.startswith("apt_"):
        try:
            cid = int(message.split("_")[1])
            if cid in appointments_ids:
                apt_id = cid
        except (ValueError, IndexError):
            pass

    # Fallback: por número de posición
    if apt_id is None:
        try:
            idx = int(message) - 1
            if 0 <= idx < len(appointments_ids):
                apt_id = appointments_ids[idx]
        except ValueError:
            pass

    if apt_id is None:
        await send_message(phone, "No entendí 🤔 Elegí un turno de la lista o escribí *menu* para volver.")
        return

    success = cancel_appointment(db, apt_id, phone)

    if success:
        buttons = [
            {"id": "sacar_turno", "title": "📅 Sacar turno"},
            {"id": "mis_turnos", "title": "📋 Mis turnos"},
        ]
        await send_reply_buttons(phone, "❌ Turno cancelado.\n\n¿Querés hacer algo más?", buttons)
    else:
        await send_message(phone, "No se pudo cancelar el turno 😕\nEscribí *menu* para volver.")

    reset_conversation(phone)

# ---------------------------------------------------------------------------
# HUMAN HANDOFF → Avisar al dueño
# ---------------------------------------------------------------------------

async def _handle_human_handoff(phone: str, name: str):
    await send_message(phone, "👤 ¡Dale! Le aviso al equipo que querés hablar.\nTe van a contestar a la brevedad 🙌")

    if OWNER_PHONE:
        try:
            client_name = name if name else "Un cliente"
            await send_message(
                OWNER_PHONE,
                f"🔔 *Atención*\n\n{client_name} (tel: {phone}) quiere hablar con vos desde el bot de WhatsApp."
            )
        except Exception as e:
            logger.error(f"No se pudo notificar al dueño: {e}")

    reset_conversation(phone)
