from django.db import migrations


def add_reopened_email_templates(apps, schema_editor):
    EmailTemplate = apps.get_model("helpdesk", "EmailTemplate")

    for template in EmailTemplate.objects.filter(
        template_name__in=["updated_cc", "updated_owner", "updated_submitter"]
    ):
        EmailTemplate.objects.get_or_create(
            template_name=template.template_name.replace("updated_", "reopened_"),
            locale=template.locale,
            defaults={
                "subject": template.subject.replace("(Updated)", "(Reopened)"),
                "heading": template.heading.replace("Updated", "Reopened"),
                "plain_text": template.plain_text.replace("Updated", "Reopened").replace(
                    "updated", "reopened"
                ),
                "html": template.html.replace("Updated", "Reopened").replace(
                    "updated", "reopened"
                ),
            },
        )


def remove_reopened_email_templates(apps, schema_editor):
    EmailTemplate = apps.get_model("helpdesk", "EmailTemplate")
    EmailTemplate.objects.filter(
        template_name__in=["reopened_cc", "reopened_owner", "reopened_submitter"]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("helpdesk", "0043_fix_on_delete_behaviour"),
    ]

    operations = [
        migrations.RunPython(
            add_reopened_email_templates,
            remove_reopened_email_templates,
        ),
    ]
