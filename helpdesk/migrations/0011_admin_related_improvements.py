# -*- coding: utf-8 -*-
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('helpdesk', '0010_remove_queuemembership'),
    ]

    operations = [
        migrations.AlterField(
            model_name='queue',
            name='permission_name',
            field=models.CharField(editable=False, max_length=50, blank=True, help_text='Name used in the django.contrib.auth permission system', null=True, verbose_name='Django auth permission name'),
        ),
        migrations.AlterField(
            model_name='queue',
            name='slug',
            field=models.SlugField(help_text="This slug is used when building ticket ID's. Once set, try not to change it or e-mailing may get messy.", unique=True, verbose_name='Slug'),
        ),
    ]
