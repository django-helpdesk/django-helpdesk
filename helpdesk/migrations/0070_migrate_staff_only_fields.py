# Generated by Django 3.2.12 on 2022-08-10 20:26

from django.db import migrations


def move_staff_only_field(apps, schema_editor):
    CustomField = apps.get_model('helpdesk', 'CustomField')
    fields = CustomField.objects.all()
    for field in fields:
        field.staff = True
        if field.staff_only:
            field.public = False
        else:
            field.public = True
        field.save()


def remove_staff_fields(apps, schema_editor):
    CustomField = apps.get_model('helpdesk', 'CustomField')
    fields = CustomField.objects.all()
    for field in fields:
        if not field.public:
            field.staff_only = True
            field.save()


class Migration(migrations.Migration):

    dependencies = [
        ('helpdesk', '0069_add_staff_and_public_fields'),
    ]

    operations = [
        migrations.RunPython(move_staff_only_field, remove_staff_fields)
    ]
