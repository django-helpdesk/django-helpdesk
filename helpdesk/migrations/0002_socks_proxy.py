# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('helpdesk', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='queue',
            name='socks_proxy_host',
            field=models.GenericIPAddressField(help_text='Socks proxy IP address. Default: 127.0.0.1', null=True, verbose_name='Socks Proxy Host', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='queue',
            name='socks_proxy_port',
            field=models.IntegerField(help_text='Socks proxy port number. Default: 9150 (default TOR port)', null=True, verbose_name='Socks Proxy Port', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='queue',
            name='socks_proxy_type',
            field=models.CharField(choices=[(b'socks4', 'SOCKS4'), (b'socks5', 'SOCKS5')], max_length=8, blank=True, help_text='SOCKS4 or SOCKS5 allows you to proxy your connections through a SOCKS server.', null=True, verbose_name='Socks Proxy Type'),
            preserve_default=True,
        ),
    ]
