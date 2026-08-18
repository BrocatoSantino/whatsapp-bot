from fastapi import APIRouter, Request, Form, Depends, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta, timezone
import locale

from app.database import get_db
from app.models import Appointment, Tenant, Service
from app.services.appointment import get_appointments_by_date, cancel_appointment

router = APIRouter()
import os
current_dir = os.path.dirname(os.path.realpath(__file__))
templates = Jinja2Templates(directory=os.path.join(current_dir, "templates"))

def get_mock_appointments(tenant_id, target_date=None, start_date=None, end_date=None):
    from app.models import Client, Service
    from datetime import time
    import random
    
    mock_apps = []
    num_apps = random.randint(20, 30) if start_date else random.randint(5, 8)
    
    mock_service = Service(id=999, name="Corte Clásico (Mock)", price=6500, duration_minutes=45)
    mock_client = Client(id=999, name="Cliente de Prueba", phone="5491100000000")
    
    if start_date and end_date:
        days_in_week = (end_date - start_date).days + 1
        for i in range(num_apps):
            day_offset = random.randint(0, days_in_week - 1)
            app_date = start_date + timedelta(days=day_offset)
            hour = random.randint(10, 19)
            minute = random.choice([0, 30])
            status = random.choices(['completed', 'cancelled', 'no_show'], weights=[0.8, 0.1, 0.1])[0]
            
            app = Appointment(id=1000+i, tenant_id=tenant_id, date=app_date, time=time(hour, minute), status=status)
            app.service = mock_service
            app.client = mock_client
            mock_apps.append(app)
    elif target_date:
        for i in range(num_apps):
            hour = random.randint(10, 19)
            minute = random.choice([0, 30])
            status = random.choices(['pending', 'completed', 'cancelled', 'no_show'], weights=[0.5, 0.3, 0.1, 0.1])[0]
            
            app = Appointment(id=1000+i, tenant_id=tenant_id, date=target_date, time=time(hour, minute), status=status)
            app.service = mock_service
            app.client = mock_client
            mock_apps.append(app)
            
    # Sort by date and time
    mock_apps.sort(key=lambda x: (x.date, x.time))
    return mock_apps

def get_admin_session(admin_session: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> Tenant | None:
    if not admin_session:
        return None
    try:
        tenant_id, pwd_hash = admin_session.split(":")
        tenant = db.query(Tenant).filter(Tenant.id == int(tenant_id)).first()
        if tenant and tenant.password_hash == pwd_hash:
            return tenant
    except Exception:
        pass
    return None

@router.get("/admin/login", response_class=HTMLResponse)
async def login_get(request: Request, tenant: Tenant | None = Depends(get_admin_session)):
    if tenant:
        return RedirectResponse(url="/admin", status_code=303)
    return templates.TemplateResponse(
        request=request, name="login.html", context={"error": False, "business_name": "TurnoFlow", "hide_navbar": True}
    )

@router.post("/admin/login", response_class=HTMLResponse)
async def login_post(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.username == username).first()
    if tenant and tenant.password_hash == password:
        response = RedirectResponse(url="/admin", status_code=303)
        response.set_cookie(
            key="admin_session", 
            value=f"{tenant.id}:{tenant.password_hash}", 
            httponly=True, 
            secure=True, 
            samesite="strict",
            max_age=31536000
        )
        return response
    
    return templates.TemplateResponse(
        request=request, name="login.html", context={"error": True, "business_name": "TurnoFlow", "hide_navbar": True}
    )

@router.get("/admin/logout")
async def logout():
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie("admin_session")
    return response

MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

ar_tz = timezone(timedelta(hours=-3))

@router.get("/admin", response_class=HTMLResponse)
async def dashboard(
    request: Request, 
    fecha: str | None = None,
    db: Session = Depends(get_db),
    tenant: Tenant | None = Depends(get_admin_session)
):
    if not tenant:
        return RedirectResponse(url="/admin/login", status_code=303)
    
    if fecha:
        try:
            target_date = datetime.strptime(fecha, "%Y-%m-%d").date()
        except ValueError:
            target_date = datetime.now(ar_tz).date()
    else:
        target_date = datetime.now(ar_tz).date()

    if os.getenv("MOCK_DATA") == "True":
        raw_appointments = get_mock_appointments(tenant.id, target_date=target_date)
    else:
        raw_appointments = get_appointments_by_date(db, target_date, tenant.id)
    
    recaudacion = sum(app.service.price for app in raw_appointments if app.service and app.status in ['confirmed', 'pending', 'completed'])
    
    appointments = []
    now = datetime.now(ar_tz).replace(tzinfo=None)
    for app in raw_appointments:
        if app.status in ['cancelled', 'no_show', 'completed']:
            continue
            
        if target_date == now.date() and app.status != 'completed':
            app_datetime = datetime.combine(target_date, app.time)
            if now > app_datetime + timedelta(minutes=30):
                app.status = 'completed'
                db.commit()
                continue
                
        appointments.append(app)
        
    total_turnos = len(appointments)
    
    prev_date = target_date - timedelta(days=1)
    next_date = target_date + timedelta(days=1)
    
    is_today = target_date == datetime.now(ar_tz).date()
    fecha_format = f"{DIAS[target_date.weekday()]} {target_date.day} de {MESES[target_date.month - 1]} {target_date.year}"

    services = db.query(Service).filter(Service.tenant_id == tenant.id, Service.active == True).all()

    return templates.TemplateResponse(
        request=request, 
        name="dashboard.html", 
        context={
            "appointments": appointments,
            "target_date": target_date,
            "prev_date": prev_date,
            "next_date": next_date,
            "fecha_format": fecha_format,
            "is_today": is_today,
            "total_turnos": total_turnos,
            "recaudacion": recaudacion,
            "business_name": tenant.name,
            "services": services
        }
    )

@router.post("/admin/estado/{appointment_id}")
async def update_appointment_status(
    appointment_id: int, 
    status: str = Form(...),
    db: Session = Depends(get_db),
    tenant: Tenant | None = Depends(get_admin_session)
):
    if not tenant:
        return RedirectResponse(url="/admin/login", status_code=303)
    
    if status not in ['pending', 'completed', 'no_show', 'cancelled']:
        return RedirectResponse(url="/admin", status_code=303)
        
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id, Appointment.tenant_id == tenant.id).first()
    if appointment:
        appointment.status = status
        db.commit()
    
    return RedirectResponse(url=f"/admin?fecha={appointment.date.strftime('%Y-%m-%d')}" if appointment else "/admin", status_code=303)

@router.get("/admin/historial", response_class=HTMLResponse)
async def historial(
    request: Request, 
    week_offset: int = 0,
    db: Session = Depends(get_db),
    tenant: Tenant | None = Depends(get_admin_session)
):
    if not tenant:
        return RedirectResponse(url="/admin/login", status_code=303)
    
    ar_tz = timezone(timedelta(hours=-3))
    now = datetime.now(ar_tz).date()
    
    monday = now - timedelta(days=now.weekday()) + timedelta(weeks=week_offset)
    sunday = monday + timedelta(days=6)
    
    if os.getenv("MOCK_DATA") == "True":
        appointments = get_mock_appointments(tenant.id, start_date=monday, end_date=sunday)
    else:
        appointments = db.query(Appointment).filter(
            Appointment.tenant_id == tenant.id,
            Appointment.date >= monday,
            Appointment.date <= sunday
        ).all()
    
    total_revenue = 0
    total_minutes = 0
    completed_cuts = 0
    
    daily_counts = [0] * 7
    daily_dates = [(monday + timedelta(days=i)).strftime('%d/%m') for i in range(7)]
    
    for app in appointments:
        if app.status == 'completed':
            completed_cuts += 1
            if app.service:
                total_revenue += app.service.price
                total_minutes += app.service.duration_minutes
                
            day_index = (app.date - monday).days
            if 0 <= day_index <= 6:
                daily_counts[day_index] += 1
                
    hours = total_minutes // 60
    mins = total_minutes % 60
    time_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
    
    week_range_str = f"{monday.day} {MESES[monday.month-1][:3]} - {sunday.day} {MESES[sunday.month-1][:3]}"

    return templates.TemplateResponse(
        request=request, 
        name="historial.html", 
        context={
            "week_offset": week_offset,
            "week_range_str": week_range_str,
            "total_revenue": total_revenue,
            "time_str": time_str,
            "completed_cuts": completed_cuts,
            "daily_counts": daily_counts,
            "daily_dates": daily_dates,
            "business_name": tenant.name
        }
    )

from app.models import BlockedTime
from fastapi import Form
import json

@router.get("/admin/configuracion", response_class=HTMLResponse)
async def configuracion_get(
    request: Request,
    db: Session = Depends(get_db),
    tenant: Tenant | None = Depends(get_admin_session)
):
    if not tenant:
        return RedirectResponse(url="/admin/login", status_code=303)
        
    blocked_times = db.query(BlockedTime).filter(BlockedTime.tenant_id == tenant.id).order_by(BlockedTime.date.asc()).all()
    
    try:
        working_days = json.loads(tenant.working_days)
    except:
        working_days = [0, 1, 2, 3, 4, 5]
        
    try:
        business_shifts = json.loads(tenant.business_shifts)
    except:
        business_shifts = []

    return templates.TemplateResponse(
        request=request,
        name="configuracion.html",
        context={
            "business_name": tenant.name,
            "working_days": working_days,
            "business_shifts": business_shifts,
            "blocked_times": blocked_times,
            "slot_duration": tenant.slot_duration_minutes
        }
    )

@router.post("/admin/configuracion/horarios")
async def update_horarios(
    request: Request,
    working_days: str = Form(...),
    business_shifts: str = Form(...),
    slot_duration: int = Form(...),
    db: Session = Depends(get_db),
    tenant: Tenant | None = Depends(get_admin_session)
):
    if not tenant:
        return RedirectResponse(url="/admin/login", status_code=303)
        
    try:
        # Validar JSON básico
        json.loads(working_days)
        json.loads(business_shifts)
        
        tenant.working_days = working_days
        tenant.business_shifts = business_shifts
        if slot_duration >= 5:
            tenant.slot_duration_minutes = slot_duration
        db.commit()
    except Exception as e:
        print(f"Error parseando horarios: {e}")
        
    return RedirectResponse(url="/admin/configuracion", status_code=303)

@router.post("/admin/configuracion/block")
async def add_block(
    request: Request,
    fecha: str = Form(...),
    start_time: str = Form(None),
    end_time: str = Form(None),
    reason: str = Form(None),
    db: Session = Depends(get_db),
    tenant: Tenant | None = Depends(get_admin_session)
):
    if not tenant:
        return RedirectResponse(url="/admin/login", status_code=303)
        
    try:
        target_date = datetime.strptime(fecha, "%Y-%m-%d").date()
        s_time = datetime.strptime(start_time, "%H:%M").time() if start_time else None
        e_time = datetime.strptime(end_time, "%H:%M").time() if end_time else None
        
        block = BlockedTime(
            tenant_id=tenant.id,
            date=target_date,
            start_time=s_time,
            end_time=e_time,
            reason=reason
        )
        db.add(block)
        db.commit()
    except Exception as e:
        print(f"Error guardando bloqueo: {e}")
        
    return RedirectResponse(url="/admin/configuracion", status_code=303)

@router.post("/admin/configuracion/block/{block_id}/delete")
async def delete_block(
    block_id: int,
    db: Session = Depends(get_db),
    tenant: Tenant | None = Depends(get_admin_session)
):
    if not tenant:
        return RedirectResponse(url="/admin/login", status_code=303)
        
    block = db.query(BlockedTime).filter(BlockedTime.id == block_id, BlockedTime.tenant_id == tenant.id).first()
    if block:
        db.delete(block)
        db.commit()
        
    return RedirectResponse(url="/admin/configuracion", status_code=303)

from app.services.availability import get_available_slots
from app.services.appointment import create_appointment
from fastapi import Query, Form

@router.get("/admin/api/slots")
async def get_slots(
    date: str = Query(...), 
    service_id: int = Query(...),
    db: Session = Depends(get_db),
    tenant: Tenant | None = Depends(get_admin_session)
):
    if not tenant:
        return []
    
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
        slots = get_available_slots(db, target_date, service_id, tenant.id)
        return [{"time": s.strftime("%H:%M")} for s in slots]
    except Exception as e:
        print(f"Error fetching slots: {e}")
        return []

@router.post("/admin/turnos/nuevo")
async def add_manual_appointment(
    client_name: str = Form(...),
    client_phone: str = Form(""),
    service_id: int = Form(...),
    date: str = Form(...),
    time: str = Form(...),
    db: Session = Depends(get_db),
    tenant: Tenant | None = Depends(get_admin_session)
):
    if not tenant:
        return RedirectResponse(url="/admin/login", status_code=303)
        
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
        target_time = datetime.strptime(time, "%H:%M").time()
        
        # Phone logic (use dummy if empty)
        phone = client_phone.strip()
        if not phone:
            phone = f"manual_{int(datetime.now().timestamp())}"
            
        create_appointment(db, phone, client_name, service_id, target_date, target_time, tenant.id)
    except Exception as e:
        print(f"Error creating manual appointment: {e}")
        
    return RedirectResponse(url=f"/admin?fecha={date}", status_code=303)

@router.get("/admin/servicios", response_class=HTMLResponse)
async def servicios_get(
    request: Request,
    db: Session = Depends(get_db),
    tenant: Tenant | None = Depends(get_admin_session)
):
    if not tenant:
        return RedirectResponse(url="/admin/login", status_code=303)
        
    services = db.query(Service).filter(Service.tenant_id == tenant.id).all()
    
    return templates.TemplateResponse(
        request=request,
        name="servicios.html",
        context={
            "business_name": tenant.name,
            "services": services
        }
    )

@router.post("/admin/servicios/nuevo")
async def add_service(
    name: str = Form(...),
    price: float = Form(...),
    db: Session = Depends(get_db),
    tenant: Tenant | None = Depends(get_admin_session)
):
    if not tenant:
        return RedirectResponse(url="/admin/login", status_code=303)
        
    try:
        new_service = Service(
            tenant_id=tenant.id,
            name=name,
            price=price,
            duration_minutes=tenant.slot_duration_minutes,
            active=True
        )
        db.add(new_service)
        db.commit()
    except Exception as e:
        print(f"Error creating service: {e}")
        
    return RedirectResponse(url="/admin/servicios", status_code=303)

@router.post("/admin/servicios/{service_id}/editar")
async def edit_service(
    service_id: int,
    name: str = Form(...),
    price: float = Form(...),
    active: str = Form(None),
    db: Session = Depends(get_db),
    tenant: Tenant | None = Depends(get_admin_session)
):
    if not tenant:
        return RedirectResponse(url="/admin/login", status_code=303)
        
    try:
        service = db.query(Service).filter(Service.id == service_id, Service.tenant_id == tenant.id).first()
        if service:
            service.name = name
            service.price = price
            service.duration_minutes = tenant.slot_duration_minutes
            service.active = active == "true"
            db.commit()
    except Exception as e:
        print(f"Error editing service: {e}")
        
    return RedirectResponse(url="/admin/servicios", status_code=303)

@router.post("/admin/servicios/{service_id}/eliminar")
async def delete_service(
    service_id: int,
    db: Session = Depends(get_db),
    tenant: Tenant | None = Depends(get_admin_session)
):
    if not tenant:
        return RedirectResponse(url="/admin/login", status_code=303)
        
    try:
        service = db.query(Service).filter(Service.id == service_id, Service.tenant_id == tenant.id).first()
        if service:
            db.delete(service)
            db.commit()
    except Exception as e:
        print(f"Error deleting service: {e}")
        
    return RedirectResponse(url="/admin/servicios", status_code=303)

