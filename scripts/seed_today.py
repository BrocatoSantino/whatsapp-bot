import sys
import os
from datetime import datetime, date, timedelta, time
import random

# Agregar el root del proyecto al sys.path para poder importar app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import Tenant, Client, Service, Appointment
from app.services.availability import get_available_slots

def seed_today():
    db = SessionLocal()
    tenant_id = 2
    
    tenant = db.query(Tenant).filter_by(id=tenant_id).first()
    if not tenant:
        print("Tenant 2 not found!")
        return

    service = db.query(Service).filter_by(tenant_id=tenant_id).first()
    
    # Conseguir clientes de prueba
    clients = db.query(Client).filter(Client.tenant_id == tenant_id).all()
    if not clients:
        names = ["Juan Perez", "Carlos Gomez", "Matias Rossi", "Lucas Fernandez", "Nicolas Silva", "Federico Lopez"]
        for i, name in enumerate(names):
            client = Client(tenant_id=tenant_id, phone=f"549110000000{i}", name=name)
            db.add(client)
            clients.append(client)
        db.commit()

    today = date(2026, 9, 16) # Miércoles 16
    
    # 1. Llenar la mañana de hoy dejando SOLO 1 vacío.
    # La mañana consideramos antes de las 14:00
    available_slots_today = get_available_slots(db, today, service.id, tenant.id)
    morning_slots = [t for t in available_slots_today if t.hour < 14]
    
    if len(morning_slots) > 1:
        # Elegir un slot al azar para dejar vacio
        slot_to_leave_empty = random.choice(morning_slots)
        slots_to_fill = [t for t in morning_slots if t != slot_to_leave_empty]
        
        appointments_created = 0
        for t in slots_to_fill:
            client = random.choice(clients)
            appt = Appointment(
                tenant_id=tenant_id,
                client_id=client.id,
                service_id=service.id,
                date=today,
                time=t,
                status="confirmed"
            )
            db.add(appt)
            appointments_created += 1
            
        print(f"Llenada la mañana de hoy. Creados {appointments_created} turnos. Dejado libre: {slot_to_leave_empty}")
    else:
        print("No hay suficientes slots en la mañana para llenar dejando 1 libre.")

    # 2. Agregar un par de turnos para el resto de la semana
    days_to_seed = [today + timedelta(days=1), today + timedelta(days=2)] # Jueves y Viernes
    times_to_seed = [time(10, 0), time(11, 0), time(12, 0), time(16, 0), time(17, 0), time(18, 0)]
    
    extra_appts = 0
    for d in days_to_seed:
        num_appts = random.randint(2, 4)
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
            extra_appts += 1
            
    db.commit()
    print(f"Creados {extra_appts} turnos extra para Jueves y Viernes.")

if __name__ == "__main__":
    seed_today()
