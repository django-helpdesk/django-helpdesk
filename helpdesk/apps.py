from django.apps import AppConfig


class HelpdeskConfig(AppConfig):
    name = 'helpdesk'
    verbose_name = "Helpdesk"
    # for Django 3.2 support:
    # see:
    # https://docs.djangoproject.com/en/3.2/ref/applications/#django.apps.AppConfig.default_auto_field
    default_auto_field = 'django.db.models.AutoField'
