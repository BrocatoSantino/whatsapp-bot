from app.database import Base, engine, SessionLocal
from app.models import Service, Client, Appointment

def setup_database():
    """Crea las tablas y los datos iniciales."""
    print("Creando tablas en la base de datos...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # Verificar si ya existen servicios
        existing_services = db.query(Service).count()
        if existing_services == 0:
            print("Insertando servicios de ejemplo...")
            services = [
                Service(name="Corte", duration_minutes=30, price=5000),
                Service(name="Barba", duration_minutes=20, price=3000),
                Service(name="Corte + Barba", duration_minutes=45, price=7000),
                Service(name="Fade", duration_minutes=40, price=6000),
            ]
            db.add_all(services)
            db.commit()
            print("Servicios insertados correctamente.")
        else:
            print("Los servicios ya existen en la base de datos.")
            
        print("¡Configuración de base de datos completada!")
    finally:
        db.close()

if __name__ == "__main__":
    setup_database()
