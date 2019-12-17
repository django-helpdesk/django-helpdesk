# -*- coding: utf-8 -*-
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
        migrations.DeleteModel(
            name='QueueMembership',
        ),
    ]
