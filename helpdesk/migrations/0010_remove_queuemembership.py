# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('helpdesk', '0009_migrate_queuemembership'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='queuemembership',
            name='queues',
        ),
        migrations.RemoveField(
            model_name='queuemembership',
            name='user',
        ),
        migrations.AddField(
            model_name='queue',
            name='permission_name',
            field=models.CharField(help_text='Name used in the django.contrib.auth permission system', max_length=50, null=True, verbose_name='Django auth permission name', blank=True),
        ),
        migrations.DeleteModel(
            name='QueueMembership',
        ),
    ]
