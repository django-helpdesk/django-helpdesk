"""
When only a single queue is configured, there is nothing meaningful for a
user to choose, so the queue selector should be hidden (and default to that
queue) rather than shown as a single-option dropdown.

See: https://github.com/django-helpdesk/django-helpdesk/issues/289
"""

from django import forms
from django.test import TestCase
from django.urls import reverse

from helpdesk.forms import EditTicketForm, TicketForm
from helpdesk.models import Queue, Ticket

from .helpers import get_staff_user


class TicketFormSingleQueueTestCase(TestCase):
    def test_queue_hidden_when_only_one_choice(self):
        form = TicketForm(queue_choices=[(1, "Products")])
        self.assertIsInstance(form.fields["queue"].widget, forms.HiddenInput)
        self.assertEqual(form.fields["queue"].initial, 1)

    def test_queue_shown_when_multiple_choices(self):
        form = TicketForm(
            queue_choices=[("", "--------"), (1, "Products"), (2, "Support")]
        )
        self.assertNotIsInstance(form.fields["queue"].widget, forms.HiddenInput)


class EditTicketFormSingleQueueTestCase(TestCase):
    def test_queue_hidden_when_only_one_queue_exists(self):
        queue = Queue.objects.create(title="Products", slug="products")
        ticket = Ticket.objects.create(
            title="Test ticket", submitter_email="test@example.com", queue=queue
        )
        form = EditTicketForm(instance=ticket)
        self.assertIsInstance(form.fields["queue"].widget, forms.HiddenInput)
        self.assertEqual(form.fields["queue"].initial, queue.pk)

    def test_queue_shown_when_multiple_queues_exist(self):
        queue = Queue.objects.create(title="Products", slug="products")
        Queue.objects.create(title="Support", slug="support")
        ticket = Ticket.objects.create(
            title="Test ticket", submitter_email="test@example.com", queue=queue
        )
        form = EditTicketForm(instance=ticket)
        self.assertNotIsInstance(form.fields["queue"].widget, forms.HiddenInput)


class TicketDetailQueueFieldTestCase(TestCase):
    def setUp(self):
        self.user = get_staff_user()
        self.client.login(username=self.user.username, password="password")

    def test_queue_select_hidden_with_single_queue(self):
        queue = Queue.objects.create(title="Products", slug="products")
        ticket = Ticket.objects.create(
            title="Test ticket", submitter_email="test@example.com", queue=queue
        )
        response = self.client.get(reverse("helpdesk:view", args=[ticket.id]))
        html = response.content.decode()
        self.assertIn(
            f'<input type="hidden" id="id_queue" name="queue" value="{queue.id}"', html
        )
        self.assertNotIn('<select class="form-select" id="id_queue"', html)

    def test_queue_select_shown_with_multiple_queues(self):
        queue = Queue.objects.create(title="Products", slug="products")
        Queue.objects.create(title="Support", slug="support")
        ticket = Ticket.objects.create(
            title="Test ticket", submitter_email="test@example.com", queue=queue
        )
        response = self.client.get(reverse("helpdesk:view", args=[ticket.id]))
        html = response.content.decode()
        self.assertIn('<select class="form-select" id="id_queue" name="queue">', html)
