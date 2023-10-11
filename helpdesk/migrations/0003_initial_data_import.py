# -*- coding: utf-8 -*-
from django.db import migrations

# Email templates are created during create_organization, removing the need for this migration.

class Migration(migrations.Migration):

    dependencies = [
        ('helpdesk', '0002_populate_usersettings'),
    ]

    operations = [
        migrations.RunPython(migrations.RunPython.noop, migrations.RunPython.noop),
    ]
