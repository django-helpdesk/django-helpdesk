# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
from sys import path

from django.db import models, migrations
from django.core import serializers

fixture_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../fixtures'))
fixture_filename = 'emailtemplate.json'

def deserialize_fixture():
    fixture_file = os.path.join(fixture_dir, fixture_filename)

    with open(fixture_file, 'rb') as fixture:
        return list(serializers.deserialize('json', fixture, ignorenonexistent=True))


def load_fixture(apps, schema_editor):
    objects = deserialize_fixture()

    for obj in objects:
        obj.save()


def unload_fixture(apps, schema_editor):
    "Delete all EmailTemplate objects"

    objects = deserialize_fixture()

    EmailTemplate = apps.get_model("helpdesk", "emailtemplate")
    EmailTemplate.objects.filter(pk__in=[ obj.object.pk for obj in objects ]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('helpdesk', '0002_populate_usersettings'),
    ]

    operations = [
        migrations.RunPython(load_fixture, reverse_code=unload_fixture),
    ]
