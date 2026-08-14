from fastapi import APIRouter, Request, Form, Depends, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta, timezone
import locale

from app.database import get_db
from app.models import Appointment, Tenant
from app.services.appointment import get_appointments_by_date, cancel_appointment

router = APIRouter()
import os
current_dir = os.path.dirname(os.path.realpath(__file__))
templates = Jinja2Templates(directory=os.path.join(current_dir, "templates"))

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
        request=request, name="login.html", context={"error": False, "business_name": "TurnosPro", "hide_navbar": True}
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
        request=request, name="login.html", context={"error": True, "business_name": "TurnosPro", "hide_navbar": True}
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

    raw_appointments = get_appointments_by_date(db, target_date, tenant.id)
    
    recaudacion = sum(app.service.price for app in raw_appointments if app.service and app.status in ['confirmed', 'pending', 'completed'])
    
    appointments = []
    now = datetime.now(ar_tz).replace(tzinfo=None)
    for app in raw_appointments:
        if app.status in ['cancelled', 'no_show', 'completed']:
            continue
            
        if target_date == now.date():
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
            "business_name": tenant.name
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

    appointments = get_appointments_by_date(db, target_date, tenant.id)
    
    prev_date = target_date - timedelta(days=1)
    next_date = target_date + timedelta(days=1)
    is_today = target_date == datetime.now(ar_tz).date()
    fecha_format = f"{DIAS[target_date.weekday()]} {target_date.day} de {MESES[target_date.month - 1]} {target_date.year}"

    return templates.TemplateResponse(
        request=request, 
        name="historial.html", 
        context={
            "appointments": appointments,
            "target_date": target_date,
            "prev_date": prev_date,
            "next_date": next_date,
            "fecha_format": fecha_format,
            "is_today": is_today,
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
