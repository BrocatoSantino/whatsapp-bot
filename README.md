# ✂️ TurnoFlow — WhatsApp Booking SaaS

Este proyecto es un sistema integral de reservas automatizado vía WhatsApp, diseñado como un **SaaS (Software as a Service) Multi-Tenant (Multi-Barbería)**. Permite a múltiples barberías o salones usar un mismo servidor para que sus clientes autogestionen turnos 24/7 de forma 100% aislada, ofreciendo a cada dueño un panel de administración premium personalizado.

## ✨ Características Principales

*   🏢 **Arquitectura Multi-Barbería (Multi-Tenant):** Un solo servidor y base de datos aloja múltiples barberías. Cada barbería tiene su propio número de WhatsApp, clientes, configuración de horarios y turnos totalmente aislados.
*   🤖 **Bot de WhatsApp Inteligente:** Flujo conversacional optimizado usando la API Oficial de Meta Cloud.
*   📱 **Panel Admin Premium (PWA):** Dashboard "Glassmorphism" instalable en celulares para que los dueños administren todo su negocio.
*   🔒 **Prevención de Doble Reserva y Excepciones:** Control de concurrencia estricto. Permite configurar días laborables, cortes (almuerzo) y bloqueos excepcionales (feriados o descansos).
*   ⏰ **Timezone-Aware:** Todo el motor de reservas funciona anclado a la zona horaria UTC-3 (Argentina).
*   🔔 **Recordatorios y Retención:** Tareas automáticas que recuerdan turnos 24hs antes y envían campañas a clientes que no asisten hace 30 días, identificando dinámicamente desde qué barbería se envía.
*   ☁️ **Cloud Native:** Arquitectura Serverless pensada para desplegarse en Vercel (Backend) y Supabase (Base de Datos PostgreSQL).

## 📋 Requisitos

*   Python 3.10+
*   Cuenta de **Meta Business** (Tokens de WhatsApp para cada barbería).
*   Cuenta de **Supabase** (Base de datos PostgreSQL en producción).
*   Cuenta de **Vercel** (Hosting).

## 🚀 Instalación y Configuración

1. Clona el repositorio:
```bash
git clone <repo-url>
cd whatsapp-peluqueria
```

2. Entorno virtual y dependencias:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. Variables de entorno:
Copia `.env.example` a `.env` y llena los datos base. En Multi-Tenant, las credenciales de WhatsApp globales de `.env` ya no se usan, ¡están en la base de datos!
```bash
# Base de Datos (URL de Supabase o SQLite local)
# DATABASE_URL="postgresql://postgres.[tu-proyecto]:[pass]@[tu-pooler].supabase.com:6543/postgres"
DATABASE_URL="sqlite:///./peluqueria.db"

# Panel Admin (Contraseña maestra general)
ADMIN_PASSWORD=admin123
```

## 👥 Añadir Barberías (Tenants)

Para registrar una nueva barbería en tu SaaS, usa el script de comando:

```bash
python3 scripts/add_second_tenant.py
```
Este script (que podés modificar a tu gusto) inserta un nuevo negocio en la base de datos con su respectivo `wa_phone_number_id` y `wa_access_token` de Meta, y le crea un usuario y contraseña para entrar al panel de control web.

## ☁️ Despliegue en Producción (Vercel)

El proyecto incluye el archivo `vercel.json` listo para Serverless Functions.

1. Vincula tu repositorio de GitHub directamente en el dashboard de Vercel.
2. Agrega la variable `DATABASE_URL` apuntando a tu PostgreSQL (Supabase) en la sección **Environment Variables** de tu proyecto en Vercel. Asegurate de usar el **Connection Pooler URL (IPv4)**.
3. El dominio de tu aplicación será el que Vercel te asigne por defecto (ej: `https://tu-proyecto.vercel.app`), o puedes comprar uno personalizado en la pestaña **Domains** de Vercel.
4. Despliega la aplicación.

### Configurar Tareas Automáticas (Vercel Cron)
Los recordatorios automáticos ya están configurados en `vercel.json` para ejecutarse automáticamente en la nube.
*   `0 23 * * *`: Recordatorios de turnos.
*   `0 16 * * *`: Campañas de reactivación.

## ⚙️ Conectar Webhooks de Meta

En el panel de Meta for Developers de cada cliente, deberás apuntar el Webhook de WhatsApp a la URL de tu SaaS:
`https://tu-proyecto.vercel.app/webhook`

## 👑 Panel Admin Web

Accede a: `https://tu-proyecto.vercel.app/admin/login`
El dueño de cada barbería deberá iniciar sesión con su `username` y `password` generados al crear el Tenant.

---
*Diseñado para escalar como un producto SaaS B2B.* 💈🚀
