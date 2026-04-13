import os

from django.core.asgi import get_asgi_application

from .env import load_dotenv


load_dotenv()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "portal_backend.settings")

application = get_asgi_application()
