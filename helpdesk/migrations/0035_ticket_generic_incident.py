# Generated by Django 2.2.13 on 2020-12-23 10:01

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('helpdesk', '0034_genericincident'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='generic_incident',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tickets', to='helpdesk.GenericIncident', verbose_name='inicident générique'),
        ),
    ]