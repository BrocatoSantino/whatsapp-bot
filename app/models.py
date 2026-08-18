from sqlalchemy import Column, Integer, String, Float, Boolean, Date, Time, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Tenant(Base):
    """Modelo maestro para cada empresa/barbería."""
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    
    # Credenciales de Meta por empresa
    wa_phone_number_id = Column(String, unique=True, index=True, nullable=False)
    wa_access_token = Column(String, nullable=False)
    owner_phone = Column(String, nullable=True)
    
    # Configuración de horarios por empresa (JSON guardado como String)
    working_days = Column(String, default='[0, 1, 2, 3, 4, 5]')  # Lunes a Sábado por defecto
    business_shifts = Column(String, default='[{"start": "09:30", "end": "12:30"}, {"start": "16:00", "end": "20:30"}]')
    slot_duration_minutes = Column(Integer, default=45)
    
    created_at = Column(DateTime, server_default=func.now())

    clients = relationship("Client", back_populates="tenant", cascade="all, delete-orphan")
    services = relationship("Service", back_populates="tenant", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="tenant", cascade="all, delete-orphan")
    blocked_times = relationship("BlockedTime", back_populates="tenant", cascade="all, delete-orphan")

class BlockedTime(Base):
    """Modelo para excepciones y bloqueos de agenda por empresa."""
    __tablename__ = "blocked_times"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    date = Column(Date, nullable=False, index=True)
    start_time = Column(Time, nullable=True) # Si es null, bloquea todo el día
    end_time = Column(Time, nullable=True)
    reason = Column(String, nullable=True) # Ej: Vacaciones, Feriado, Medico

    tenant = relationship("Tenant", back_populates="blocked_times")


class Client(Base):
    """Modelo para representar a los clientes."""
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    phone = Column(String, index=True)  # Quitamos unique=True porque un mismo cliente puede ir a 2 barberías distintas
    name = Column(String, default="")
    created_at = Column(DateTime, server_default=func.now())

    tenant = relationship("Tenant", back_populates="clients")
    appointments = relationship("Appointment", back_populates="client")


class Service(Base):
    """Modelo para representar los servicios de la peluquería."""
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    name = Column(String, nullable=False)
    duration_minutes = Column(Integer, default=30)
    price = Column(Float, default=0)
    active = Column(Boolean, default=True)

    tenant = relationship("Tenant", back_populates="services")
    appointments = relationship("Appointment", back_populates="service")


class Appointment(Base):
    """Modelo para representar los turnos."""
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"))
    service_id = Column(Integer, ForeignKey("services.id"))
    date = Column(Date)
    time = Column(Time)
    status = Column(String, default="confirmed")
    created_at = Column(DateTime, server_default=func.now())

    tenant = relationship("Tenant", back_populates="appointments")
    client = relationship("Client", back_populates="appointments")
    service = relationship("Service", back_populates="appointments")


class ConversationState(Base):
    """Estado de conversación del bot, persistido en base de datos para sobrevivir reinicios serverless."""
    __tablename__ = "conversation_states"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    phone = Column(String, nullable=False, index=True)
    state = Column(String, default="IDLE")
    data_json = Column(String, default="{}")  # JSON serializado
    last_activity = Column(DateTime, nullable=False)

    __table_args__ = (
        # Un solo estado por combinación tenant+phone
        {"sqlite_autoincrement": True},
    )
