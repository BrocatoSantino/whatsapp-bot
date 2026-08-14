from datetime import date, time, datetime, timedelta, timezone
import json
from sqlalchemy.orm import Session
from app.models import Appointment, Service, Tenant, BlockedTime

def get_available_dates(db: Session, tenant_id: int, days_ahead: int = 7) -> list[date]:
    """Retorna los próximos días hábiles basándose en los horarios del tenant y excepciones."""
    available_dates = []
    
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        return []
    
    try:
        working_days = json.loads(tenant.working_days)
    except:
        working_days = [0, 1, 2, 3, 4, 5]
        
    # Hora local de Argentina (UTC-3)
    ar_tz = timezone(timedelta(hours=-3))
    current_date = datetime.now(ar_tz).date()
    
    while len(available_dates) < days_ahead:
        if current_date.weekday() in working_days:
            # Check if there is a full day block
            full_block = db.query(BlockedTime).filter(
                BlockedTime.tenant_id == tenant_id,
                BlockedTime.date == current_date,
                BlockedTime.start_time.is_(None),
                BlockedTime.end_time.is_(None)
            ).first()
            
            if not full_block:
                available_dates.append(current_date)
        current_date += timedelta(days=1)
        
    return available_dates

def get_available_slots(db: Session, target_date: date, service_id: int, tenant_id: int) -> list[time]:
    """
    Obtiene los horarios disponibles para un servicio en una fecha específica para un tenant.
    Soporta turnos cortados y filtrado por excepciones (BlockedTime).
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        return []
        
    service = db.query(Service).filter(Service.id == service_id, Service.tenant_id == tenant_id).first()
    if not service:
        return []
    
    duration = service.duration_minutes
    try:
        business_shifts = json.loads(tenant.business_shifts)
    except:
        business_shifts = []
        
    slot_duration_minutes = tenant.slot_duration_minutes
    
    # Obtiene turnos existentes
    appointments = db.query(Appointment).filter(
        Appointment.tenant_id == tenant_id,
        Appointment.date == target_date,
        Appointment.status.in_(['confirmed', 'pending', 'completed'])
    ).all()
    
    # Calcula slots ocupados por turnos
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
                current += timedelta(minutes=slot_duration_minutes)
                
    # Obtiene bloqueos parciales para el día
    partial_blocks = db.query(BlockedTime).filter(
        BlockedTime.tenant_id == tenant_id,
        BlockedTime.date == target_date,
        BlockedTime.start_time.isnot(None),
        BlockedTime.end_time.isnot(None)
    ).all()
    
    available_slots = []
    
    ar_tz = timezone(timedelta(hours=-3))
    now = datetime.now(ar_tz).replace(tzinfo=None)
    
    # Genera slots para cada turno
    for shift in business_shifts:
        start_hour, start_minute = map(int, shift["start"].split(":"))
        end_hour, end_minute = map(int, shift["end"].split(":"))
        
        start_datetime = datetime.combine(target_date, time(start_hour, start_minute))
        end_datetime = datetime.combine(target_date, time(end_hour, end_minute))
        
        current = start_datetime
        
        while current + timedelta(minutes=duration) <= end_datetime:
            if target_date == now.date() and current <= now:
                current += timedelta(minutes=slot_duration_minutes)
                continue
                
            is_free = True
            check_time = current
            end_check = current + timedelta(minutes=duration)
            
            while check_time < end_check:
                ct_time = check_time.time()
                
                # Check si está ocupado por otro turno
                if ct_time in occupied_slots:
                    is_free = False
                    break
                    
                # Check si choca con un bloqueo parcial
                for block in partial_blocks:
                    if block.start_time <= ct_time < block.end_time:
                        is_free = False
                        break
                        
                if not is_free:
                    break
                    
                check_time += timedelta(minutes=slot_duration_minutes)
                
            if is_free:
                available_slots.append(current.time())
                
            current += timedelta(minutes=slot_duration_minutes)
            
    return available_slots
