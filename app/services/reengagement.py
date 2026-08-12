import datetime
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import Appointment, Client
from app.database import SessionLocal
from app.whatsapp.client import send_reply_buttons

logger = logging.getLogger(__name__)

async def send_reengagement_messages():
    db = SessionLocal()
    try:
        # Calcular fecha límite: hace 30 días
        ar_tz = datetime.timezone(datetime.timedelta(hours=-3))
        thirty_days_ago = datetime.datetime.now(ar_tz).date() - datetime.timedelta(days=30)
        
        # Encontrar clientes cuyo ÚLTIMO turno (sin importar estado) fue hace 30 días exactos.
        # Esto evita mandar el mensaje todos los días después de los 30 días.
        
        # Subquery: la fecha del último turno de cada cliente
        subquery = db.query(
            Appointment.client_id,
            func.max(Appointment.date).label('last_apt_date')
        ).group_by(Appointment.client_id).subquery()
        
        # Buscar clientes donde su last_apt_date sea exactamente hace 30 días
        clients_to_reengage = db.query(Client).join(
            subquery, Client.id == subquery.c.client_id
        ).filter(
            subquery.c.last_apt_date == thirty_days_ago
        ).all()
        
        logger.info(f"Enviando mensajes de reactivación a {len(clients_to_reengage)} clientes (último turno: {thirty_days_ago})")
        
        for client in clients_to_reengage:
            if not client.phone:
                continue
                
            name = client.name if client.name else "campeón"
            
            body = (f"👋 ¡Ey {name}! Hace rato que no te vemos por *puerto.barberr* 💈\n\n"
                    f"Ya pasaron algunas semanas desde tu último corte. ¿Querés ir separando un lugar para estos días?")
            
            buttons = [
                {"id": "sacar_turno", "title": "📅 Sacar turno"},
                {"id": "mis_turnos", "title": "👍 No por ahora"}
            ]
            
            try:
                await send_reply_buttons(client.phone, body, buttons)
                logger.info(f"Mensaje de reactivación enviado a {client.phone}")
            except Exception as e:
                logger.error(f"Error enviando reactivación a {client.phone}: {e}")
                
    except Exception as e:
        logger.error(f"Error general en send_reengagement_messages: {e}")
    finally:
        db.close()
