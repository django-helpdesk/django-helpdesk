# -*- coding: utf-8 -*-
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('helpdesk', '0006_email_maxlength'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customfield',
            name='label',
            field=models.CharField(help_text='The display label for this field', max_length=30, verbose_name='Label'),
        ),
    ]
