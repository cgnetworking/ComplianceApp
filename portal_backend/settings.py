from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    value = os.environ.get(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


def parse_database_url(database_url: str) -> dict[str, object]:
    parsed = urlparse(database_url)
    scheme = parsed.scheme.lower()
    if scheme not in {"postgres", "postgresql", "pgsql"}:
        raise ValueError(f"Unsupported database scheme: {parsed.scheme}")
    if parsed.username or parsed.password:
        raise ValueError("DATABASE_URL must not include credentials. Use DATABASE_USER and DATABASE_PASSWORD.")

    database_name = unquote(parsed.path.lstrip("/"))
    if not database_name:
        raise ValueError("DATABASE_URL must include a database name.")

    options = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": database_name,
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or ""),
    }

    query = parse_qs(parsed.query)
    if "sslmode" in query and query["sslmode"]:
        options["OPTIONS"] = {"sslmode": query["sslmode"][-1]}

    return options


def resolve_database() -> dict[str, object]:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is required. SQLite is not supported in this project.")

    database_user = os.environ.get("DATABASE_USER", "").strip()
    if not database_user:
        raise RuntimeError("DATABASE_USER is required.")

    database_password = os.environ.get("DATABASE_PASSWORD")
    if database_password is None:
        raise RuntimeError("DATABASE_PASSWORD is required (can be blank).")

    options = parse_database_url(database_url)
    options["USER"] = database_user
    options["PASSWORD"] = database_password
    return options


DEBUG = False
RUNNING_TESTS = "test" in sys.argv
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "").strip()
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = secrets.token_urlsafe(50)
    else:
        raise RuntimeError(
            "DJANGO_SECRET_KEY is required when DJANGO_DEBUG is disabled."
        )
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "http://localhost:8000")
SOCIAL_AUTH_SSO_BACKEND_PATH = os.environ.get(
    "SOCIAL_AUTH_SSO_BACKEND_PATH",
    "social_core.backends.open_id_connect.OpenIdConnectAuth",
).strip()
SOCIAL_AUTH_SSO_BACKEND_NAME = os.environ.get("SOCIAL_AUTH_SSO_BACKEND_NAME", "oidc").strip() or "oidc"
SOCIAL_AUTH_SSO_LOGIN_LABEL = os.environ.get("SOCIAL_AUTH_SSO_LOGIN_LABEL", "Sign in with SSO").strip() or "Sign in with SSO"
SOCIAL_AUTH_ALLOWED_DOMAINS = env_list("SOCIAL_AUTH_ALLOWED_DOMAINS")
SOCIAL_AUTH_ALLOWED_EMAILS = env_list("SOCIAL_AUTH_ALLOWED_EMAILS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "social_django",
    "portal",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "portal.csp.NonceContentSecurityPolicyMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "social_django.middleware.SocialAuthExceptionMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "portal_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "social_django.context_processors.backends",
                "social_django.context_processors.login_redirect",
                "portal.csp.csp_nonce_context",
            ],
        },
    },
]

WSGI_APPLICATION = "portal_backend.wsgi.application"
ASGI_APPLICATION = "portal_backend.asgi.application"

DATABASES = {"default": resolve_database()}
AUTHENTICATION_BACKENDS = [
    SOCIAL_AUTH_SSO_BACKEND_PATH,
    "django.contrib.auth.backends.ModelBackend",
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"
LOGIN_ERROR_URL = "/login/"
SOCIAL_AUTH_LOGIN_URL = LOGIN_URL
SOCIAL_AUTH_LOGIN_REDIRECT_URL = LOGIN_REDIRECT_URL
SOCIAL_AUTH_LOGIN_ERROR_URL = LOGIN_ERROR_URL
SOCIAL_AUTH_URL_NAMESPACE = "social"
SOCIAL_AUTH_REQUIRE_POST = True
SOCIAL_AUTH_SANITIZE_REDIRECTS = True
SOCIAL_AUTH_REDIRECT_IS_HTTPS = env_bool("SOCIAL_AUTH_REDIRECT_IS_HTTPS", default=False)
SOCIAL_AUTH_JSONFIELD_ENABLED = True
SOCIAL_AUTH_RAISE_EXCEPTIONS = False
SOCIAL_AUTH_UID_LENGTH = 223
SOCIAL_AUTH_USERNAME_IS_FULL_EMAIL = True
SOCIAL_AUTH_FORCE_EMAIL_LOWERCASE = True
SOCIAL_AUTH_PROTECTED_USER_FIELDS = ["email"]
SOCIAL_AUTH_IMMUTABLE_USER_FIELDS = ["email"]

if SOCIAL_AUTH_SSO_BACKEND_NAME == "oidc":
    SOCIAL_AUTH_OIDC_OIDC_ENDPOINT = os.environ.get("SOCIAL_AUTH_OIDC_OIDC_ENDPOINT", "").strip()
    SOCIAL_AUTH_OIDC_KEY = os.environ.get("SOCIAL_AUTH_OIDC_KEY", "").strip()
    SOCIAL_AUTH_OIDC_SECRET = os.environ.get("SOCIAL_AUTH_OIDC_SECRET", "").strip()
    SOCIAL_AUTH_OIDC_SCOPE = env_list("SOCIAL_AUTH_OIDC_SCOPE", "openid,profile,email")
    oidc_username_key = os.environ.get("SOCIAL_AUTH_OIDC_USERNAME_KEY", "").strip()
    if oidc_username_key:
        SOCIAL_AUTH_OIDC_USERNAME_KEY = oidc_username_key

backend_settings_prefix = SOCIAL_AUTH_SSO_BACKEND_NAME.upper().replace("-", "_")
if SOCIAL_AUTH_ALLOWED_DOMAINS:
    globals()[f"SOCIAL_AUTH_{backend_settings_prefix}_WHITELISTED_DOMAINS"] = SOCIAL_AUTH_ALLOWED_DOMAINS
if SOCIAL_AUTH_ALLOWED_EMAILS:
    globals()[f"SOCIAL_AUTH_{backend_settings_prefix}_WHITELISTED_EMAILS"] = SOCIAL_AUTH_ALLOWED_EMAILS

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "webapp"]
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", default=not RUNNING_TESTS)
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", default=not RUNNING_TESTS)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", default=not RUNNING_TESTS)
SECURE_HSTS_SECONDS = max(0, env_int("SECURE_HSTS_SECONDS", 31536000 if not RUNNING_TESTS else 0))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=SECURE_HSTS_SECONDS > 0 and not RUNNING_TESTS,
)
SECURE_HSTS_PRELOAD = env_bool(
    "SECURE_HSTS_PRELOAD",
    default=SECURE_HSTS_SECONDS > 0 and not RUNNING_TESTS,
)
SECURE_CONTENT_TYPE_NOSNIFF = env_bool("SECURE_CONTENT_TYPE_NOSNIFF", default=True)
SECURE_REFERRER_POLICY = os.environ.get("SECURE_REFERRER_POLICY", "strict-origin-when-cross-origin").strip()

# Keep upload payloads bounded and configurable per endpoint.
FILE_UPLOAD_MAX_MEMORY_SIZE = max(1024, env_int("FILE_UPLOAD_MAX_MEMORY_SIZE", 2621440))
DATA_UPLOAD_MAX_MEMORY_SIZE = max(
    FILE_UPLOAD_MAX_MEMORY_SIZE,
    env_int("DATA_UPLOAD_MAX_MEMORY_SIZE", 20971520),
)
POLICY_UPLOAD_MAX_FILE_BYTES = max(1024, env_int("POLICY_UPLOAD_MAX_FILE_BYTES", 2097152))
MAPPING_UPLOAD_MAX_FILE_BYTES = max(1024, env_int("MAPPING_UPLOAD_MAX_FILE_BYTES", 5242880))
VENDOR_UPLOAD_MAX_FILE_BYTES = max(1024, env_int("VENDOR_UPLOAD_MAX_FILE_BYTES", 10485760))
POLICY_UPLOAD_MAX_FILES = max(1, env_int("POLICY_UPLOAD_MAX_FILES", 20))
VENDOR_UPLOAD_MAX_FILES = max(1, env_int("VENDOR_UPLOAD_MAX_FILES", 25))
UPLOAD_SCANNING_ENABLED = env_bool("UPLOAD_SCANNING_ENABLED", default=True)

LOGIN_THROTTLE_MAX_ATTEMPTS = max(1, env_int("LOGIN_THROTTLE_MAX_ATTEMPTS", 5))
LOGIN_THROTTLE_WINDOW_SECONDS = max(60, env_int("LOGIN_THROTTLE_WINDOW_SECONDS", 900))
LOGIN_THROTTLE_LOCKOUT_SECONDS = max(60, env_int("LOGIN_THROTTLE_LOCKOUT_SECONDS", 900))

ASSESSMENT_WORKER_POLL_INTERVAL_SECONDS = max(
    1,
    int(os.environ.get("ASSESSMENT_WORKER_POLL_INTERVAL_SECONDS", "10")),
)
ASSESSMENT_WORKER_LEASE_SECONDS = max(
    60,
    int(os.environ.get("ASSESSMENT_WORKER_LEASE_SECONDS", "900")),
)
ASSESSMENT_STORAGE_ROOT = os.environ.get("ASSESSMENT_STORAGE_ROOT", "").strip()
ASSESSMENT_CERTIFICATE_ROOT = os.environ.get("ASSESSMENT_CERTIFICATE_ROOT", "").strip()
ASSESSMENT_STAGING_ROOT = os.environ.get("ASSESSMENT_STAGING_ROOT", "").strip()
ASSESSMENT_PFX_PASSWORD_CREDENTIAL_NAME = (
    os.environ.get("ASSESSMENT_PFX_PASSWORD_CREDENTIAL_NAME", "assessment-pfx-password").strip()
    or "assessment-pfx-password"
)
ASSESSMENT_PFX_PASSWORD_FILE = os.environ.get("ASSESSMENT_PFX_PASSWORD_FILE", "").strip()
