from sqlalchemy import Column, Integer, String, Float, Boolean, Date, Time, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Client(Base):
    """Modelo para representar a los clientes."""
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String, unique=True, index=True)
    name = Column(String, default="")
    created_at = Column(DateTime, server_default=func.now())

    appointments = relationship("Appointment", back_populates="client")

class Service(Base):
    """Modelo para representar los servicios de la peluquería."""
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    duration_minutes = Column(Integer, default=30)
    price = Column(Float, default=0)
    active = Column(Boolean, default=True)

    appointments = relationship("Appointment", back_populates="service")

class Appointment(Base):
    """Modelo para representar los turnos."""
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    service_id = Column(Integer, ForeignKey("services.id"))
    date = Column(Date)
    time = Column(Time)
    status = Column(String, default="confirmed")
    created_at = Column(DateTime, server_default=func.now())

    client = relationship("Client", back_populates="appointments")
    service = relationship("Service", back_populates="appointments")
