import os
import sys
import json

# Agregar el directorio raíz al path para poder importar la app
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from app.database import SessionLocal
from app.models import Tenant
from app.config import WA_ACCESS_TOKEN, BUSINESS_SHIFTS, SLOT_DURATION_MINUTES

def add_tenant():
    db = SessionLocal()
    
    # Datos de la segunda barbería
    new_phone_id = "1304736589387130"
    new_owner_phone = "5493329551155"
    
    # Chequear si ya existe
    existing = db.query(Tenant).filter(Tenant.wa_phone_number_id == new_phone_id).first()
    
    if existing:
        print(f"La barbería con ID {new_phone_id} ya existe en la base de datos.")
    else:
        new_tenant = Tenant(
            name="Segunda Barbería",
            username="barberia2",
            password_hash="admin123", # Contraseña genérica por ahora
            wa_phone_number_id=new_phone_id,
            wa_access_token=WA_ACCESS_TOKEN, # Mismo token
            owner_phone=new_owner_phone,
            business_shifts=json.dumps(BUSINESS_SHIFTS),
            slot_duration_minutes=SLOT_DURATION_MINUTES,
            working_days='[0, 1, 2, 3, 4, 5]'
        )
        db.add(new_tenant)
        db.commit()
        db.refresh(new_tenant)
        print(f"Segunda barbería creada exitosamente con ID: {new_tenant.id}")
        
    db.close()

if __name__ == "__main__":
    add_tenant()
