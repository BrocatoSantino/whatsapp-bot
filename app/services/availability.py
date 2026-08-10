from datetime import date, time, datetime, timedelta
from sqlalchemy.orm import Session
from app.models import Appointment, Service
from app.config import BUSINESS_DAYS, BUSINESS_HOURS_START, BUSINESS_HOURS_END, SLOT_DURATION_MINUTES

def get_available_dates(days_ahead: int = 7) -> list[date]:
    """Retorna los próximos días hábiles basándose en BUSINESS_DAYS."""
    available_dates = []
    current_date = date.today()
    
    while len(available_dates) < days_ahead:
        if current_date.weekday() in BUSINESS_DAYS:
            available_dates.append(current_date)
        current_date += timedelta(days=1)
        
    return available_dates

def get_available_slots(db: Session, target_date: date, service_id: int) -> list[time]:
    """
    Obtiene los horarios disponibles para un servicio en una fecha específica.
    """
    # Obtiene duración del servicio de la DB
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        return []
    
    duration = service.duration_minutes
    
    # Obtiene turnos existentes (no cancelados) para ese día
    appointments = db.query(Appointment).filter(
        Appointment.date == target_date,
        Appointment.status != 'cancelled'
    ).all()
    
    # Calcula slots ocupados
    occupied_slots = set()
    for apt in appointments:
        apt_service = db.query(Service).filter(Service.id == apt.service_id).first()
        if apt_service:
            apt_duration = apt_service.duration_minutes
            start_datetime = datetime.combine(target_date, apt.time)
            end_datetime = start_datetime + timedelta(minutes=apt_duration)
            
            # Marcar todos los bloques de SLOT_DURATION_MINUTES ocupados
            current = start_datetime
            while current < end_datetime:
                occupied_slots.add(current.time())
                current += timedelta(minutes=SLOT_DURATION_MINUTES)
    
    # Genera todos los slots posibles
    available_slots = []
    start_datetime = datetime.combine(target_date, time(BUSINESS_HOURS_START, 0))
    end_datetime = datetime.combine(target_date, time(BUSINESS_HOURS_END, 0))
    
    current = start_datetime
    now = datetime.now()
    
    while current + timedelta(minutes=duration) <= end_datetime:
        # Si es hoy, no muestra horarios pasados
        if target_date == now.date() and current <= now:
            current += timedelta(minutes=SLOT_DURATION_MINUTES)
            continue
            
        # Verifica si los slots necesarios para la duración del servicio están libres
        is_free = True
        check_time = current
        end_check = current + timedelta(minutes=duration)
        
        while check_time < end_check:
            if check_time.time() in occupied_slots:
                is_free = False
                break
            check_time += timedelta(minutes=SLOT_DURATION_MINUTES)
            
        if is_free:
            available_slots.append(current.time())
            
        current += timedelta(minutes=SLOT_DURATION_MINUTES)
        
    return available_slots
