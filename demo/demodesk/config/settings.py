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

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '_crkn1+fnzu5$vns_-d+^ayiq%z4k*s!!ag0!mfy36(y!vrazd'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

# SECURITY WARNING: you probably want to configure your server
# to use HTTPS with secure cookies, then you'd want to set
# the following settings:
#
#SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
#SESSION_COOKIE_SECURE = True
#CSRF_COOKIE_SECURE = True
#
# We leave them commented out here because most likely for
# an internal demo you don't need such security, but please
# remember when setting up your own development / production server!


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
]

ROOT_URLCONF = 'demo.demodesk.config.urls'

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

WSGI_APPLICATION = 'demo.demodesk.config.wsgi.application'


# django-helpdesk configuration settings
# You can override django-helpdesk's defaults by redefining them here.
# To see what settings are available, see the docs/configuration.rst
# file for more information.
# Some common settings are below.

HELPDESK_DEFAULT_SETTINGS = {
            'use_email_as_submitter': True,
            'email_on_ticket_assign': True,
            'email_on_ticket_change': True,
            'login_view_ticketlist': True,
            'email_on_ticket_apichange': True,
            'preset_replies': True,
            'tickets_per_page': 25
}

# Should the public web portal be enabled?
HELPDESK_PUBLIC_ENABLED = True
HELPDESK_VIEW_A_TICKET_PUBLIC = True
HELPDESK_SUBMIT_A_TICKET_PUBLIC = True

# Should the Knowledgebase be enabled?
HELPDESK_KB_ENABLED = True

HELPDESK_TICKETS_TIMELINE_ENABLED = True

# Allow users to change their passwords
HELPDESK_SHOW_CHANGE_PASSWORD = True

# Activate the API
HELPDESK_ACTIVATE_API_ENDPOINT = True

# Instead of showing the public web portal first,
# we can instead redirect users straight to the login page.
HELPDESK_REDIRECT_TO_LOGIN_BY_DEFAULT = False
LOGIN_URL = 'helpdesk:login'
LOGIN_REDIRECT_URL = 'helpdesk:home'

# Database
# - by default, we use SQLite3 for the demo, but you can also
#   configure MySQL or PostgreSQL, see the docs for more:
# https://docs.djangoproject.com/en/1.11/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
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

SESSION_COOKIE_AGE = 86400 # = 1 day

# For better default security, set these cookie flags, but
# these are likely to cause problems when testing locally
#CSRF_COOKIE_SECURE = True
#SESSION_COOKIE_SECURE = True
#CSRF_COOKIE_HTTPONLY = True
#SESSION_COOKIE_HTTPONLY = True


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
DEFAULT_FROM_EMAIL = 'helpdesk@example.com'
SERVER_EMAIL = 'helpdesk@example.com'
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# If you want to test sending real emails, uncomment and modify the following:
#EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
#EMAIL_HOST = 'smtp.example.com'
#EMAIL_PORT = '25'

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

STATIC_URL = '/static/'
# static root needs to be defined in order to use collectstatic
STATIC_ROOT = os.path.join(BASE_DIR, 'static')

# MEDIA_ROOT is where media uploads are stored.
# We set this to a directory to host file attachments created
# with tickets.
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Fixtures
# https://docs.djangoproject.com/en/1.11/ref/settings/#std:setting-FIXTURE_DIRS
# - This is only necessary to make the demo project work, not needed for
# your own projects unless you make your own fixtures
FIXTURE_DIRS = [os.path.join(BASE_DIR, 'fixtures')]


# for Django 3.2+, set default for autofields:
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

try:
    from .local_settings import *
except ImportError:
    pass
