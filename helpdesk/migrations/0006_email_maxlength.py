# -*- coding: utf-8 -*-
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('helpdesk', '0005_queues_no_null'),
    ]

    operations = [
        migrations.AlterField(
            model_name='queue',
            name='email_address',
            field=models.EmailField(help_text='All outgoing e-mails for this queue will use this e-mail address. If you use IMAP or POP3, this should be the e-mail address for that mailbox.', max_length=254, null=True, verbose_name='E-Mail Address', blank=True),
        ),
        migrations.AlterField(
            model_name='ticket',
            name='submitter_email',
            field=models.EmailField(help_text='The submitter will receive an email for all public follow-ups left for this task.', max_length=254, null=True, verbose_name='Submitter E-Mail', blank=True),
        ),
        migrations.AlterField(
            model_name='ticketcc',
            name='email',
            field=models.EmailField(help_text='For non-user followers, enter their e-mail address', max_length=254, null=True, verbose_name='E-Mail Address', blank=True),
        ),
    ]
