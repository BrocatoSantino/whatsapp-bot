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
    title="puerto.barberr Bot API",
    description="API de WhatsApp y Panel de Administración para puerto.barberr",
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
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def root():
    return RedirectResponse(url="/admin", status_code=303)

@app.get("/api/update-services")
async def update_services(db: Session = Depends(get_db)):
    from app.models import Service
    services = db.query(Service).all()
    out = []
    for s in services:
        if "corte" == s.name.lower().strip() or "corte de pelo" in s.name.lower():
            s.price = 15000
            s.active = True
            out.append(f"Actualizado: {s.name} a ${s.price}")
        else:
            s.active = False
            out.append(f"Desactivado: {s.name}")
    db.commit()
    return {"status": "ok", "changes": out}
