# Generated by Django 2.2.13 on 2020-06-25 07:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('helpdesk', '0023_auto_20200624_1754'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='billing',
            field=models.PositiveSmallIntegerField(blank=True, choices=[(1, 'Contrat de maintenance'), (2, 'Carnet de jeton'), (3, 'Devis'), (4, 'Offert'), (5, 'Facturation à tort')], default=1, null=True, verbose_name='facturation'),
        ),
    ]