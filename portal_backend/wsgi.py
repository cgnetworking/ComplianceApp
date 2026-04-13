import os

from django.core.wsgi import get_wsgi_application

from .env import load_dotenv


load_dotenv()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "portal_backend.settings")

application = get_wsgi_application()
