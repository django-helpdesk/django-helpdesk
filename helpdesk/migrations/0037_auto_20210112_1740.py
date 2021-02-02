# Generated by Django 2.2.17 on 2021-01-12 16:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('helpdesk', '0036_genericincident_subscribers'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ticket',
            name='link_open',
            field=models.URLField(blank=True, help_text='Lien depuis lequel le ticket a été ouvert.', max_length=300, null=True),
        ),
    ]