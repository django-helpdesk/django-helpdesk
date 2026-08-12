import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = True
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": Path(BASE_DIR / "test.db"),
        "USER": "",
        "PASSWORD": "",
        "HOST": "",
        "PORT": "",
    }
}
INSTALLED_APPS = (
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.humanize",
    "django.contrib.messages",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.staticfiles",
    "bootstrap4form",
    "rest_framework",
    "helpdesk",
)

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": (
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.debug",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.request",
            ),
        },
    },
]

LOGIN_URL = "/login/"
ROOT_URLCONF = "tests.urls"
SECRET_KEY = "wowdonotusethisfakesecuritykeyyouneedarealsecure1"
STATIC_URL = "/static/"
SITE_ID = 1
TIME_ZONE = "UTC"

# For speed
PASSWORD_HASHERS = ("django.contrib.auth.hashers.MD5PasswordHasher",)

# Helpdesk specific settings
# The following settings disable teams
HELPDESK_TEAMS_MODEL = "auth.User"
HELPDESK_TEAMS_MIGRATION_DEPENDENCIES = []
HELPDESK_KBITEM_TEAM_GETTER = lambda _: None
# Set IMAP Server Debug Verbosity
HELPDESK_IMAP_DEBUG_LEVEL = int(os.environ.get("HELPDESK_IMAP_DEBUG_LEVEL", "0"))
