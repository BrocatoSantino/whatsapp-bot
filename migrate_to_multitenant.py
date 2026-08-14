import os
import sys

# Ajustar PYTHONPATH para que pueda importar módulos locales
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.database import engine, Base, SessionLocal
from app.models import Tenant, Client, Service, Appointment
from app.config import (
    BUSINESS_NAME, ADMIN_USERNAME, ADMIN_PASSWORD, 
    WA_PHONE_NUMBER_ID, WA_ACCESS_TOKEN, OWNER_PHONE,
    BUSINESS_SHIFTS, SLOT_DURATION_MINUTES
)
import json

def migrate():
    print("Iniciando migración a Multi-Tenant...")
    
    db = SessionLocal()
    
    try:
        db.query(Tenant).first()
        print("La tabla 'tenants' ya existe.")
    except Exception as e:
        print("Creando nuevas tablas...")
        db.rollback()
        Base.metadata.create_all(bind=engine)

    # Create the default tenant if none exists
    tenant = db.query(Tenant).filter(Tenant.username == ADMIN_USERNAME).first()
    if not tenant:
        print(f"Creando Tenant por defecto para: {BUSINESS_NAME}...")
        tenant = Tenant(
            name=BUSINESS_NAME,
            username=ADMIN_USERNAME,
            password_hash=ADMIN_PASSWORD,
            wa_phone_number_id=WA_PHONE_NUMBER_ID or "PENDING",
            wa_access_token=WA_ACCESS_TOKEN or "PENDING",
            owner_phone=OWNER_PHONE,
            business_shifts=json.dumps(BUSINESS_SHIFTS),
            slot_duration_minutes=SLOT_DURATION_MINUTES
        )
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
        print(f"Tenant creado con ID: {tenant.id}")
    else:
        print(f"Tenant ya existe con ID: {tenant.id}")

    # SQLite workaround to add columns safely
    tables_to_update = ['clients', 'services', 'appointments']
    for table in tables_to_update:
        try:
            db.execute(text(f"SELECT tenant_id FROM {table} LIMIT 1"))
        except Exception:
            db.rollback()
            print(f"Agregando columna tenant_id a la tabla {table}...")
            # En SQLite, lo agregamos con DEFAULT
            db.execute(text(f"ALTER TABLE {table} ADD COLUMN tenant_id INTEGER DEFAULT {tenant.id} REFERENCES tenants(id)"))
            db.commit()
            print(f"Columna tenant_id agregada a {table}.")

    # Update any nulls just in case
    db.execute(text("UPDATE clients SET tenant_id = :tid WHERE tenant_id IS NULL"), {"tid": tenant.id})
    db.execute(text("UPDATE services SET tenant_id = :tid WHERE tenant_id IS NULL"), {"tid": tenant.id})
    db.execute(text("UPDATE appointments SET tenant_id = :tid WHERE tenant_id IS NULL"), {"tid": tenant.id})
    db.commit()
    
    print("Migración completada exitosamente.")

if __name__ == "__main__":
    migrate()
