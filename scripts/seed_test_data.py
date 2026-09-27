import sys
import os
from datetime import datetime, date, timedelta, time
import random

# Agregar el root del proyecto al sys.path para poder importar app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import Tenant, Client, Service, Appointment

def seed():
    db = SessionLocal()
    tenant_id = 2
    
    tenant = db.query(Tenant).filter_by(id=tenant_id).first()
    if not tenant:
        print("Tenant 2 not found!")
        return
        
    print(f"Seeding data for Tenant: {tenant.name}")

    # Verificar o crear al menos un servicio
    services = db.query(Service).filter_by(tenant_id=tenant_id).all()
    if not services:
        print("No services found, creating default services...")
        svc1 = Service(tenant_id=tenant_id, name="Corte Clásico", duration_minutes=30, price=5000, active=True)
        svc2 = Service(tenant_id=tenant_id, name="Corte y Barba", duration_minutes=60, price=8000, active=True)
        db.add_all([svc1, svc2])
        db.commit()
        services = [svc1, svc2]
    
    service = services[0]

    # Nombres ficticios
    names = ["Juan Perez", "Carlos Gomez", "Matias Rossi", "Lucas Fernandez", "Nicolas Silva", "Federico Lopez"]
    
    # Crear clientes
    clients = []
    for i, name in enumerate(names):
        client = Client(tenant_id=tenant_id, phone=f"549110000000{i}", name=name)
        db.add(client)
        clients.append(client)
    
    db.commit()
    print(f"Created {len(clients)} clients.")

    # Crear turnos
    # Hoy es 15 de septiembre de 2026 (Martes). Miercoles es 16.
    # Vamos a crear turnos para el Lunes 14, Martes 15, Jueves 17, Viernes 18
    base_date = date(2026, 9, 14) # Lunes
    
    days_to_seed = [
        base_date, # Lunes 14
        base_date + timedelta(days=1), # Martes 15
    ]
    
    times_to_seed = [
        time(10, 0), time(11, 0), time(12, 0), 
        time(16, 0), time(17, 0), time(18, 0)
    ]
    
    appointments_created = 0
    
    for d in days_to_seed:
        # 3 a 5 turnos por dia
        num_appts = random.randint(3, 5)
        selected_times = random.sample(times_to_seed, num_appts)
        
        for t in selected_times:
            client = random.choice(clients)
            appt = Appointment(
                tenant_id=tenant_id,
                client_id=client.id,
                service_id=service.id,
                date=d,
                time=t,
                status="confirmed"
            )
            db.add(appt)
            appointments_created += 1
            
    db.commit()
    print(f"Created {appointments_created} appointments.")
    
    # Marcar los clientes creados con un flag o comentario? 
    # El delete despues va a ser facil si borramos todos los clientes con telefono '549110000000%'

if __name__ == "__main__":
    seed()
