from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from app.database import engine, Base, get_db
from app.whatsapp.webhook import router as webhook_router
from app.admin.router import router as admin_router
import logging

# Configurar logging básico
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Crear tablas al startup (desactivado para Vercel)
# Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TurnoFlow API",
    description="Sistema de gestión de turnos por WhatsApp para barberías",
    version="1.0.0"
)

# Montar routers
app.include_router(webhook_router)
app.include_router(admin_router)

import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

# Configurar directorio estático
static_dir = os.path.join(os.path.dirname(__file__), "admin", "static")

# Vercel tiene un sistema de archivos de solo lectura. Solo montamos si el directorio existe.
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def root():
    return RedirectResponse(url="/admin", status_code=303)

