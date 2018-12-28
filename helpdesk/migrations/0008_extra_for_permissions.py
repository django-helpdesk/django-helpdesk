# -*- coding: utf-8 -*-
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('helpdesk', '0007_max_length_by_integer'),
    ]

    operations = [
        migrations.AddField(
            model_name='queue',
            name='permission_name',
            field=models.CharField(help_text='Name used in the django.contrib.auth permission system', max_length=50, null=True, verbose_name='Django auth permission name', blank=True),
        ),
    ]
