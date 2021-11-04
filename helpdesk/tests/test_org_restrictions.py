# -*- coding: utf-8 -*-
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.test import TestCase
from django.test.client import Client

from helpdesk.models import Queue, Ticket, FormType
from helpdesk import settings
from helpdesk.query import __Query__
from helpdesk.user import HelpdeskUser
from seed.lib.superperms.orgs.models import Organization

'''
Suite of Test Cases to extend PerQueueStaffMembershipTestCase
When a user has a default_org 'a', they should not be able to
view tickets belonging to org 'b', even if they are a part of
org 'b' until they switch to org 'b'

'''
import logging

logging.disable(logging.CRITICAL)

class PerQueueOrgMembershipTestCase(TestCase):

    IDENTIFIERS = (1, 2)

    def setUp(self):
        """
        Create user_1 with access to queue_1 and queue_2.
        Each queue belongs to a different org
        Even a superuser should only view tickets for one
        org at a time
        """
        self.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION = settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION
        settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION = True
        self.client = Client()
        User = get_user_model()

        self.users = {}
        self.login = {1: 'User_1', 2: 'superuser'}
        self.passw = {1: '1', 2: 'superuser'}

        superuser = User.objects.create(
            username='superuser',
            is_staff=True,
            is_superuser=True,
        )
        superuser.set_password('superuser')
        superuser.default_organization_id = 1
        superuser.save()
        self.users[2] = superuser

        user = self.__dict__['user_%d' % 1] = User.objects.create(
            username='User_%d' % 1,
            is_staff=True,
            email="foo%s@example.com" % 1
        )
        user.set_password(str(1))
        user.default_organization_id = 1
        user.save()
        self.users[1] = user

        for identifier in self.IDENTIFIERS:
            org = Organization.objects.create(
                name='Organization %d' % identifier,
                id=identifier,
            )
            org.save()
            queue = Queue.objects.create(
                title='Queue %d' % identifier,
                slug='q%d' % identifier,
                organization=org
            )
            queue.save()
            form = FormType.objects.create(
                organization=org,
            )
            # Set user_1 to be part of each org
            self.users[1].orgs.add(org)

            # The prefix 'helpdesk.' must be trimmed
            p = Permission.objects.get(codename=queue.permission_name[9:])
            self.users[identifier].user_permissions.add(p)

            for ticket_number in range(1, identifier + 1):
                x = Ticket.objects.create(
                    title='Unassigned Ticket %d in Queue %d' % (ticket_number, identifier),
                    queue=queue,
                    ticket_form_id = form.id,
                )
                Ticket.objects.create(
                    title='Ticket %d in Queue %d Assigned to User_%d' % (ticket_number, identifier, identifier),
                    queue=queue,
                    assigned_to=user,
                    ticket_form_id = form.id,
                )

    def tearDown(self):
        """
        Reset HELPDESK_ENABLE_PER_QUEUE_STAFF_MEMBERSHIP to original value
        """
        settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION = self.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION

    def test_dashboard_ticket_counts(self):
        """
        Check that the regular user's dashboard only shows 1 of the 2 queues
        at a time. It only sees either 2 tickets or 4 tickets. The superuser
        will see similar results
        """
        # Currently in org 1. Should see only 1 and 2. In org 2, should see 2 and 4
        for identifier in self.IDENTIFIERS:
            self.client.login(username=self.login[identifier], password=self.passw[identifier])
            # switch org
            self.users[identifier].default_organization_id = identifier
            self.users[identifier].save()
            response = self.client.get(reverse('helpdesk:dashboard'))
            self.assertEqual(
                len(response.context['unassigned_tickets']),
                identifier,
                'Unassigned tickets were not properly limited by queue/org membership'
            )
            self.assertEqual(
                response.context['basic_ticket_stats']['open_ticket_stats'][0][1],
                identifier * 2,
                'Basic ticket stats were not properly limited by queue/org membership'
            )

    def test_report_ticket_counts(self):
        """
        Check that the regular user's report only shows the one queue available
        to their current org. The same applies for the superuser. They should
        only see a total of 2 then 4 tickets.
        """
        # Regular users
        for identifier in self.IDENTIFIERS:
            self.client.login(username=self.login[identifier], password=self.passw[identifier])
            # switch org
            self.users[identifier].default_organization_id = identifier
            self.users[identifier].save()
            response = self.client.get(reverse('helpdesk:report_index'))
            self.assertEqual(
                len(response.context['dash_tickets']),
                1,
                'The queues in dash_tickets were not properly limited by queue/org membership'
            )
            self.assertEqual(
                response.context['dash_tickets'][0]['open'],
                identifier * 2,
                'The tickets in dash_tickets were not properly limited by queue/org membership'
            )
            self.assertEqual(
                response.context['basic_ticket_stats']['open_ticket_stats'][0][1],
                identifier * 2,
                'Basic ticket stats were not properly limited by queue/org membership'
            )


    def test_org_dropdown_restriction(self):
        """
        Ensure that a user sees only the orgs available to them in the
        drop down menu
        """
        self.assertEqual(
            len(self.users[1].orgs.all()),
            2,
            'Improper amount of orgs returned for the user'
        )

    def test_ticket_list_per_queue_user_org_restrictions(self):
        """
        Ensure user and superuser only see tickets within their org
        Should list two tickets, then four tickets when org changes
        """
        # Regular users
        for identifier in self.IDENTIFIERS:
            self.client.login(username=self.login[identifier], password=self.passw[identifier])
            # switch org
            self.users[identifier].default_organization_id = identifier
            self.users[identifier].save()
            response = self.client.get(reverse('helpdesk:list'))
            tickets = __Query__(HelpdeskUser(self.users[identifier]),
                                base64query=response.context['urlsafe_query']).get()
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

    def test_ticket_reports_per_queue_user_org_restrictions(self):
        """
        Ensure that the two users can only generate reports in the queues
        belonging to their current org
        """
        # Regular users
        for identifier in self.IDENTIFIERS:
            self.client.login(username=self.login[identifier], password=self.passw[identifier])
            # switch org
            self.users[identifier].default_organization_id = identifier
            self.users[identifier].save()
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

    def test_ticket_navigation(self):
        """
        Users should not be able to view tickets from other orgs
        Even if the user is a superuser and/or staff
        """
        from helpdesk.decorators import is_helpdesk_staff

        # Regular user
        self.client.login(username='User_%d' % 1, password=str(1))
        self.users[1].default_organization_id = 1       # Reset default org
        self.users[1].save()
        self.assertTrue(is_helpdesk_staff(self.users[1]))
        response = self.client.get(reverse('helpdesk:view', kwargs={'ticket_id': 25}))
        print(response)
        self.assertTemplateUsed(response, 'helpdesk/ticket.html')

        # Being in a different org, should not be able to view ticket belonging to org 1
        self.users[1].default_organization_id = 2
        self.users[1].save()
        response = self.client.get(reverse('helpdesk:view', kwargs={'ticket_id': 25}))
        self.assertEqual(response.status_code, 403)

        # Super User
        self.client.login(username='superuser', password='superuser')
        self.users[2].default_organization_id = 1       # Reset default org
        self.users[2].save()
        self.assertTrue(is_helpdesk_staff(self.users[2]))
        response = self.client.get(reverse('helpdesk:view', kwargs={'ticket_id': 25}))
        print(response)
        self.assertTemplateUsed(response, 'helpdesk/ticket.html')

        # Being in a different org, should not be able to view ticket belonging to org 1
        self.users[2].default_organization_id = 2
        self.users[2].save()
        response = self.client.get(reverse('helpdesk:view', kwargs={'ticket_id': 25}))
        self.assertEqual(response.status_code, 403)
