
import datetime
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.test import TestCase
from django.test.client import Client
from helpdesk.models import FollowUp, Queue, Ticket
from helpdesk import settings as helpdesk_settings
import uuid


class TimeSpentAutoTestCase(TestCase):

    def setUp(self):
        """Creates a queue, ticket and user."""
        self.queue_public = Queue.objects.create(
            title='Queue 1',
            slug='q1',
            allow_public_submission=True,
            dedicated_time=datetime.timedelta(minutes=60)
        )

        self.ticket_data = {
            'title': 'Test Ticket',
            'description': 'Some Test Ticket',
        }

        ticket_data = dict(queue=self.queue_public, **self.ticket_data)
        self.ticket = Ticket.objects.create(**ticket_data)

        self.client = Client()

        user1_kwargs = {
            'username': 'staff',
            'email': 'staff@example.com',
            'password': make_password('Test1234'),
            'is_staff': True,
            'is_superuser': False,
            'is_active': True
        }
        self.user = User.objects.create(**user1_kwargs)
    
    def test_add_followup_time_spent_auto(self):
        """Tests automatic time_spent calculation."""

        helpdesk_settings.FOLLOWUP_TIME_SPENT_AUTO = True

        message_id = uuid.uuid4().hex
        followup = FollowUp.objects.create(
            ticket=self.ticket,
            date=self.ticket.created + datetime.timedelta(minutes=30),
            title="Testing followup",
            comment="Testing followup time spent",
            public=True,
            user=self.user,
            new_status=1,
            message_id=message_id,
            time_spent=None
        )
        followup.save()

        self.assertEqual(followup.time_spent.seconds, 1800)
        self.assertEqual(self.ticket.time_spent.seconds, 1800)
        self.assertEqual(self.queue_public.time_spent.seconds, 1800)
        self.assertTrue(
            self.queue_public.dedicated_time.seconds > self.queue_public.time_spent.seconds
        )