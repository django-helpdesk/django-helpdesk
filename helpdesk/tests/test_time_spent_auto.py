
from datetime import datetime, timedelta
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.test.client import Client
from django.urls import reverse
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

        self.user = User.objects.create(
            username='staff',
            email='staff@example.com',
            password=make_password('Test1234'),
            is_staff=True,
            is_superuser=False,
            is_active=True
        )

        self.client = Client()


    def loginUser(self, is_staff=True):
        """Create a staff user and login"""
        User = get_user_model()
        self.user = User.objects.create(
            username='User_1',
            is_staff=is_staff,
        )
        self.user.set_password('pass')
        self.user.save()
        self.client.login(username='User_1', password='pass')
    

    def test_add_two_followups_time_spent_auto(self):
        """Tests automatic time_spent calculation."""
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

                self.assertEqual(followup2.time_spent.total_seconds(), delta.total_seconds())
                self.assertEqual(ticket.time_spent.total_seconds(), assertion_delta.total_seconds() + delta.total_seconds())

                # delete second follow-up as we test it with many intervals
                followup2.delete()


    def test_followup_time_spent_auto_opening_hours(self):
        """Tests automatic time_spent calculation with opening hours and holidays."""

        # activate automatic calculation
        helpdesk_settings.FOLLOWUP_TIME_SPENT_AUTO = True
        helpdesk_settings.FOLLOWUP_TIME_SPENT_OPENING_HOURS = {
            "monday": (0, 23.9999),
            "tuesday": (8, 18),
            "wednesday": (8.5, 18.5),
            "thursday": (0, 10),
            "friday": (13, 23),
            "saturday": (0, 0),
            "sunday": (0, 0),
        }

        # adding holidays
        helpdesk_settings.FOLLOWUP_TIME_SPENT_EXCLUDE_HOLIDAYS = (
            '2024-03-18', '2024-03-19', '2024-03-20', '2024-03-21', '2024-03-22',
        )

        # ticket creation date, follow-up creation date, assertion value
        TEST_VALUES = (
            # monday
            ('2024-03-04T00:00:00+00:00', '2024-03-04T09:30:10+00:00', timedelta(hours=9, minutes=30, seconds=10)),
            # tuesday
            ('2024-03-05T07:00:00+00:00', '2024-03-05T09:00:00+00:00', timedelta(hours=1)),
            ('2024-03-05T17:50:00+00:00', '2024-03-05T17:51:00+00:00', timedelta(minutes=1)),
            ('2024-03-05T17:50:00+00:00', '2024-03-05T19:51:00+00:00', timedelta(minutes=10)),
            ('2024-03-05T18:00:00+00:00', '2024-03-05T23:59:59+00:00', timedelta(hours=0)),
            ('2024-03-05T20:00:00+00:00', '2024-03-05T20:59:59+00:00', timedelta(hours=0)),
            # wednesday
            ('2024-03-06T08:00:00+00:00', '2024-03-06T09:01:00+00:00', timedelta(minutes=31)),
            ('2024-03-06T01:00:00+00:00', '2024-03-06T19:30:10+00:00', timedelta(hours=10)),
            ('2024-03-06T18:01:00+00:00', '2024-03-06T19:00:00+00:00', timedelta(minutes=29)),
            # thursday
            ('2024-03-07T00:00:00+00:00', '2024-03-07T09:30:10+00:00', timedelta(hours=9, minutes=30, seconds=10)),
            ('2024-03-07T09:30:00+00:00', '2024-03-07T10:30:00+00:00', timedelta(minutes=30)),
            # friday
            ('2024-03-08T00:00:00+00:00', '2024-03-08T23:30:10+00:00', timedelta(hours=10)),
            # saturday
            ('2024-03-09T00:00:00+00:00', '2024-03-09T09:30:10+00:00', timedelta(hours=0)),
            # sunday
            ('2024-03-10T00:00:00+00:00', '2024-03-10T09:30:10+00:00', timedelta(hours=0)),

            # monday to sunday
            ('2024-03-04T04:00:00+00:00', '2024-03-10T09:00:00+00:00', timedelta(hours=60)),

            # two weeks
            ('2024-03-04T04:00:00+00:00', '2024-03-17T09:00:00+00:00', timedelta(hours=124)),

            # three weeks, the third one is holidays
            ('2024-03-04T04:00:00+00:00', '2024-03-24T09:00:00+00:00', timedelta(hours=124)),
            ('2024-03-18T04:00:00+00:00', '2024-03-24T09:00:00+00:00', timedelta(hours=0)),
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

            self.assertEqual(followup1.time_spent.total_seconds(), assertion_delta.total_seconds())
            self.assertEqual(ticket.time_spent.total_seconds(), assertion_delta.total_seconds())

        # removing opening hours and holidays
        helpdesk_settings.FOLLOWUP_TIME_SPENT_OPENING_HOURS = {}
        helpdesk_settings.FOLLOWUP_TIME_SPENT_EXCLUDE_HOLIDAYS = ()

    def test_followup_time_spent_auto_exclude_statuses(self):
        """Tests automatic time_spent calculation OPEN_STATUS exclusion."""

        # activate automatic calculation
        helpdesk_settings.FOLLOWUP_TIME_SPENT_AUTO = True

        # Follow-ups with OPEN_STATUS are excluded from time counting
        helpdesk_settings.FOLLOWUP_TIME_SPENT_EXCLUDE_STATUSES = (Ticket.OPEN_STATUS,)


        # create and setup test ticket time
        ticket = Ticket.objects.create(**self.ticket_data)
        ticket_time_p = datetime.strptime('2024-03-04T00:00:00+00:00', "%Y-%m-%dT%H:%M:%S%z")
        ticket.created = ticket_time_p
        ticket.modified = ticket_time_p
        ticket.save()

        fup_time_p = datetime.strptime('2024-03-10T00:00:00+00:00', "%Y-%m-%dT%H:%M:%S%z")
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

        # The Follow-up time_spent should be zero as the default OPEN_STATUS was excluded from calculation
        self.assertEqual(followup1.time_spent.total_seconds(), 0.0)
        self.assertEqual(ticket.time_spent.total_seconds(), 0.0)

        # Remove status exclusion
        helpdesk_settings.FOLLOWUP_TIME_SPENT_EXCLUDE_STATUSES = ()


    def test_followup_time_spent_auto_exclude_queues(self):
        """Tests automatic time_spent calculation queues exclusion."""

        # activate automatic calculation
        helpdesk_settings.FOLLOWUP_TIME_SPENT_AUTO = True

        # Follow-ups within the default queue are excluded from time counting
        helpdesk_settings.FOLLOWUP_TIME_SPENT_EXCLUDE_QUEUES = ('q1',)


        # create and setup test ticket time
        ticket = Ticket.objects.create(**self.ticket_data)
        ticket_time_p = datetime.strptime('2024-03-04T00:00:00+00:00', "%Y-%m-%dT%H:%M:%S%z")
        ticket.created = ticket_time_p
        ticket.modified = ticket_time_p
        ticket.save()

        fup_time_p = datetime.strptime('2024-03-10T00:00:00+00:00', "%Y-%m-%dT%H:%M:%S%z")
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

        # The Follow-up time_spent should be zero as the default queue was excluded from calculation
        self.assertEqual(followup1.time_spent.total_seconds(), 0.0)
        self.assertEqual(ticket.time_spent.total_seconds(), 0.0)

        # Remove queues exclusion
        helpdesk_settings.FOLLOWUP_TIME_SPENT_EXCLUDE_QUEUES = ()

    def test_http_followup_time_spent_auto_exclude_queues(self):
        """Tests automatic time_spent calculation queues exclusion with client"""

        # activate automatic calculation
        helpdesk_settings.FOLLOWUP_TIME_SPENT_AUTO = True
        helpdesk_settings.FOLLOWUP_TIME_SPENT_EXCLUDE_QUEUES = ('stop1', 'stop2')

        # make staff user
        self.loginUser()

        # create queues
        queues_sequence = ('new', 'stop1', 'resume1', 'stop2', 'resume2', 'end')
        queues = dict()
        for slug in queues_sequence:
            queues[slug] = Queue.objects.create(
                title=slug,
                slug=slug,
            )

        # create ticket
        initial_data = {
            'title': 'Queue change ticket test',
            'queue': queues['new'],
            'assigned_to': self.user,
            'status': Ticket.OPEN_STATUS,
            'created': datetime.strptime('2024-04-09T08:00:00+00:00', "%Y-%m-%dT%H:%M:%S%z")
        }
        ticket = Ticket.objects.create(**initial_data)

        # create a change queue follow-up every hour
        # first follow-up created at the same time of the ticket without queue change
        # new --1h--> stop1 --0h--> resume1 --1h--> stop2 --0h--> resume2 --1h--> end
        for (i, queue) in enumerate(queues_sequence):
            # create follow-up
            post_data = {
                'comment': 'ticket in queue {}'.format(queue),
                'queue': queues[queue].id,
            }
            response = self.client.post(reverse('helpdesk:update', kwargs={
                                        'ticket_id': ticket.id}), post_data)
            latest_fup = ticket.followup_set.latest('id')
            latest_fup.date = ticket.created + timedelta(hours=i)
            latest_fup.time_spent = None
            latest_fup.save()
        
        # total ticket time for followups is 5 hours
        self.assertEqual(latest_fup.date - ticket.created, timedelta(hours=5))
        # calculated time spent with 2 hours exclusion is 3 hours
        self.assertEqual(ticket.time_spent.total_seconds(), timedelta(hours=3).total_seconds())

        # remove queues exclusion
        helpdesk_settings.FOLLOWUP_TIME_SPENT_EXCLUDE_QUEUES = ()