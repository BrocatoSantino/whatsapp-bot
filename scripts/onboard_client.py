#!/usr/bin/env python3
"""
Script interactivo para dar de alta una nueva barbería en TurnoFlow.
Ejecutar desde la raíz del proyecto: python scripts/onboard_client.py
"""
import os
import sys
import json

# Agregar el directorio raíz al path para poder importar la app
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from app.database import SessionLocal
from app.models import Tenant, Service

def main():
    print("\n" + "="*50)
    print("   🚀 TurnoFlow — Alta de Nueva Barbería")
    print("="*50 + "\n")
    
    # Datos del negocio
    name = input("📌 Nombre del negocio (ej: Puerto Barber): ").strip()
    if not name:
        print("❌ El nombre es obligatorio.")
        return
    
    username = input("👤 Usuario para el panel admin (ej: puertobarber): ").strip().lower()
    if not username:
        print("❌ El usuario es obligatorio.")
        return
    
    password = input("🔑 Contraseña para el panel admin: ").strip()
    if not password:
        print("❌ La contraseña es obligatoria.")
        return
    
    # Datos de Meta/WhatsApp
    print("\n--- Datos de Meta (WhatsApp API) ---")
    wa_phone_number_id = input("📱 Phone Number ID de Meta: ").strip()
    if not wa_phone_number_id:
        print("❌ El Phone Number ID es obligatorio.")
        return
    
    wa_access_token = input("🔐 Access Token permanente de Meta: ").strip()
    if not wa_access_token:
        print("❌ El Access Token es obligatorio.")
        return
    
    owner_phone = input("📞 Teléfono del dueño (con código país, ej: 5493329574608): ").strip()
    
    # Horarios
    print("\n--- Configuración de Horarios ---")
    print("Días laborales por defecto: Lunes a Sábado")
    print("Horarios por defecto: 09:30-12:30 y 16:00-20:30")
    custom = input("¿Querés personalizar los horarios? (s/n): ").strip().lower()
    
    if custom == 's':
        print("\nIngresá los días laborales separados por coma (0=Lun, 1=Mar, 2=Mie, 3=Jue, 4=Vie, 5=Sab, 6=Dom)")
        days_input = input("Días (ej: 0,1,2,3,4,5): ").strip()
        try:
            working_days = [int(d.strip()) for d in days_input.split(",")]
        except:
            working_days = [0, 1, 2, 3, 4, 5]
        
        shifts = []
        print("\nIngresá las franjas horarias (vacío para terminar):")
        while True:
            start = input("  Hora inicio (ej: 09:30, o Enter para terminar): ").strip()
            if not start:
                break
            end = input("  Hora fin (ej: 12:30): ").strip()
            if end:
                shifts.append({"start": start, "end": end})
        
        if not shifts:
            shifts = [{"start": "09:30", "end": "12:30"}, {"start": "16:00", "end": "20:30"}]
        
        slot_str = input("Duración de cada turno en minutos (default: 45): ").strip()
        slot_duration = int(slot_str) if slot_str.isdigit() else 45
    else:
        working_days = [0, 1, 2, 3, 4, 5]
        shifts = [{"start": "09:30", "end": "12:30"}, {"start": "16:00", "end": "20:30"}]
        slot_duration = 45
    
    # Servicios
    print("\n--- Servicios ---")
    services_list = []
    print("Ingresá los servicios (vacío para terminar):")
    while True:
        svc_name = input("  Nombre del servicio (ej: Corte, o Enter para terminar): ").strip()
        if not svc_name:
            break
        svc_price = input(f"  Precio de '{svc_name}' (ej: 12000): ").strip()
        svc_duration = input(f"  Duración de '{svc_name}' en minutos (default: {slot_duration}): ").strip()
        
        services_list.append({
            "name": svc_name,
            "price": float(svc_price) if svc_price else 0,
            "duration": int(svc_duration) if svc_duration.isdigit() else slot_duration
        })
    
    if not services_list:
        services_list = [{"name": "Corte", "price": 12000, "duration": slot_duration}]
        print("  (Se agregó 'Corte' por defecto)")
    
    # Confirmar
    print("\n" + "="*50)
    print("   📋 Resumen")
    print("="*50)
    print(f"  Negocio:     {name}")
    print(f"  Usuario:     {username}")
    print(f"  Contraseña:  {password}")
    print(f"  Phone ID:    {wa_phone_number_id}")
    print(f"  Tel. dueño:  {owner_phone or 'No configurado'}")
    print(f"  Días:        {working_days}")
    print(f"  Franjas:     {shifts}")
    print(f"  Duración:    {slot_duration} min")
    print(f"  Servicios:   {[s['name'] for s in services_list]}")
    print("="*50)
    
    confirm = input("\n¿Confirmar alta? (s/n): ").strip().lower()
    if confirm != 's':
        print("❌ Cancelado.")
        return
    
    # Crear en la base de datos
    db = SessionLocal()
    try:
        # Verificar que no exista
        existing = db.query(Tenant).filter(
            (Tenant.username == username) | (Tenant.wa_phone_number_id == wa_phone_number_id)
        ).first()
        
        if existing:
            print(f"❌ Ya existe una barbería con ese usuario o Phone ID.")
            return
        
        tenant = Tenant(
            name=name,
            username=username,
            password_hash=password,
            wa_phone_number_id=wa_phone_number_id,
            wa_access_token=wa_access_token,
            owner_phone=owner_phone or None,
            working_days=json.dumps(working_days),
            business_shifts=json.dumps(shifts),
            slot_duration_minutes=slot_duration
        )
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
        
        # Crear servicios
        for svc in services_list:
            service = Service(
                tenant_id=tenant.id,
                name=svc["name"],
                price=svc["price"],
                duration_minutes=svc["duration"],
                active=True
            )
            db.add(service)
        db.commit()
        
        print(f"\n✅ ¡Barbería '{name}' creada exitosamente!")
        print(f"   ID: {tenant.id}")
        print(f"   Panel: tu-dominio.com/admin/login")
        print(f"   Usuario: {username}")
        print(f"   Servicios: {len(services_list)} creados")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()
