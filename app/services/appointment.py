from datetime import date, time, datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.models import Client, Appointment, Service
from app.services.availability import get_available_slots

def get_or_create_client(db: Session, phone: str, name: str, tenant_id: int) -> Client:
    """Busca un cliente por teléfono y tenant, lo crea si no existe. Actualiza el nombre si cambió."""
    client = db.query(Client).filter(Client.phone == phone, Client.tenant_id == tenant_id).first()
    if not client:
        client = Client(phone=phone, name=name, tenant_id=tenant_id)
        db.add(client)
        db.commit()
        db.refresh(client)
    elif name and client.name != name:
        client.name = name
        db.commit()
        db.refresh(client)
    return client

def create_appointment(db: Session, phone: str, name: str, service_id: int, apt_date: date, apt_time: time, tenant_id: int, status: str = "confirmed") -> Appointment | None:
    """Crea un nuevo turno para el cliente de un tenant específico."""
    service = db.query(Service).filter(Service.id == service_id, Service.tenant_id == tenant_id).first()
    if not service:
        return None
        
    # Doble chequeo de concurrencia: verificar si el turno sigue disponible
    available_slots = get_available_slots(db, apt_date, service_id, tenant_id)
    if apt_time not in available_slots:
        return None
        
    client = get_or_create_client(db, phone, name, tenant_id)
    
    appointment = Appointment(
        tenant_id=tenant_id,
        client_id=client.id,
        service_id=service_id,
        date=apt_date,
        time=apt_time,
        status=status
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment

def get_client_appointments(db: Session, phone: str, tenant_id: int) -> list[Appointment]:
    """Obtiene los turnos futuros confirmados de un cliente para un tenant específico."""
    client = db.query(Client).filter(Client.phone == phone, Client.tenant_id == tenant_id).first()
    if not client:
        return []
        
    ar_tz = timezone(timedelta(hours=-3))
    today = datetime.now(ar_tz).date()
    return db.query(Appointment).filter(
        Appointment.tenant_id == tenant_id,
        Appointment.client_id == client.id,
        Appointment.status == "confirmed",
        Appointment.date >= today
    ).order_by(Appointment.date, Appointment.time).all()

def cancel_appointment(db: Session, appointment_id: int, phone: str, tenant_id: int) -> bool:
    """Cancela un turno si pertenece al cliente y al tenant."""
    client = db.query(Client).filter(Client.phone == phone, Client.tenant_id == tenant_id).first()
    if not client:
        return False
        
    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.tenant_id == tenant_id,
        Appointment.client_id == client.id
    ).first()
    
    if appointment and appointment.status != "cancelled":
        appointment.status = "cancelled"
        db.commit()
        return True
    return False

def get_appointments_by_date(db: Session, target_date: date, tenant_id: int) -> list[Appointment]:
    """Obtiene todos los turnos para una fecha específica de un tenant."""
    return db.query(Appointment).filter(
        Appointment.tenant_id == tenant_id,
        Appointment.date == target_date
    ).order_by(Appointment.time).all()

def get_all_services(db: Session, tenant_id: int) -> list[Service]:
    """Obtiene todos los servicios activos de un tenant."""
    return db.query(Service).filter(Service.tenant_id == tenant_id, Service.active == True).all()
