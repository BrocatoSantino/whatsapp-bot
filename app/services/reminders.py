import datetime
import logging
from sqlalchemy.orm import Session
from app.models import Appointment
from app.database import SessionLocal
from app.whatsapp.client import send_template_message
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
            if not apt.client or not apt.client.phone or not apt.tenant:
                continue
                
            service_name = apt.service.name if apt.service else "Corte de pelo"
            phone = apt.client.phone
            tenant = apt.tenant
            
            components = [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": format_date(apt.date)},
                        {"type": "text", "text": format_time(apt.time)},
                        {"type": "text", "text": service_name}
                    ]
                }
            ]
            
            try:
                await send_template_message(
                    phone=phone,
                    template_name="recordatorio_turno",
                    language_code="es_AR",
                    components=components,
                    phone_number_id=tenant.wa_phone_number_id,
                    access_token=tenant.wa_access_token
                )
                logger.info(f"Recordatorio con plantilla enviado a {phone} para turno {apt.id} ({tenant.name})")
            except Exception as e:
                logger.error(f"Error enviando recordatorio con plantilla a {phone}: {e}")
                
    except Exception as e:
        logger.error(f"Error general en send_tomorrow_reminders: {e}")
    finally:
        db.close()
