# Generated by Django 3.2.7 on 2022-03-07 15:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orgs', '0027_organization_helpdesk_organization'),
        ('helpdesk', '0051_alter_kbitem_answer'),
    ]

    operations = [
        migrations.AlterField(
            model_name='kbcategory',
            name='slug',
            field=models.SlugField(unique=True, verbose_name='Slug'),
        ),
        migrations.AlterField(
            model_name='queue',
            name='slug',
            field=models.SlugField(help_text="This slug is used when building ticket ID's. Once set, try not to change it or e-mailing may get messy.", verbose_name='Slug'),
        ),
        migrations.AlterUniqueTogether(
            name='queue',
            unique_together={('organization', 'slug')},
        ),
    ]