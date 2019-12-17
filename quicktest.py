import os
import sys
import argparse

import django
from django.conf import settings


class QuickDjangoTest(object):
    """
    A quick way to run the Django test suite without a fully-configured project.

    Example usage:

        >>> QuickDjangoTest('app1', 'app2')

    Based on a script published by Lukasz Dziedzia at:
    http://stackoverflow.com/questions/3841725/how-to-launch-tests-for-django-reusable-app
    """
    DIRNAME = os.path.dirname(__file__)
    INSTALLED_APPS = (
        'django.contrib.admin',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.humanize',
        'django.contrib.messages',
        'django.contrib.sessions',
        'django.contrib.sites',
        'django.contrib.staticfiles',
        'bootstrap4form',
        'helpdesk',
    )
    MIDDLEWARE = [
        'django.middleware.security.SecurityMiddleware',
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.middleware.common.CommonMiddleware',
        'django.middleware.csrf.CsrfViewMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'django.contrib.messages.middleware.MessageMiddleware',
        'django.middleware.clickjacking.XFrameOptionsMiddleware',
    ]

    TEMPLATES = [
        {
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'APP_DIRS': True,
            'OPTIONS': {
                'context_processors': (
                    # Defaults:
                    "django.contrib.auth.context_processors.auth",
                    "django.template.context_processors.debug",
                    "django.template.context_processors.i18n",
                    "django.template.context_processors.media",
                    "django.template.context_processors.static",
                    "django.template.context_processors.tz",
                    "django.contrib.messages.context_processors.messages",
                    # Our extra:
                    "django.template.context_processors.request",
                ),
            },
        },
    ]


    def __init__(self, *args, **kwargs):
        self.tests = args
        self._tests()

    def _tests(self):

        settings.configure(
            DEBUG=True,
            DATABASES={
                'default': {
                    'ENGINE': 'django.db.backends.sqlite3',
                    'NAME': os.path.join(self.DIRNAME, 'database.db'),
                    'USER': '',
                    'PASSWORD': '',
                    'HOST': '',
                    'PORT': '',
                }
            },
            INSTALLED_APPS=self.INSTALLED_APPS,
            MIDDLEWARE=self.MIDDLEWARE,
            ROOT_URLCONF='helpdesk.tests.urls',
            STATIC_URL='/static/',
            LOGIN_URL='/helpdesk/login/',
            TEMPLATES=self.TEMPLATES,
            SITE_ID=1
        )

        from django.test.runner import DiscoverRunner
        test_runner = DiscoverRunner(verbosity=1)
        django.setup()

        failures = test_runner.run_tests(self.tests)
        if failures:
            sys.exit(failures)

if __name__ == '__main__':
    """
    What do when the user hits this file from the shell.

    Example usage:

        $ python quicktest.py test1 test2

    """
    parser = argparse.ArgumentParser(
        usage="[args]",
        description="Run Django tests."
    )
    parser.add_argument('tests', nargs="*", type=str)
    args = parser.parse_args()
    if not args.tests:
        args.tests = ['helpdesk']
    QuickDjangoTest(*args.tests)
