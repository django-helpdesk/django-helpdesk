"""
Django settings for django-helpdesk demodesk project.

For more information on this file, see
https://docs.djangoproject.com/en/1.11/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.11/ref/settings/
"""


import os


# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.11/howto/deployment/checklist/

# Read SECRET_KEY from DJANGO_HELPDESK_SECRET_KEY env var
try:
    SECRET_KEY = os.environ['DJANGO_HELPDESK_SECRET_KEY']
except KeyError:
    raise Exception("DJANGO_HELPDESK_SECRET_KEY environment variable is not set")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = os.environ.get("DJANGO_HELPDESK_ALLOWED_HOSTS", "*, localhost, 0.0.0.0").split(",")

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.contrib.humanize',
    'bootstrap4form',
    'account',  # Required by pinax-teams
    'pinax.invitations',  # required by pinax-teams
    'pinax.teams',  # team support
    'reversion',  # required by pinax-teams
    'helpdesk',  # This is us!
    'rest_framework',  # required for the API
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    "whitenoise.middleware.WhiteNoiseMiddleware",
]

ROOT_URLCONF = 'standalone.config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'debug': True,
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'standalone.config.wsgi.application'


# django-helpdesk configuration settings
# You can override django-helpdesk's defaults by redefining them here.
# To see what settings are available, see the docs/configuration.rst
# file for more information.
# Some common settings are below.

HELPDESK_DEFAULT_SETTINGS = {
    'use_email_as_submitter': os.environ.get('HELPDESK_USE_EMAIL_AS_SUBMITTER', 'True') == 'True',
    'email_on_ticket_assign': os.environ.get('HELPDESK_EMAIL_ON_TICKET_ASSIGN', 'True') == 'True',
    'email_on_ticket_change': os.environ.get('HELPDESK_EMAIL_ON_TICKET_CHANGE', 'True') == 'True',
    'login_view_ticketlist': os.environ.get('HELPDESK_LOGIN_VIEW_TICKETLIST', 'True') == 'True',
    'email_on_ticket_apichange': os.environ.get('HELPDESK_EMAIL_ON_TICKET_APICHANGE', 'True') == 'True',
    'preset_replies': os.environ.get('HELPDESK_PRESET_REPLIES', 'True') == 'True',
    'tickets_per_page': os.environ.get('HELPDESK_TICKETS_PER_PAGE', '25'),
}

# Should the public web portal be enabled?
HELPDESK_PUBLIC_ENABLED = os.environ.get('HELPDESK_PUBLIC_ENABLED', 'True') == 'True'
HELPDESK_VIEW_A_TICKET_PUBLIC = os.environ.get('HELPDESK_VIEW_A_TICKET_PUBLIC', 'True') == 'True'
HELPDESK_SUBMIT_A_TICKET_PUBLIC = os.environ.get('HELPDESK_SUBMIT_A_TICKET_PUBLIC', 'True') == 'True'

# Should the Knowledgebase be enabled?
HELPDESK_KB_ENABLED = os.environ.get('HELPDESK_KB_ENABLED', 'True') == 'True'

HELPDESK_TICKETS_TIMELINE_ENABLED = os.environ.get('HELPDESK_TICKETS_TIMELINE_ENABLED', 'True') == 'True'

# Allow users to change their passwords
HELPDESK_SHOW_CHANGE_PASSWORD = os.environ.get('HELPDESK_SHOW_CHANGE_PASSWORD', 'True') == 'True'

# Instead of showing the public web portal first,
# we can instead redirect users straight to the login page.
HELPDESK_REDIRECT_TO_LOGIN_BY_DEFAULT = os.environ.get('HELPDESK_REDIRECT_TO_LOGIN_BY_DEFAULT', 'False') == 'True'
LOGIN_URL = 'helpdesk:login'
LOGIN_REDIRECT_URL = 'helpdesk:home'


DATABASES = {
  # Setup postgress db with postgres as host and db name and read password from env var
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'postgres'),
        'USER': os.environ.get('POSTGRES_USER', 'postgres'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'postgres'),
        'HOST': os.environ.get('POSTGRES_HOST', 'postgres'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
    }
}


# Sites
# - this allows hosting of more than one site from a single server,
#   in practice you can probably just leave this default if you only
#   host a single site, but read more in the docs:
# https://docs.djangoproject.com/en/1.11/ref/contrib/sites/

SITE_ID = 1


# Sessions
# https://docs.djangoproject.com/en/1.11/topics/http/sessions

SESSION_COOKIE_AGE = 86400  # = 1 day

# Password validation
# https://docs.djangoproject.com/en/1.11/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Email
# https://docs.djangoproject.com/en/1.11/topics/email/

# This demo uses the console backend, which simply prints emails to the console
# rather than actually sending them out.
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'example@example.com')
SERVER_EMAIL = os.environ.get('SERVER_EMAIL', 'example@example.com')

if os.environ.get('EMAIL_HOST', None):
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    try:
        EMAIL_HOST = os.environ['EMAIL_HOST']
    except KeyError:
        raise ImproperlyConfigured('Please set the EMAIL_HOST environment variable.')
    try:
        EMAIL_PORT = os.environ['EMAIL_PORT']
    except KeyError:
        raise ImproperlyConfigured('Please set the EMAIL_PORT environment variable.')
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Internationalization
# https://docs.djangoproject.com/en/1.11/topics/i18n/

# By default, django-helpdesk uses en, but other languages are also available.
# The most complete translations are: es-MX, ru, zh-Hans
# Contribute to our translations via Transifex if you can!
# See CONTRIBUTING.rst for more info.
LANGUAGE_CODE = 'en-US'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.11/howto/static-files/
def normpath(*args):
    return os.path.normpath(os.path.abspath(os.path.join(*args)))


PROJECT_ROOT = normpath(__file__, "..", "..")
STATIC_ROOT = os.environ.get("DJANGO_HELPDESK_STATIC_ROOT", normpath(PROJECT_ROOT, "static"))
STATIC_URL = os.environ.get("DJANGO_HELPDESK_STATIC_URL", "/static/")


# MEDIA_ROOT is where media uploads are stored.
# We set this to a directory to host file attachments created
# with tickets.
MEDIA_URL = '/media/'
MEDIA_ROOT = '/data/media'

# for Django 3.2+, set default for autofields:
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'ERROR',  # Change to 'DEBUG' if you want to print all debug messages as well
            'propagate': True,
        },
    },
}
