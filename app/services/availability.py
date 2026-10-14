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
    except (json.JSONDecodeError, TypeError):
        working_days = [0, 1, 2, 3, 4, 5]
        
    try:
        overrides = json.loads(tenant.day_overrides or '{}')
    except (json.JSONDecodeError, TypeError):
        overrides = {}
        
    # Hora local de Argentina (UTC-3)
    ar_tz = timezone(timedelta(hours=-3))
    current_date = datetime.now(ar_tz).date()
    
    while len(available_dates) < days_ahead:
        day_str = str(current_date.weekday())
        is_working_day = current_date.weekday() in working_days
        has_override = day_str in overrides
        
        if has_override:
            day_is_open = len(overrides[day_str]) > 0
        else:
            day_is_open = is_working_day
            
        if day_is_open:
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
    Soporta turnos cortados, horarios de corrido, solapamiento real de intervalos
    y filtrado por excepciones (BlockedTime).
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        return []
        
    service = db.query(Service).filter(Service.id == service_id, Service.tenant_id == tenant_id).first()
    if not service:
        return []
    
    duration = service.duration_minutes
    slot_duration_minutes = tenant.slot_duration_minutes or 45
    
    day_str = str(target_date.weekday())
    try:
        overrides = json.loads(tenant.day_overrides or '{}')
    except (json.JSONDecodeError, TypeError):
        overrides = {}
        
    if day_str in overrides:
        business_shifts = overrides[day_str]
    else:
        try:
            business_shifts = json.loads(tenant.business_shifts or '[]')
        except (json.JSONDecodeError, TypeError):
            business_shifts = []
            
    if not business_shifts:
        return []
    
    # Recopilar todos los intervalos ocupados (busy_start, busy_end) para target_date
    busy_intervals = []

    # 1. Turnos existentes confirmados / pendientes / completados
    appointments = db.query(Appointment).filter(
        Appointment.tenant_id == tenant_id,
        Appointment.date == target_date,
        Appointment.status.in_(['confirmed', 'pending', 'completed'])
    ).all()
    
    for apt in appointments:
        apt_service = db.query(Service).filter(Service.id == apt.service_id).first()
        apt_duration = apt_service.duration_minutes if apt_service else slot_duration_minutes
        apt_start = datetime.combine(target_date, apt.time)
        apt_end = apt_start + timedelta(minutes=apt_duration)
        busy_intervals.append((apt_start, apt_end))
                
    # 2. Slots ocupados por turnos fijos recurrentes
    from app.models import RecurringAppointment
    recurring = db.query(RecurringAppointment).filter(
        RecurringAppointment.tenant_id == tenant_id,
        RecurringAppointment.day_of_week == target_date.weekday(),
        RecurringAppointment.active == True
    ).all()
    for rec in recurring:
        rec_service = db.query(Service).filter(Service.id == rec.service_id).first()
        rec_duration = rec_service.duration_minutes if rec_service else slot_duration_minutes
        rec_start = datetime.combine(target_date, rec.time)
        rec_end = rec_start + timedelta(minutes=rec_duration)
        busy_intervals.append((rec_start, rec_end))
                
    # 3. Bloqueos parciales para el día
    partial_blocks = db.query(BlockedTime).filter(
        BlockedTime.tenant_id == tenant_id,
        BlockedTime.date == target_date,
        BlockedTime.start_time.isnot(None),
        BlockedTime.end_time.isnot(None)
    ).all()
    for block in partial_blocks:
        b_start = datetime.combine(target_date, block.start_time)
        b_end = datetime.combine(target_date, block.end_time)
        busy_intervals.append((b_start, b_end))
    
    available_slots = []
    
    ar_tz = timezone(timedelta(hours=-3))
    now = datetime.now(ar_tz).replace(tzinfo=None)
    
    # Genera slots candidatos para cada turno
    for shift in business_shifts:
        try:
            start_hour, start_minute = map(int, shift["start"].split(":"))
            end_hour, end_minute = map(int, shift["end"].split(":"))
        except (ValueError, KeyError, AttributeError):
            continue
        
        start_datetime = datetime.combine(target_date, time(start_hour, start_minute))
        end_datetime = datetime.combine(target_date, time(end_hour, end_minute))
        
        current = start_datetime
        
        while current + timedelta(minutes=duration) <= end_datetime:
            slot_start = current
            slot_end = current + timedelta(minutes=duration)

            if target_date == now.date() and slot_start <= now:
                current += timedelta(minutes=slot_duration_minutes)
                continue
                
            # Dos intervalos [slot_start, slot_end) y [busy_start, busy_end) se solapan sii:
            # slot_start < busy_end and busy_start < slot_end
            is_free = True
            for busy_start, busy_end in busy_intervals:
                if slot_start < busy_end and busy_start < slot_end:
                    is_free = False
                    break
                    
            if is_free:
                available_slots.append(slot_start.time())
                
            current += timedelta(minutes=slot_duration_minutes)
            
    return available_slots
