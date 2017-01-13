# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('helpdesk', '0013_email_box_local_dir_and_logging'),
    ]

    operations = [
        migrations.AlterField(
            model_name='usersettings',
            name='user',
            field=models.OneToOneField(to=settings.AUTH_USER_MODEL, related_name='usersettings_helpdesk'),
        ),
    ]
