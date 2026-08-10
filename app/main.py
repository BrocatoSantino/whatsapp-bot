from fastapi import FastAPI
from app.database import engine, Base
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

@app.get("/")
async def root():
    return {"message": "puerto.barberr Bot API está funcionando. Visita /admin para el panel de administración."}
