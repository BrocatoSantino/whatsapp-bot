# ✂️ puerto.barberr — WhatsApp Booking Bot (SaaS)

Este proyecto es un sistema integral de reservas automatizado vía WhatsApp, diseñado específicamente para **puerto.barberr**. Funciona como un **SaaS (Software as a Service)** completo, permitiendo a los clientes autogestionar sus turnos 24/7 y ofreciendo al dueño un panel de administración premium para controlar su negocio.

## ✨ Características Principales

*   🤖 **Bot de WhatsApp Inteligente:** Flujo conversacional optimizado usando la API Oficial de Meta Cloud. Soporta menús interactivos, botones rápidos y manejo de errores (ej. audios no soportados).
*   📱 **Panel Admin (PWA):** Dashboard de diseño premium ("Glassmorphism"). Instalable en el celular (Progressive Web App) para uso nativo.
*   🔒 **Prevención de Doble Reserva:** Control de concurrencia estricto en la base de datos para evitar turnos superpuestos.
*   ⏰ **Timezone-Aware:** Todo el motor de reservas funciona anclado a la zona horaria UTC-3 (Argentina), haciéndolo invulnerable a los desfasajes horarios de servidores cloud internacionales.
*   🔔 **Recordatorios Automáticos (Cron):** Envío automático de recordatorios por WhatsApp un día antes del turno.
*   🔄 **Campañas de Reactivación:** El bot detecta clientes que no asisten hace 30 días y les envía un mensaje para incentivarlos a volver.
*   ☁️ **Cloud Native:** Arquitectura Serverless pensada para desplegarse en Vercel (Backend) y Supabase (Base de Datos PostgreSQL).

## 📋 Requisitos

*   Python 3.10+
*   Cuenta de **Meta Business** (para obtener tokens de WhatsApp).
*   Cuenta de **Supabase** (para la base de datos PostgreSQL en producción).
*   Cuenta de **Vercel** (para hosting).

## 🚀 Instalación Local

1. Clona el repositorio y navega al directorio:
```bash
git clone <repo-url>
cd whatsapp-peluqueria
```

2. Crea y activa un entorno virtual:
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

3. Instala las dependencias:
```bash
pip install -r requirements.txt
```

4. Configura las variables de entorno:
Copia el `.env.example` a `.env` y llena los datos:
```bash
# Meta / WhatsApp Cloud API
WA_VERIFY_TOKEN=tu_token_secreto_a_eleccion
WA_ACCESS_TOKEN=tu_token_de_meta
WA_PHONE_NUMBER_ID=tu_phone_id
WA_APP_SECRET=tu_app_secret

# Base de Datos (URL de Supabase o SQLite local)
DATABASE_URL=postgresql://user:pass@host:5432/postgres

# Panel Admin
ADMIN_PASSWORD=tu_contraseña_segura
```

## ⚙️ Configurar Meta WhatsApp

1. Ve a [developers.facebook.com](https://developers.facebook.com/).
2. Crea una App tipo **Business** y agrega el producto **WhatsApp**.
3. Obtén tu **Phone Number ID** y el **Access Token**.
4. Configura el **Webhook** en Meta apuntando a `https://tu-dominio.vercel.app/webhook` (o usa `ngrok` para desarrollo local).

## ▶️ Ejecutar en Desarrollo

Inicia el servidor local de FastAPI:
```bash
uvicorn app.main:app --reload
```
El servidor estará corriendo en `http://localhost:8000`.

## ☁️ Despliegue en Producción (Vercel)

El proyecto incluye el archivo `vercel.json` listo para Serverless Functions.

1. Instala el Vercel CLI o vincula tu repositorio de GitHub directamente en el dashboard de Vercel.
2. Agrega todas las variables del `.env` en la sección **Environment Variables** de tu proyecto en Vercel.
3. Despliega la aplicación.

### Configurar Tareas Automáticas (Cron Jobs)
Para que los recordatorios y las campañas de reactivación funcionen, debes usar un servicio de Cron externo (como [cron-job.org](https://cron-job.org) o Vercel Cron) que haga una petición GET a las siguientes rutas todos los días a las 10:00 AM:
*   `https://tu-dominio.vercel.app/api/cron/reminders`
*   `https://tu-dominio.vercel.app/api/cron/reengagement`

## 👑 Panel Admin

Accede a: `https://tu-dominio.vercel.app/admin`
*Desde un celular, abre el menú del navegador y selecciona "Agregar a la pantalla principal" para usarlo como aplicación.*

## 📁 Estructura del proyecto

```text
whatsapp-peluqueria/
├── app/
│   ├── admin/             # Panel web (Rutas y Templates)
│   ├── services/          # Lógica de negocio (Citas, Disponibilidad, Cron)
│   ├── whatsapp/          # Lógica del bot (Webhook, Estado conversacional)
│   ├── config.py          # Configuración global
│   ├── database.py        # Motor SQLAlchemy
│   ├── models.py          # Modelos de BD (Cliente, Turno, Servicio)
│   └── main.py            # Instancia de FastAPI
├── vercel.json            # Configuración Serverless
├── requirements.txt       # Dependencias
└── README.md              # Documentación
```

---
*Diseñado para ser un producto escalable (SaaS).* 💈
