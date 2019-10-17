from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core import mail
from django.urls import reverse
from django.test import TestCase
from django.test.client import Client
from helpdesk.models import Queue, Ticket, FollowUp
from helpdesk import settings as helpdesk_settings
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
import uuid
import datetime

try:  # python 3
    from urllib.parse import urlparse
except ImportError:  # python 2
    from urlparse import urlparse

from helpdesk.templatetags.ticket_to_link import num_to_link


class TimeSpentTestCase(TestCase):

    def setUp(self):
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

    def test_add_followup(self):
        """Tests whether staff can delete tickets"""

        message_id = uuid.uuid4().hex
        followup = FollowUp.objects.create(
            ticket=self.ticket,
            date=datetime.datetime.now(),
            title="Testing followup",
            comment="Testing followup time spent",
            public=True,
            user=self.user,
            new_status=1,
            message_id=message_id,
            time_spent=datetime.timedelta(minutes=30)
        )

        followup.save()

        self.assertEqual(followup.time_spent.seconds, 1800)
        self.assertEqual(self.ticket.time_spent.seconds, 1800)
        self.assertEqual(self.queue_public.time_spent.seconds, 1800)
        self.assertTrue(
            self.queue_public.dedicated_time.seconds > self.queue_public.time_spent.seconds
        )
