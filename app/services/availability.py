from datetime import date, time, datetime, timedelta
from sqlalchemy.orm import Session
from app.models import Appointment, Service
from app.config import BUSINESS_DAYS, BUSINESS_SHIFTS, SLOT_DURATION_MINUTES

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
    Soporta turnos cortados (mañana y tarde).
    """
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        return []
    
    duration = service.duration_minutes
    
    # Obtiene turnos existentes (no cancelados, ni no-show)
    appointments = db.query(Appointment).filter(
        Appointment.date == target_date,
        Appointment.status.in_(['pending', 'completed']) # cancelled y no_show liberan el turno
    ).all()
    
    # Calcula slots ocupados
    occupied_slots = set()
    for apt in appointments:
        apt_service = db.query(Service).filter(Service.id == apt.service_id).first()
        if apt_service:
            apt_duration = apt_service.duration_minutes
            start_datetime = datetime.combine(target_date, apt.time)
            end_datetime = start_datetime + timedelta(minutes=apt_duration)
            
            current = start_datetime
            while current < end_datetime:
                occupied_slots.add(current.time())
                current += timedelta(minutes=SLOT_DURATION_MINUTES)
    
    available_slots = []
    now = datetime.now()
    
    # Genera slots para cada turno (mañana y tarde)
    for shift in BUSINESS_SHIFTS:
        start_hour, start_minute = map(int, shift["start"].split(":"))
        end_hour, end_minute = map(int, shift["end"].split(":"))
        
        start_datetime = datetime.combine(target_date, time(start_hour, start_minute))
        end_datetime = datetime.combine(target_date, time(end_hour, end_minute))
        
        current = start_datetime
        
        while current + timedelta(minutes=duration) <= end_datetime:
            # Si es hoy, no muestra horarios pasados
            if target_date == now.date() and current <= now:
                current += timedelta(minutes=SLOT_DURATION_MINUTES)
                continue
                
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
