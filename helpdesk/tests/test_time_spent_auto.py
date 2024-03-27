
from datetime import datetime, timedelta
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.test.client import Client
from helpdesk.models import FollowUp, Queue, Ticket
from helpdesk import settings as helpdesk_settings
import uuid


@override_settings(USE_TZ=True)
class TimeSpentAutoTestCase(TestCase):

    def setUp(self):
        """Creates a queue, ticket and user."""
        self.queue_public = Queue.objects.create(
            title='Queue 1',
            slug='q1',
            allow_public_submission=True,
            dedicated_time=timedelta(minutes=60)
        )

        self.ticket_data = dict(queue=self.queue_public,
                                title='test ticket',
                                description='test ticket description')

        self.client = Client()

        self.user = User.objects.create(
            username='staff',
            email='staff@example.com',
            password=make_password('Test1234'),
            is_staff=True,
            is_superuser=False,
            is_active=True
        )

    def test_add_two_followups_time_spent_auto(self):
        """Tests automatic time_spent calculation"""
        # activate automatic calculation
        helpdesk_settings.FOLLOWUP_TIME_SPENT_AUTO = True

        # ticket creation date, follow-up creation date, assertion value
        TEST_VALUES = (
            # friday
            ('2024-03-01T00:00:00+00:00', '2024-03-01T09:30:10+00:00', timedelta(hours=9, minutes=30, seconds=10)),
            ('2024-03-01T00:00:00+00:00', '2024-03-01T23:59:58+00:00', timedelta(hours=23, minutes=59, seconds=58)),
            ('2024-03-01T00:00:00+00:00', '2024-03-01T23:59:59+00:00', timedelta(hours=23, minutes=59, seconds=59)),
            ('2024-03-01T00:00:00+00:00', '2024-03-02T00:00:00+00:00', timedelta(hours=24)),
            ('2024-03-01T00:00:00+00:00', '2024-03-02T09:00:00+00:00', timedelta(hours=33)),
            ('2024-03-01T00:00:00+00:00', '2024-03-03T00:00:00+00:00', timedelta(hours=48)),
        )

        for (ticket_time, fup_time, assertion_delta) in TEST_VALUES:
            # create and setup test ticket time
            ticket = Ticket.objects.create(**self.ticket_data)
            ticket_time_p = datetime.strptime(ticket_time, "%Y-%m-%dT%H:%M:%S%z")
            ticket.created = ticket_time_p
            ticket.modified = ticket_time_p
            ticket.save()

            fup_time_p = datetime.strptime(fup_time, "%Y-%m-%dT%H:%M:%S%z")
            followup1 = FollowUp.objects.create(
                ticket=ticket,
                date=fup_time_p,
                title="Testing followup",
                comment="Testing followup time spent",
                public=True,
                user=self.user,
                new_status=1,
                message_id=uuid.uuid4().hex,
                time_spent=None
            )
            followup1.save()

            self.assertEqual(followup1.time_spent.total_seconds(), assertion_delta.total_seconds())
            self.assertEqual(ticket.time_spent.total_seconds(), assertion_delta.total_seconds())

            # adding a second follow-up at different intervals
            for delta in (timedelta(seconds=1), timedelta(minutes=1), timedelta(hours=1), timedelta(days=1), timedelta(days=10)):
                
                followup2 = FollowUp.objects.create(
                    ticket=ticket,
                    date=followup1.date + delta,
                    title="Testing followup 2",
                    comment="Testing followup time spent 2",
                    public=True,
                    user=self.user,
                    new_status=1,
                    message_id=uuid.uuid4().hex,
                    time_spent=None
                )
                followup2.save()

                self.assertEqual(followup2.time_spent.total_seconds(), delta.total_seconds())
                self.assertEqual(ticket.time_spent.total_seconds(), assertion_delta.total_seconds() + delta.total_seconds())

                # delete second follow-up as we test it with many intervals
                followup2.delete()


    def test_add_two_followups_time_spent_auto(self):
        """Tests automatic time_spent calculation"""
        # activate automatic calculation
        helpdesk_settings.FOLLOWUP_TIME_SPENT_AUTO = True

        # ticket creation date, follow-up creation date, assertion value
        TEST_VALUES = (
            # friday
            ('2024-03-01T00:00:00+00:00', '2024-03-01T09:30:10+00:00', timedelta(hours=9, minutes=30, seconds=10)),
            ('2024-03-01T00:00:00+00:00', '2024-03-01T23:59:58+00:00', timedelta(hours=23, minutes=59, seconds=58)),
            ('2024-03-01T00:00:00+00:00', '2024-03-01T23:59:59+00:00', timedelta(hours=23, minutes=59, seconds=59)),
            ('2024-03-01T00:00:00+00:00', '2024-03-02T00:00:00+00:00', timedelta(hours=24)),
            ('2024-03-01T00:00:00+00:00', '2024-03-02T09:00:00+00:00', timedelta(hours=33)),
            ('2024-03-01T00:00:00+00:00', '2024-03-03T00:00:00+00:00', timedelta(hours=48)),
        )