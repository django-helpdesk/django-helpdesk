# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('helpdesk', '0003_initial_data_import'),
    ]

    operations = [
        migrations.CreateModel(
            name='QueueMembership',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('queues', models.ManyToManyField(to='helpdesk.Queue', verbose_name='Authorized Queues')),
                ('user', models.OneToOneField(verbose_name='User', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Queue Membership',
                'verbose_name_plural': 'Queue Memberships',
            },
            bases=(models.Model,),
        ),
    ]
