import os
from dotenv import load_dotenv

load_dotenv()

# WhatsApp Webhook (compartido entre todos los tenants)
WA_VERIFY_TOKEN = os.getenv('WA_VERIFY_TOKEN')
WA_APP_SECRET = os.getenv('WA_APP_SECRET')

# Base de datos
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./peluqueria.db')
