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
current_dir = os.path.dirname(os.path.realpath(__file__))
templates = Jinja2Templates(directory=os.path.join(current_dir, "templates"))

def get_admin_session(admin_session: str | None = Cookie(default=None)):
    if admin_session != "authenticated":
        return False
    return True

@router.get("/admin/login", response_class=HTMLResponse)
async def login_get(request: Request, admin_session: str | None = Cookie(default=None)):
    if admin_session == "authenticated":
        return RedirectResponse(url="/admin", status_code=303)
    return templates.TemplateResponse(
        request=request, name="login.html", context={"error": False, "business_name": BUSINESS_NAME}
    )

@router.post("/admin/login", response_class=HTMLResponse)
async def login_post(request: Request, password: str = Form(...)):
    if password == ADMIN_PASSWORD:
        response = RedirectResponse(url="/admin", status_code=303)
        response.set_cookie(key="admin_session", value="authenticated", httponly=True)
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

    appointments = get_appointments_by_date(db, target_date)
    
    total_turnos = len(appointments)
    recaudacion = sum(app.service.price for app in appointments if app.service and app.status != 'cancelled')
    
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

@router.post("/admin/cancelar/{appointment_id}")
async def cancel_appointment_admin(
    appointment_id: int, 
    db: Session = Depends(get_db),
    is_authenticated: bool = Depends(get_admin_session)
):
    if not is_authenticated:
        return RedirectResponse(url="/admin/login", status_code=303)
    
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if appointment:
        appointment.status = 'cancelled'
        db.commit()
        # Optionally, could use cancel_appointment(db, appointment_id, appointment.client.phone) 
        # but the requirements explicitly say to change the DB directly.
    
    return RedirectResponse(url="/admin", status_code=303)
