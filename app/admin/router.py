from fastapi import APIRouter, Request, Form, Depends, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
import locale

from app.config import ADMIN_PASSWORD, BUSINESS_NAME
from app.database import get_db
from app.models import Appointment
from app.services.appointment import get_appointments_by_date, cancel_appointment

router = APIRouter()
import os
import hashlib
current_dir = os.path.dirname(os.path.realpath(__file__))
templates = Jinja2Templates(directory=os.path.join(current_dir, "templates"))

def get_session_token():
    # Genera un token único y seguro basado en la contraseña del admin.
    # Así, nadie puede adivinar el valor de la cookie de sesión.
    return hashlib.sha256(f"{ADMIN_PASSWORD}_barber_secret_salt".encode()).hexdigest()

def get_admin_session(admin_session: str | None = Cookie(default=None)):
    if admin_session != get_session_token():
        return False
    return True

@router.get("/admin/login", response_class=HTMLResponse)
async def login_get(request: Request, admin_session: str | None = Cookie(default=None)):
    if admin_session == get_session_token():
        return RedirectResponse(url="/admin", status_code=303)
    return templates.TemplateResponse(
        request=request, name="login.html", context={"error": False, "business_name": BUSINESS_NAME}
    )

@router.post("/admin/login", response_class=HTMLResponse)
async def login_post(request: Request, password: str = Form(...)):
    if password == ADMIN_PASSWORD:
        response = RedirectResponse(url="/admin", status_code=303)
        # Seguridad mejorada: HttpOnly, Secure (solo HTTPS), SameSite=strict
        response.set_cookie(
            key="admin_session", 
            value=get_session_token(), 
            httponly=True, 
            secure=True, 
            samesite="strict"
        )
        return response
    
    return templates.TemplateResponse(
        request=request, name="login.html", context={"error": True, "business_name": BUSINESS_NAME}
    )

@router.get("/admin/logout")
async def logout():
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie("admin_session")
    return response

# Ayuda para formatear la fecha en español (ej. Lunes 12 de Agosto 2024)
MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

@router.get("/admin", response_class=HTMLResponse)
async def dashboard(
    request: Request, 
    fecha: str | None = None,
    db: Session = Depends(get_db),
    is_authenticated: bool = Depends(get_admin_session)
):
    if not is_authenticated:
        return RedirectResponse(url="/admin/login", status_code=303)
    
    if fecha:
        try:
            target_date = datetime.strptime(fecha, "%Y-%m-%d").date()
        except ValueError:
            target_date = date.today()
    else:
        target_date = date.today()

    raw_appointments = get_appointments_by_date(db, target_date)
    
    # Calculate recaudacion using all non-cancelled appointments
    recaudacion = sum(app.service.price for app in raw_appointments if app.service and app.status in ['confirmed', 'pending', 'completed'])
    
    # Filter appointments for the dashboard
    appointments = []
    now = datetime.now()
    for app in raw_appointments:
        if app.status in ['cancelled', 'no_show']:
            continue
            
        if target_date == now.date():
            # Hide if current time > appointment time + 30 mins
            app_datetime = datetime.combine(target_date, app.time)
            if now > app_datetime + timedelta(minutes=30):
                continue
                
        appointments.append(app)
        
    total_turnos = len(appointments)
    
    prev_date = target_date - timedelta(days=1)
    next_date = target_date + timedelta(days=1)
    
    is_today = target_date == date.today()
    
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
            "business_name": BUSINESS_NAME
        }
    )

@router.post("/admin/estado/{appointment_id}")
async def update_appointment_status(
    appointment_id: int, 
    status: str = Form(...),
    db: Session = Depends(get_db),
    is_authenticated: bool = Depends(get_admin_session)
):
    if not is_authenticated:
        return RedirectResponse(url="/admin/login", status_code=303)
    
    if status not in ['pending', 'completed', 'no_show', 'cancelled']:
        return RedirectResponse(url="/admin", status_code=303)
        
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if appointment:
        appointment.status = status
        db.commit()
    
    return RedirectResponse(url=f"/admin?fecha={appointment.date.strftime('%Y-%m-%d')}" if appointment else "/admin", status_code=303)

@router.get("/admin/historial", response_class=HTMLResponse)
async def historial(
    request: Request, 
    fecha: str | None = None,
    db: Session = Depends(get_db),
    is_authenticated: bool = Depends(get_admin_session)
):
    if not is_authenticated:
        return RedirectResponse(url="/admin/login", status_code=303)
    
    if fecha:
        try:
            target_date = datetime.strptime(fecha, "%Y-%m-%d").date()
        except ValueError:
            target_date = date.today()
    else:
        target_date = date.today()

    appointments = get_appointments_by_date(db, target_date)
    
    prev_date = target_date - timedelta(days=1)
    next_date = target_date + timedelta(days=1)
    is_today = target_date == date.today()
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
            "business_name": BUSINESS_NAME
        }
    )
