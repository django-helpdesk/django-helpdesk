# -*- coding: utf-8 -*-
from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('helpdesk', '0032_kbitem_enabled'),
    ]

    operations = [
        migrations.AlterField(
            model_name='CustomField',
            name='data_type',
            field = models.CharField(choices=[('varchar', 'Character (single line)'), ('text', 'Text (multi-line)'), ('integer', 'Integer'), ('decimal', 'Decimal'), ('list', 'List'), ('boolean', 'Boolean (checkbox yes/no)'), ('date', 'Date'), ('time', 'Time'), ('datetime', 'Date & Time'), ('email', 'E-Mail Address'), ('url', 'URL'), ('ipaddress', 'IP Address'), ('slug', 'Slug'), ('htmlmulti', 'HTML multi-line')], verbose_name='Data Type', help_text='Allows you to restrict the data entered into this field', max_length=100)
        ),
    ]

