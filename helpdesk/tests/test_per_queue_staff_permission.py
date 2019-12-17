from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.test import TestCase
from django.test.client import Client

from helpdesk.models import Queue, Ticket
from helpdesk import settings
from helpdesk.query import get_query
from helpdesk.user import HelpdeskUser


class PerQueueStaffMembershipTestCase(TestCase):

    IDENTIFIERS = (1, 2)

    def setUp(self):
        """
        Create user_1 with access to queue_1 containing 2 ticket
        and    user_2 with access to queue_2 containing 4 tickets
        and superuser who should be able to access both queues
        """
        self.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION = settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION
        settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION = True
        self.client = Client()
        User = get_user_model()

        self.superuser = User.objects.create(
            username='superuser',
            is_staff=True,
            is_superuser=True,
        )
        self.superuser.set_password('superuser')
        self.superuser.save()

        self.identifier_users = {}

        for identifier in self.IDENTIFIERS:
            queue = self.__dict__['queue_%d' % identifier] = Queue.objects.create(
                title='Queue %d' % identifier,
                slug='q%d' % identifier,
            )

            user = self.__dict__['user_%d' % identifier] = User.objects.create(
                username='User_%d' % identifier,
                is_staff=True,
                email="foo%s@example.com" % identifier
            )
            user.set_password(str(identifier))
            user.save()
            self.identifier_users[identifier] = user

            # The prefix 'helpdesk.' must be trimmed
            p = Permission.objects.get(codename=queue.permission_name[9:])
            user.user_permissions.add(p)

            for ticket_number in range(1, identifier + 1):
                Ticket.objects.create(
                    title='Unassigned Ticket %d in Queue %d' % (ticket_number, identifier),
                    queue=queue,
                )
                Ticket.objects.create(
                    title='Ticket %d in Queue %d Assigned to User_%d' % (ticket_number, identifier, identifier),
                    queue=queue,
                    assigned_to=user,
                )

    def tearDown(self):
        """
        Reset HELPDESK_ENABLE_PER_QUEUE_STAFF_MEMBERSHIP to original value
        """
        settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION = self.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION

    def test_dashboard_ticket_counts(self):
        """
        Check that the regular users' dashboard only shows 1 of the 2 queues,
        that user_1 only sees a total of 2 tickets, that user_2 sees a total of 4
        tickets, but that the superuser's dashboard shows all queues and tickets.
        """

        # Regular users
        for identifier in self.IDENTIFIERS:
            self.client.login(username='User_%d' % identifier, password=str(identifier))
            response = self.client.get(reverse('helpdesk:dashboard'))
            self.assertEqual(
                len(response.context['unassigned_tickets']),
                identifier,
                'Unassigned tickets were not properly limited by queue membership'
            )
            self.assertEqual(
                response.context['basic_ticket_stats']['open_ticket_stats'][0][1],
                identifier * 2,
                'Basic ticket stats were not properly limited by queue membership'
            )

        # Superuser
        self.client.login(username='superuser', password='superuser')
        response = self.client.get(reverse('helpdesk:dashboard'))
        self.assertEqual(
            len(response.context['unassigned_tickets']),
            3,
            'Unassigned tickets were limited by queue membership for a superuser'
        )
        self.assertEqual(
            response.context['basic_ticket_stats']['open_ticket_stats'][0][1] +
            response.context['basic_ticket_stats']['open_ticket_stats'][1][1],
            6,
            'Basic ticket stats were limited by queue membership for a superuser'
        )

    def test_report_ticket_counts(self):
        """
        Check that the regular users' report only shows 1 of the 2 queues,
        that user_1 only sees a total of 2 tickets, that user_2 sees a total of 4
        tickets, but that the superuser's report shows all queues and tickets.
        """

        # Regular users
        for identifier in self.IDENTIFIERS:
            self.client.login(username='User_%d' % identifier, password=str(identifier))
            response = self.client.get(reverse('helpdesk:report_index'))
            self.assertEqual(
                len(response.context['dash_tickets']),
                1,
                'The queues in dash_tickets were not properly limited by queue membership'
            )
            self.assertEqual(
                response.context['dash_tickets'][0]['open'],
                identifier * 2,
                'The tickets in dash_tickets were not properly limited by queue membership'
            )
            self.assertEqual(
                response.context['basic_ticket_stats']['open_ticket_stats'][0][1],
                identifier * 2,
                'Basic ticket stats were not properly limited by queue membership'
            )

        # Superuser
        self.client.login(username='superuser', password='superuser')
        response = self.client.get(reverse('helpdesk:report_index'))
        self.assertEqual(
            len(response.context['dash_tickets']),
            2,
            'The queues in dash_tickets were limited by queue membership for a superuser'
        )
        self.assertEqual(
            response.context['dash_tickets'][0]['open'] +
            response.context['dash_tickets'][1]['open'],
            6,
            'The tickets in dash_tickets were limited by queue membership for a superuser'
        )
        self.assertEqual(
            response.context['basic_ticket_stats']['open_ticket_stats'][0][1] +
            response.context['basic_ticket_stats']['open_ticket_stats'][1][1],
            6,
            'Basic ticket stats were limited by queue membership for a superuser'
        )

    def test_ticket_list_per_queue_user_restrictions(self):
        """
        Ensure that while the superuser can list all tickets, user_1 can only
        list the 2 tickets in his queue and user_2 can list only the 4 tickets
        in his queue.
        """
        # Regular users
        for identifier in self.IDENTIFIERS:
            self.client.login(username='User_%d' % identifier, password=str(identifier))
            response = self.client.get(reverse('helpdesk:list'))
            tickets = get_query(response.context['urlsafe_query'], HelpdeskUser(self.identifier_users[identifier]))
            self.assertEqual(
                len(tickets),
                identifier * 2,
                'Ticket list was not properly limited by queue membership'
            )
            self.assertEqual(
                len(response.context['queue_choices']),
                1,
                'Queue choices were not properly limited by queue membership'
            )
            self.assertEqual(
                response.context['queue_choices'][0],
                Queue.objects.get(title="Queue %d" % identifier),
                'Queue choices were not properly limited by queue membership'
            )

        # Superuser
        self.client.login(username='superuser', password='superuser')
        response = self.client.get(reverse('helpdesk:list'))
        tickets = get_query(response.context['urlsafe_query'], HelpdeskUser(self.superuser))
        self.assertEqual(
            len(tickets),
            6,
            'Ticket list was limited by queue membership for a superuser'
        )

    def test_ticket_reports_per_queue_user_restrictions(self):
        """
        Ensure that while the superuser can generate reports on all queues and
        tickets, user_1 can only generate reports for queue 1 and user_2 can
        only do so for queue 2
        """
        # Regular users
        for identifier in self.IDENTIFIERS:
            self.client.login(username='User_%d' % identifier, password=str(identifier))
            response = self.client.get(
                reverse('helpdesk:run_report', kwargs={'report': 'userqueue'})
            )
            # Only two columns of data should be present: ticket counts for
            # unassigned and this user only
            self.assertEqual(
                len(response.context['data']),
                2,
                'Queues in report were not properly limited by queue membership'
            )
            # Each user should see a total number of tickets equal to twice their ID
            self.assertEqual(
                sum([sum(user_tickets[1:]) for user_tickets in response.context['data']]),
                identifier * 2,
                'Tickets in report were not properly limited by queue membership'
            )
            # Each user should only be able to pick 1 queue
            self.assertEqual(
                len(response.context['headings']),
                2,
                'Queue choices were not properly limited by queue membership'
            )
            # The queue each user can pick should be the queue named after their ID
            self.assertEqual(
                response.context['headings'][1],
                "Queue %d" % identifier,
                'Queue choices were not properly limited by queue membership'
            )

        # Superuser
        self.client.login(username='superuser', password='superuser')
        response = self.client.get(
            reverse('helpdesk:run_report', kwargs={'report': 'userqueue'})
        )
        # Superuser should see ticket counts for all two queues, which includes
        # three columns: unassigned and both user 1 and user 2
        self.assertEqual(
            len(response.context['data'][0]),
            3,
            'Queues in report were improperly limited by queue membership for a superuser'
        )
        # Superuser should see the total ticket count of three tickets
        self.assertEqual(
            sum([sum(user_tickets[1:]) for user_tickets in response.context['data']]),
            6,
            'Tickets in report were improperly limited by queue membership for a superuser'
        )
        self.assertEqual(
            len(response.context['headings']),
            3,
            'Queue choices were improperly limited by queue membership for a superuser'
        )
