import os
from dotenv import load_dotenv

load_dotenv()

WA_PHONE_NUMBER_ID = os.getenv('WA_PHONE_NUMBER_ID')
WA_ACCESS_TOKEN = os.getenv('WA_ACCESS_TOKEN')
WA_VERIFY_TOKEN = os.getenv('WA_VERIFY_TOKEN')
WA_APP_SECRET = os.getenv('WA_APP_SECRET')

BUSINESS_NAME = os.getenv('BUSINESS_NAME', 'puerto.barberr')
BUSINESS_HOURS_START = int(os.getenv('BUSINESS_HOURS_START', 9))
BUSINESS_HOURS_END = int(os.getenv('BUSINESS_HOURS_END', 20))
SLOT_DURATION_MINUTES = int(os.getenv('SLOT_DURATION_MINUTES', 30))
BUSINESS_DAYS = [0, 1, 2, 3, 4, 5]  # Lunes a Sábado

ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./peluqueria.db')
OWNER_PHONE = os.getenv('OWNER_PHONE', '')
