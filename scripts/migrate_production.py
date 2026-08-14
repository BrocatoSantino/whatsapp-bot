import os
import sys
import json
from sqlalchemy import text

# Agregar el directorio raíz al path para poder importar la app
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from app.database import engine, SessionLocal
from app.models import Base, Tenant
from app.config import (
    BUSINESS_NAME, ADMIN_PASSWORD, 
    WA_PHONE_NUMBER_ID, WA_ACCESS_TOKEN, OWNER_PHONE,
    BUSINESS_SHIFTS, SLOT_DURATION_MINUTES
)

def migrate():
    print("🚀 Iniciando migración UNIFICADA a Producción (Multi-Tenant + Horarios)...")
    
    # 1. Crear nuevas tablas (tenants, blocked_times) si no existen
    Base.metadata.create_all(bind=engine)
    print("✅ Tablas creadas/verificadas exitosamente.")
    
    db = SessionLocal()
    try:
        # 2. Agregar columnas a tablas existentes
        # Se captura 'Exception' genérico para manejar PostgreSQL (ProgrammingError) y SQLite (OperationalError)
        print("⚙️ Verificando y agregando columnas nuevas...")
        queries = [
            "ALTER TABLE clients ADD COLUMN tenant_id INTEGER;",
            "ALTER TABLE services ADD COLUMN tenant_id INTEGER;",
            "ALTER TABLE appointments ADD COLUMN tenant_id INTEGER;",
            "ALTER TABLE tenants ADD COLUMN working_days VARCHAR DEFAULT '[0, 1, 2, 3, 4, 5]';"
        ]
        
        for q in queries:
            try:
                db.execute(text(q))
                db.commit()
            except Exception as e:
                # Si la columna ya existe, fallará de forma segura. Hacemos rollback y seguimos.
                db.rollback()
                print(f"⚠️ Nota: Ignorando error al agregar columna (probablemente ya existe).")
        
        # 3. Crear el primer Tenant (Tu Barbería) usando las variables de entorno si no existe
        tenant = db.query(Tenant).filter(Tenant.id == 1).first()
        if not tenant:
            print("📝 Creando Tenant #1 (Tu Barbería) basado en configuración actual (.env)...")
            tenant = Tenant(
                name=BUSINESS_NAME,
                username="barberia", # Usuario por defecto
                password_hash=ADMIN_PASSWORD,
                wa_phone_number_id=WA_PHONE_NUMBER_ID,
                wa_access_token=WA_ACCESS_TOKEN,
                owner_phone=OWNER_PHONE,
                business_shifts=json.dumps(BUSINESS_SHIFTS),
                slot_duration_minutes=SLOT_DURATION_MINUTES,
                working_days='[0, 1, 2, 3, 4, 5]'
            )
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
            print(f"✅ Tenant '{tenant.name}' creado con ID {tenant.id}")
        else:
            print(f"✅ Tenant #1 ya existe: '{tenant.name}'. Actualizando por las dudas...")
            # Nos aseguramos que tenga working_days
            if not tenant.working_days:
                tenant.working_days = '[0, 1, 2, 3, 4, 5]'
                db.commit()

        # 4. Asignar todos los registros huérfanos (viejos turnos) al Tenant #1 para NO PERDER DATOS
        print("🔗 Asignando registros históricos al Tenant #1 (Tu Barbería)...")
        update_queries = [
            "UPDATE clients SET tenant_id = 1 WHERE tenant_id IS NULL;",
            "UPDATE services SET tenant_id = 1 WHERE tenant_id IS NULL;",
            "UPDATE appointments SET tenant_id = 1 WHERE tenant_id IS NULL;"
        ]
        
        for q in update_queries:
            db.execute(text(q))
        
        db.commit()
        print("✅ Registros históricos protegidos y actualizados.")
        
        # 5. Intentar hacer la ForeignKey NOT NULL si la base de datos lo soporta (PostgreSQL sí, SQLite a veces no)
        try:
            db.execute(text("ALTER TABLE clients ALTER COLUMN tenant_id SET NOT NULL;"))
            db.execute(text("ALTER TABLE services ALTER COLUMN tenant_id SET NOT NULL;"))
            db.execute(text("ALTER TABLE appointments ALTER COLUMN tenant_id SET NOT NULL;"))
            db.commit()
            print("✅ Restricciones NOT NULL aplicadas a tenant_id.")
        except Exception as e:
            db.rollback()
            print("⚠️ No se pudo aplicar NOT NULL (SQLite no lo soporta directamente, es normal en local).")

        print("\n🎉 Migración a Producción completada con éxito. CERO PÉRDIDA DE DATOS.")

    except Exception as e:
        print(f"❌ Error CRÍTICO durante la migración: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    migrate()
