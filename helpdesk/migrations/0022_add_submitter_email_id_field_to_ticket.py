# -*- coding: utf-8 -*-
# Generated by Django 1.9.1 on 2016-02-07 19:51
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("helpdesk", "0021_voting_tracker"),
    ]

    operations = [
        migrations.AddField(
            model_name="followup",
            name="message_id",
            field=models.CharField(
                blank=True,
                editable=False,
                help_text="The Message ID of the submitter's email.",
                max_length=256,
                null=True,
                verbose_name="E-Mail ID",
            ),
        ),
    ]
