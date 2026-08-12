import datetime
import logging
from sqlalchemy.orm import Session
from app.models import Appointment
from app.database import SessionLocal
from app.whatsapp.client import send_reply_buttons
from app.whatsapp.conversation import DIAS, MESES

logger = logging.getLogger(__name__)

def format_date(d: datetime.date) -> str:
    return f"{DIAS[d.weekday()]} {d.day} {MESES[d.month - 1]}"

def format_time(t: datetime.time) -> str:
    return t.strftime("%H:%M")

async def send_tomorrow_reminders():
    db = SessionLocal()
    try:
        ar_tz = datetime.timezone(datetime.timedelta(hours=-3))
        now = datetime.datetime.now(ar_tz)
        tomorrow = now.date() + datetime.timedelta(days=1)
        
        # Buscar TODOS los turnos de mañana (ya que Vercel Hobby solo permite cron diario)
        appointments = db.query(Appointment).filter(
            Appointment.date == tomorrow,
            Appointment.status != 'cancelled'
        ).all()
        
        logger.info(f"Enviando {len(appointments)} recordatorios para {tomorrow}")
        
        for apt in appointments:
            if not apt.client or not apt.client.phone:
                continue
                
            service_name = apt.service.name if apt.service else "tu turno"
            phone = apt.client.phone
            
            body = (f"⏰ *Recordatorio de puerto.barberr*\n\n"
                    f"¡Hola! Te recordamos tu turno para mañana:\n"
                    f"📅 {format_date(apt.date)}\n"
                    f"🕐 {format_time(apt.time)}\n"
                    f"✂️ {service_name}\n\n"
                    f"Por favor confirmá si venís, o reprogramalo si no llegás.")
            
            buttons = [
                {"id": f"confirm_apt_{apt.id}", "title": "✅ Confirmo"},
                {"id": f"reschedule_apt_{apt.id}", "title": "🔄 Cambiar hora"},
                {"id": f"cancel_apt_{apt.id}", "title": "❌ Cancelar"}
            ]
            
            try:
                await send_reply_buttons(phone, body, buttons)
                logger.info(f"Recordatorio enviado a {phone} para turno {apt.id}")
            except Exception as e:
                logger.error(f"Error enviando recordatorio a {phone}: {e}")
                
    except Exception as e:
        logger.error(f"Error general en send_tomorrow_reminders: {e}")
    finally:
        db.close()
