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
        'bootstrapform',
    )
    MIDDLEWARE_CLASSES = [
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
        self.apps = args
        # Get the version of the test suite
        self.version = self.get_test_version()
        # Call the appropriate one
        if self.version == 'new':
            self._new_tests()
        else:
            self._old_tests()

    def get_test_version(self):
        """
        Figure out which version of Django's test suite we have to play with.
        """
        if django.VERSION >= (1, 2):
            return 'new'
        else:
            return 'old'

    def _old_tests(self):
        """
        Fire up the Django test suite from before version 1.2
        """
        settings.configure(DEBUG=True,
                           DATABASE_ENGINE='sqlite3',
                           DATABASE_NAME=os.path.join(self.DIRNAME, 'database.db'),
                           INSTALLED_APPS=self.INSTALLED_APPS + self.apps
                           )
        from django.test.simple import run_tests
        failures = run_tests(self.apps, verbosity=1)
        if failures:
            sys.exit(failures)

    def _new_tests(self):
        """
        Fire up the Django test suite developed for version 1.2
        """

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
            INSTALLED_APPS=self.INSTALLED_APPS + self.apps,
            MIDDLEWARE_CLASSES=self.MIDDLEWARE_CLASSES,
            ROOT_URLCONF='helpdesk.tests.urls',
            STATIC_URL='/static/',
            TEMPLATES=self.TEMPLATES
        )

        # compatibility with django 1.8 downwards
        # see: http://stackoverflow.com/questions/3841725/how-to-launch-tests-for-django-reusable-app

        try:
            # Django >= 1.6
            from django.test.runner import DiscoverRunner
            test_runner = DiscoverRunner(verbosity=1)
        except ImportError:
            # Django <= 1.5
            from django.test.simple import DjangoTestSuiteRunner
            test_runner = DjangoTestSuiteRunner(verbosity=1)

        if django.VERSION >= (1, 7):
            django.setup()

        failures = test_runner.run_tests(self.apps)
        if failures:
            sys.exit(failures)

if __name__ == '__main__':
    """
    What do when the user hits this file from the shell.

    Example usage:

        $ python quicktest.py app1 app2

    """
    parser = argparse.ArgumentParser(
        usage="[args]",
        description="Run Django tests on the provided applications."
    )
    parser.add_argument('apps', nargs='+', type=str)
    args = parser.parse_args()
    QuickDjangoTest(*args.apps)
