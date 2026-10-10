from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from helpdesk.models import Queue, Ticket


class TicketTemplateExtensionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user("panel-agent", is_staff=True)
        cls.ticket = Ticket.objects.create(
            queue=Queue.objects.create(title="Support", slug="panel-support"),
            title="Printer connection",
        )

    def setUp(self):
        self.client.force_login(self.user)
        self.url = reverse("helpdesk:view", args=[self.ticket.pk])

    def test_same_name_override_adds_panel_and_inherits_existing_page(self):
        with TemporaryDirectory() as directory:
            template = Path(directory) / "helpdesk" / "ticket.html"
            template.parent.mkdir()
            template.write_text(
                '{% extends "helpdesk/ticket.html" %}'
                "{% block helpdesk_ticket_panels %}{{ block.super }}"
                '<section id="extension-panel">Ticket {{ ticket.id }}: '
                "</section>{% endblock %}",
                encoding="utf-8",
            )
            template_settings = [{**settings.TEMPLATES[0], "DIRS": [directory]}]
            with override_settings(TEMPLATES=template_settings):
                response = self.client.get(self.url)
                self.assertContains(response, 'id="extension-panel"')
                self.assertContains(response, self.ticket.title)
