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
from app.models import Tenant

ar_tz = datetime.timezone(datetime.timedelta(hours=-3))

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Estado de conversaciones en memoria
# ---------------------------------------------------------------------------
conversations: dict[tuple[int, str], dict] = {}

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

def get_conversation(tenant_id: int, phone: str) -> dict:
    now = datetime.datetime.now(ar_tz).replace(tzinfo=None)
    key = (tenant_id, phone)
    if key in conversations:
        conv = conversations[key]
        # Timeout de 10 minutos sin actividad
        if now - conv["last_activity"] > datetime.timedelta(minutes=10):
            reset_conversation(tenant_id, phone)
    if key not in conversations:
        conversations[key] = {
            "state": "IDLE",
            "data": {},
            "last_activity": now
        }
    conversations[key]["last_activity"] = now
    return conversations[key]

def update_conversation(tenant_id: int, phone: str, state: str, data: dict = None):
    key = (tenant_id, phone)
    if key in conversations:
        conversations[key]["state"] = state
        if data is not None:
            conversations[key]["data"] = data
        conversations[key]["last_activity"] = datetime.datetime.now(ar_tz).replace(tzinfo=None)

def reset_conversation(tenant_id: int, phone: str):
    key = (tenant_id, phone)
    if key in conversations:
        conversations[key]["state"] = "IDLE"
        conversations[key]["data"] = {}
        conversations[key]["last_activity"] = datetime.datetime.now(ar_tz).replace(tzinfo=None)

# ---------------------------------------------------------------------------
# Handler principal
# ---------------------------------------------------------------------------

async def handle_message(phone: str, name: str, message: str, message_id: str, db: Session, tenant: Tenant):
    try:
        msg = message.strip().lower()

        # --- Manejo de audios/imágenes ---
        if msg == "unsupported_media":
            await send_message(phone, "Lo siento, soy un bot y todavía no sé escuchar audios ni ver fotos 😅\nPor favor, escribime por texto o escribí *menu*.", tenant.wa_phone_number_id, tenant.wa_access_token)
            return

        # --- Hablar con humano (funciona desde cualquier estado) ---
        if msg in HUMAN_KEYWORDS:
            await _handle_human_handoff(phone, name, tenant)
            return

        # --- Volver al menú (funciona desde cualquier estado) ---
        if msg in MENU_KEYWORDS:
            reset_conversation(tenant.id, phone)

        # --- Acciones directas (botones de recordatorio / cancelar flujo) ---
        if msg == "cancel_flow" or msg == "cancelar reserva":
            await send_message(phone, "🚫 Reserva cancelada. Escribí *menu* si necesitás algo más.", tenant.wa_phone_number_id, tenant.wa_access_token)
            reset_conversation(tenant.id, phone)
            return

        if msg.startswith("confirm_apt_"):
            await send_message(phone, "✅ ¡Genial! Te esperamos mañana. ¡Gracias por confirmar! 💈", tenant.wa_phone_number_id, tenant.wa_access_token)
            reset_conversation(tenant.id, phone)
            return

        if msg.startswith("cancel_apt_"):
            try:
                apt_id = int(msg.split("_")[2])
                success = cancel_appointment(db, apt_id, phone, tenant.id)
                if success:
                    await send_message(phone, "❌ Turno cancelado correctamente. ¡Gracias por avisar!", tenant.wa_phone_number_id, tenant.wa_access_token)
                else:
                    await send_message(phone, "No pudimos cancelar el turno 😕 Escribí *menu*.", tenant.wa_phone_number_id, tenant.wa_access_token)
            except Exception:
                pass
            reset_conversation(tenant.id, phone)
            return

        if msg.startswith("reschedule_apt_"):
            try:
                apt_id = int(msg.split("_")[2])
                success = cancel_appointment(db, apt_id, phone, tenant.id)
                if success:
                    await send_message(phone, "🔄 Ok, cancelamos el de mañana. Vamos a reprogramarlo:", tenant.wa_phone_number_id, tenant.wa_access_token)
                    update_conversation(tenant.id, phone, "MENU")
                    await _handle_menu(phone, "sacar_turno", get_conversation(tenant.id, phone), db, tenant)
                    return
                else:
                    await send_message(phone, "No pudimos reprogramar el turno 😕 Escribí *menu*.", tenant.wa_phone_number_id, tenant.wa_access_token)
            except Exception:
                pass
            reset_conversation(tenant.id, phone)
            return

        conv = get_conversation(tenant.id, phone)
        state = conv["state"]

        get_or_create_client(db, phone, name, tenant.id)

        if state == "IDLE":
            # Aceptar acciones directas desde botones de confirmación previos
            if msg in ("sacar_turno", "1"):
                update_conversation(tenant.id, phone, "MENU")
                await _handle_menu(phone, msg, get_conversation(tenant.id, phone), db, tenant)
            elif msg in ("mis_turnos", "2"):
                update_conversation(tenant.id, phone, "MENU")
                await _handle_menu(phone, msg, get_conversation(tenant.id, phone), db, tenant)
            elif msg in ("cancelar_turno", "cancelar", "3"):
                update_conversation(tenant.id, phone, "MENU")
                await _handle_menu(phone, msg, get_conversation(tenant.id, phone), db, tenant)
            else:
                await _handle_idle(phone, name, db, tenant)

        elif state == "MENU":
            await _handle_menu(phone, msg, conv, db, tenant)
        elif state == "CHOOSING_DATE":
            await _handle_choosing_date(phone, msg, conv, db, tenant)
        elif state == "CHOOSING_TIME":
            await _handle_choosing_time(phone, name, msg, conv, db, tenant)
        elif state == "CANCEL_CHOOSING":
            await _handle_cancel(phone, msg, conv, db, tenant)
        else:
            reset_conversation(tenant.id, phone)
            await _handle_idle(phone, name, db, tenant)

    except Exception as e:
        logger.error(f"Error handling message for {phone}: {e}")
        try:
            await send_message(phone, "❌ ¡Ups! Hubo un error. Escribí *menu* para volver a empezar.", tenant.wa_phone_number_id, tenant.wa_access_token)
        except Exception:
            logger.error(f"No se pudo enviar mensaje de error a {phone}")
        reset_conversation(tenant.id, phone)

# ---------------------------------------------------------------------------
# IDLE → Mostrar menú con botones
# ---------------------------------------------------------------------------

async def _handle_idle(phone: str, name: str, db: Session, tenant: Tenant):
    greeting = f"¡Hola {name}!" if name else "¡Hola!"
    contact_msg = f"\n📞 Si necesitás contactar a un humano, podés hablar al: {tenant.owner_phone}\n" if tenant.owner_phone else ""
    body = (f"💈 {greeting} Soy el asistente de *{tenant.name}*{contact_msg}\n"
            f"¿Qué necesitás?")
    buttons = [
        {"id": "sacar_turno", "title": "📅 Sacar turno"},
        {"id": "mis_turnos", "title": "📋 Mis turnos"},
        {"id": "cancelar_turno", "title": "❌ Cancelar turno"},
    ]
    await send_reply_buttons(phone, body, buttons, tenant.wa_phone_number_id, tenant.wa_access_token)
    update_conversation(tenant.id, phone, "MENU")

# ---------------------------------------------------------------------------
# MENU → Elegir acción
# ---------------------------------------------------------------------------

async def _handle_menu(phone: str, message: str, conv: dict, db: Session, tenant: Tenant):

    # ---- SACAR TURNO ----
    if message in ("sacar_turno", "1"):
        services = get_all_services(db, tenant.id)
        if not services:
            await send_message(phone, "No hay servicios disponibles ahora mismo 😕\nEscribí *menu* para volver.", tenant.wa_phone_number_id, tenant.wa_access_token)
            reset_conversation(tenant.id, phone)
            return

        # Seleccionar automáticamente el primer servicio (Corte)
        default_service = services[0]
        service_id = default_service.id
        service_name = default_service.name
        price_fmt = f"${default_service.price:,.0f}".replace(",", ".")

        # Mostrar fechas disponibles
        dates = get_available_dates(db, tenant.id, days_ahead=7)
        if not dates:
            await send_message(phone, "No hay fechas disponibles en los próximos días 😕\nEscribí *menu* para volver.", tenant.wa_phone_number_id, tenant.wa_access_token)
            reset_conversation(tenant.id, phone)
            return

        today = datetime.datetime.now(ar_tz).date()
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

        rows.append({
            "id": "cancel_flow",
            "title": "⬅️ Volver"
        })

        sections = [{"title": "Días disponibles", "rows": rows}]
        await send_list(
            phone,
            f"✂️ Valor del corte: *{price_fmt}*\n\n📅 ¿Qué día te queda bien?",
            "Ver días",
            sections,
            tenant.wa_phone_number_id,
            tenant.wa_access_token
        )

        data = {
            "service_id": service_id,
            "service_name": service_name,
            "service_price": price_fmt,
            "dates": dates_data,
        }
        update_conversation(tenant.id, phone, "CHOOSING_DATE", data)

    # ---- MIS TURNOS ----
    elif message in ("mis_turnos", "2"):
        appointments = get_client_appointments(db, phone, tenant.id)
        if not appointments:
            await send_message(phone, "No tenés turnos agendados 📭\n\n_Escribí *menu* para volver._", tenant.wa_phone_number_id, tenant.wa_access_token)
        else:
            lines = ["📅 *Tus próximos turnos:*\n"]
            for apt in appointments:
                lines.append(f"• {format_date(apt.date)} a las {format_time(apt.time)} - {apt.service.name}")
            lines.append("\n_Escribí *menu* para volver._")
            await send_message(phone, "\n".join(lines), tenant.wa_phone_number_id, tenant.wa_access_token)
        reset_conversation(tenant.id, phone)

    # ---- CANCELAR ----
    elif message in ("cancelar_turno", "cancelar", "3"):
        appointments = get_client_appointments(db, phone, tenant.id)
        if not appointments:
            await send_message(phone, "No tenés turnos para cancelar 📭\n\n_Escribí *menu* para volver._", tenant.wa_phone_number_id, tenant.wa_access_token)
            reset_conversation(tenant.id, phone)
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
        await send_list(phone, "❌ *¿Cuál turno querés cancelar?*", "Ver turnos", sections, tenant.wa_phone_number_id, tenant.wa_access_token)
        update_conversation(tenant.id, phone, "CANCEL_CHOOSING", {"appointments": cancel_data})

    else:
        await send_message(phone, "No entendí 🤔 Tocá un botón o escribí *menu* para ver las opciones.", tenant.wa_phone_number_id, tenant.wa_access_token)

# ---------------------------------------------------------------------------
# CHOOSING_DATE → Elegir día
# ---------------------------------------------------------------------------

async def _handle_choosing_date(phone: str, message: str, conv: dict, db: Session, tenant: Tenant):
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
        await send_message(phone, "No entendí 🤔 Elegí un día de la lista o escribí *menu* para volver.", tenant.wa_phone_number_id, tenant.wa_access_token)
        return

    chosen_date = datetime.date.fromisoformat(chosen_date_iso)
    service_id = conv["data"]["service_id"]

    slots = get_available_slots(db, chosen_date, service_id, tenant.id)
    if not slots:
        await send_message(phone,
            f"No hay horarios disponibles para el {format_date(chosen_date)} 😕\n"
            f"Elegí otro día o escribí *menu* para volver.", tenant.wa_phone_number_id, tenant.wa_access_token)
        return

    # Armar texto con los horarios disponibles
    slots_data = []
    msg_lines = [f"🕐 *Horarios para el {format_date(chosen_date)}*\n"]
    
    for t in slots:
        msg_lines.append(f"• {format_time(t)}")
        slots_data.append(t.isoformat())

    msg_lines.append("\n📝 _Escribí la hora que querés (ej: 16:30 o 16)_")

    buttons = [{"id": "cancel_flow", "title": "⬅️ Volver"}]
    await send_reply_buttons(phone, "\n".join(msg_lines), buttons, tenant.wa_phone_number_id, tenant.wa_access_token)

    data = conv["data"].copy()
    data.update({
        "chosen_date": chosen_date_iso,
        "slots": slots_data
    })
    update_conversation(tenant.id, phone, "CHOOSING_TIME", data)

# ---------------------------------------------------------------------------
# CHOOSING_TIME → Elegir horario (lista interactiva O texto libre)
# ---------------------------------------------------------------------------

async def _handle_choosing_time(phone: str, name: str, message: str, conv: dict, db: Session, tenant: Tenant):
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
                    f"Elegí uno de la lista o escribí otra hora.", tenant.wa_phone_number_id, tenant.wa_access_token)
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
        await send_message(phone, "No entendí la hora 🤔\nElegí de la lista o escribí la hora (ej: _16:30_ o _16_)", tenant.wa_phone_number_id, tenant.wa_access_token)
        return

    # --- Crear el turno ---
    chosen_date = datetime.date.fromisoformat(conv["data"]["chosen_date"])
    service_id = conv["data"]["service_id"]
    service_name = conv["data"]["service_name"]
    service_price = conv["data"].get("service_price", "")

    appointment = create_appointment(db, phone, name, service_id, chosen_date, chosen_time, tenant.id)

    if appointment:
        price_line = f"\n💰 {service_price}" if service_price else ""
        msg = (f"✅ *¡Listo, turno confirmado!*\n\n"
               f"📅 {format_date(chosen_date)}\n"
               f"🕐 {format_time(chosen_time)}\n"
               f"✂️ {service_name}{price_line}\n\n"
               f"Te esperamos en *{tenant.name}* 💈")

        buttons = [
            {"id": "sacar_turno", "title": "📅 Sacar otro"},
            {"id": "mis_turnos", "title": "📋 Mis turnos"},
        ]
        await send_reply_buttons(phone, msg, buttons, tenant.wa_phone_number_id, tenant.wa_access_token)
        
        if tenant.owner_phone:
            client_name = name if name else "Un cliente"
            owner_msg = (
                f"🔔 *Nuevo Turno Reservado*\n\n"
                f"👤 Cliente: {client_name} ({phone})\n"
                f"📅 Fecha: {format_date(chosen_date)}\n"
                f"🕐 Hora: {format_time(chosen_time)}\n"
                f"✂️ Servicio: {service_name}"
            )
            try:
                await send_message(tenant.owner_phone, owner_msg, tenant.wa_phone_number_id, tenant.wa_access_token)
            except Exception as e:
                logger.error(f"No se pudo notificar al dueño del nuevo turno: {e}")
                
        reset_conversation(tenant.id, phone)
    else:
        await send_message(phone, "Ups, ese horario ya no está disponible 😕\nEscribí *menu* para intentar de nuevo.", tenant.wa_phone_number_id, tenant.wa_access_token)
        reset_conversation(tenant.id, phone)

# ---------------------------------------------------------------------------
# CANCEL_CHOOSING → Cancelar un turno
# ---------------------------------------------------------------------------

async def _handle_cancel(phone: str, message: str, conv: dict, db: Session, tenant: Tenant):
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
        await send_message(phone, "No entendí 🤔 Elegí un turno de la lista o escribí *menu* para volver.", tenant.wa_phone_number_id, tenant.wa_access_token)
        return

    success = cancel_appointment(db, apt_id, phone, tenant.id)

    if success:
        buttons = [
            {"id": "sacar_turno", "title": "📅 Sacar turno"},
            {"id": "mis_turnos", "title": "📋 Mis turnos"},
        ]
        await send_reply_buttons(phone, "❌ Turno cancelado.\n\n¿Querés hacer algo más?", buttons, tenant.wa_phone_number_id, tenant.wa_access_token)
    else:
        await send_message(phone, "No se pudo cancelar el turno 😕\nEscribí *menu* para volver.", tenant.wa_phone_number_id, tenant.wa_access_token)

    reset_conversation(tenant.id, phone)

# ---------------------------------------------------------------------------
# HUMAN HANDOFF → Avisar al dueño
# ---------------------------------------------------------------------------

async def _handle_human_handoff(phone: str, name: str, tenant: Tenant):
    await send_message(phone, "👤 ¡Dale! Le aviso al equipo que querés hablar.\nTe van a contestar a la brevedad 🙌", tenant.wa_phone_number_id, tenant.wa_access_token)

    if tenant.owner_phone:
        try:
            client_name = name if name else "Un cliente"
            await send_message(
                tenant.owner_phone,
                f"🔔 *Atención*\n\n{client_name} (tel: {phone}) quiere hablar con vos desde el bot de WhatsApp.",
                tenant.wa_phone_number_id,
                tenant.wa_access_token
            )
        except Exception as e:
            logger.error(f"No se pudo notificar al dueño: {e}")

    reset_conversation(tenant.id, phone)
