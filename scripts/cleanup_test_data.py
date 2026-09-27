import sys
import os

# Agregar el root del proyecto al sys.path para poder importar app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import Tenant, Client, Appointment

def cleanup():
    db = SessionLocal()
    tenant_id = 2
    
    # Buscar los clientes que creamos en el script de test
    clients_to_delete = db.query(Client).filter(
        Client.tenant_id == tenant_id,
        Client.phone.like('549110000000%')
    ).all()
    
    if not clients_to_delete:
        print("No se encontraron clientes de prueba para eliminar.")
        return
        
    client_ids = [c.id for c in clients_to_delete]
    
    # Eliminar turnos de esos clientes
    appointments_deleted = db.query(Appointment).filter(
        Appointment.client_id.in_(client_ids)
    ).delete(synchronize_session=False)
    
    # Eliminar los clientes
    clients_deleted = db.query(Client).filter(
        Client.id.in_(client_ids)
    ).delete(synchronize_session=False)
    
    db.commit()
    print(f"Limpieza completa: Se eliminaron {appointments_deleted} turnos y {clients_deleted} clientes ficticios.")

if __name__ == "__main__":
    cleanup()
