# ✂️ puerto.barberr — Bot de WhatsApp

Este proyecto es un bot automatizado para WhatsApp diseñado para gestionar los turnos de la barbería **puerto.barberr**. Permite a los clientes agendar, consultar y cancelar turnos directamente desde WhatsApp, y provee un panel de administración web elegante para gestionar los turnos del día.

## 📋 Requisitos

- Python 3.10+
- Cuenta Meta Business (gratis, para usar la API de WhatsApp Cloud)
- [ngrok](https://ngrok.com/) para exponer el servidor local durante el desarrollo

## 🚀 Instalación

1. Clona el repositorio y navega al directorio:
```bash
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
```bash
cp .env.example .env
```
*(Edita el archivo `.env` con tus tokens reales de Meta y otras configuraciones)*

## ⚙️ Configurar Meta WhatsApp

Para que el bot se comunique con WhatsApp, sigue estos pasos:

1. Ve a [developers.facebook.com](https://developers.facebook.com/).
2. Crea una nueva App seleccionando el tipo **Business**.
3. Agrega el producto **WhatsApp** a tu aplicación.
4. En el panel de WhatsApp, obtén tu **Phone Number ID** y el **Access Token** de prueba.
5. Agrega tu número de teléfono personal a la lista de números de prueba en Meta.
6. Copia los tokens en tu archivo `.env`.

## 🗄️ Inicializar DB

Antes de arrancar, inicializa la base de datos sqlite y precarga servicios si es necesario:

```bash
python setup_db.py
```
*(Este comando asume que tienes un script setup_db.py. Si no, la DB se crea automáticamente al iniciar la app con `app/main.py`)*

## ▶️ Ejecutar

Inicia el servidor de desarrollo de FastAPI:

```bash
uvicorn app.main:app --reload
```
El servidor estará corriendo en `http://localhost:8000`.

## 🌐 Configurar Webhook (desarrollo)

Para que Meta pueda enviar mensajes a tu servidor local, necesitas exponerlo a internet:

```bash
ngrok http 8000
```
Copia la URL `https` que te da ngrok (ej: `https://xxxx.ngrok-free.app`), añádele `/webhook` y configúrala en el Dashboard de Meta WhatsApp junto con tu token de verificación (definido en `.env`).

## 👑 Panel Admin

El proyecto incluye un elegante panel de administración para ver los turnos del día y la recaudación estimada.

Accede a: `http://localhost:8000/admin`  
**Password default:** `admin123`

## 📁 Estructura del proyecto

```text
whatsapp-peluqueria/
├── app/
│   ├── admin/
│   │   ├── templates/     # Interfaces del panel web
│   │   └── router.py      # Rutas del panel admin
│   ├── services/          # Lógica de negocio (turnos, clientes)
│   ├── whatsapp/          # Lógica del bot (webhook, envío de msjs)
│   ├── config.py          # Configuración y variables de entorno
│   ├── database.py        # Conexión a la base de datos
│   ├── models.py          # Modelos SQLAlchemy
│   └── main.py            # Punto de entrada de FastAPI
├── requirements.txt       # Dependencias
└── README.md              # Documentación
```

---
*Hecho con dedicación para puerto.barberr* 💈
