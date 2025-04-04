# Generated by Django 2.2.10 on 2020-02-25 11:21

from django.db import migrations, models


def copy_title(apps, schema_editor):
    KBCategory = apps.get_model("helpdesk", "KBCategory")
    KBCategory.objects.update(name=models.F("title"))


class Migration(migrations.Migration):
    dependencies = [
        ("helpdesk", "0029_kbcategory_public"),
    ]

    operations = [
        migrations.AddField(
            model_name="kbcategory",
            name="name",
            field=models.CharField(
                blank=True,
                max_length=100,
                null=True,
                verbose_name="Name of the category",
            ),
        ),
        migrations.AlterField(
            model_name="kbcategory",
            name="title",
            field=models.CharField(
                max_length=100, verbose_name="Title on knowledgebase page"
            ),
        ),
        migrations.RunPython(copy_title, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="kbcategory",
            name="name",
            field=models.CharField(
                blank=False,
                max_length=100,
                null=False,
                verbose_name="Name of the category",
            ),
        ),
    ]
