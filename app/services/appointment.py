from datetime import date, time
from sqlalchemy.orm import Session
from app.models import Client, Appointment, Service

def get_or_create_client(db: Session, phone: str, name: str = '') -> Client:
    """Busca un cliente por teléfono, lo crea si no existe. Actualiza el nombre si cambió."""
    client = db.query(Client).filter(Client.phone == phone).first()
    if not client:
        client = Client(phone=phone, name=name)
        db.add(client)
        db.commit()
        db.refresh(client)
    elif name and client.name != name:
        client.name = name
        db.commit()
        db.refresh(client)
    return client

def create_appointment(db: Session, phone: str, name: str, service_id: int, apt_date: date, apt_time: time, status: str = "confirmed") -> Appointment | None:
    """Crea un nuevo turno para el cliente."""
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        return None
        
    client = get_or_create_client(db, phone, name)
    
    appointment = Appointment(
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

def get_client_appointments(db: Session, phone: str) -> list[Appointment]:
    """Obtiene los turnos futuros confirmados de un cliente."""
    client = db.query(Client).filter(Client.phone == phone).first()
    if not client:
        return []
        
    today = date.today()
    return db.query(Appointment).filter(
        Appointment.client_id == client.id,
        Appointment.status == "confirmed",
        Appointment.date >= today
    ).order_by(Appointment.date, Appointment.time).all()

def cancel_appointment(db: Session, appointment_id: int, phone: str) -> bool:
    """Cancela un turno si pertenece al cliente."""
    client = db.query(Client).filter(Client.phone == phone).first()
    if not client:
        return False
        
    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.client_id == client.id
    ).first()
    
    if appointment and appointment.status != "cancelled":
        appointment.status = "cancelled"
        db.commit()
        return True
    return False

def get_appointments_by_date(db: Session, target_date: date) -> list[Appointment]:
    """Obtiene todos los turnos para una fecha específica (sin filtrar estado)."""
    return db.query(Appointment).filter(
        Appointment.date == target_date
    ).order_by(Appointment.time).all()

def get_all_services(db: Session) -> list[Service]:
    """Obtiene todos los servicios activos."""
    return db.query(Service).filter(Service.active == True).all()
