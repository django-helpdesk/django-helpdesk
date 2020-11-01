from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core import mail
from django.urls import reverse
from django.test import TestCase
from django.test.client import Client
from django.utils import timezone

from helpdesk.models import CustomField, Queue, Ticket
from helpdesk import settings as helpdesk_settings

try:  # python 3
    from urllib.parse import urlparse
except ImportError:  # python 2
    from urlparse import urlparse

from helpdesk.templatetags.ticket_to_link import num_to_link
from helpdesk.user import HelpdeskUser


class TicketActionsTestCase(TestCase):
    fixtures = ['emailtemplate.json']

    def setUp(self):
        self.queue_public = Queue.objects.create(
            title='Queue 1',
            slug='q1',
            allow_public_submission=True,
            new_ticket_cc='new.public@example.com',
            updated_ticket_cc='update.public@example.com'
        )

        self.queue_private = Queue.objects.create(
            title='Queue 2',
            slug='q2',
            allow_public_submission=False,
            new_ticket_cc='new.private@example.com',
            updated_ticket_cc='update.private@example.com'
        )

        self.ticket_data = {
            'title': 'Test Ticket',
            'description': 'Some Test Ticket',
        }

        self.client = Client()
        helpdesk_settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION = False

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

    def test_ticket_markdown(self):

        ticket_data = {
            'queue': self.queue_public,
            'title': 'Test Ticket',
            'description': '*bold*',
        }

        ticket = Ticket.objects.create(**ticket_data)
        self.assertEqual(ticket.get_markdown(),
                         "<p><em>bold</em></p>")

    def test_delete_ticket_staff(self):
        # make staff user
        self.loginUser()

        """Tests whether staff can delete tickets"""
        ticket_data = dict(queue=self.queue_public, **self.ticket_data)
        ticket = Ticket.objects.create(**ticket_data)
        ticket_id = ticket.id

        response = self.client.get(reverse('helpdesk:delete', kwargs={'ticket_id': ticket_id}), follow=True)
        self.assertContains(response, 'Are you sure you want to delete this ticket')

        response = self.client.post(reverse('helpdesk:delete', kwargs={'ticket_id': ticket_id}), follow=True)
        first_redirect = response.redirect_chain[0]
        first_redirect_url = first_redirect[0]

        # Ensure we landed on the "View" page.
        # Django 1.9 compatible way of testing this
        # https://docs.djangoproject.com/en/1.9/releases/1.9/#http-redirects-no-longer-forced-to-absolute-uris
        urlparts = urlparse(first_redirect_url)
        self.assertEqual(urlparts.path, reverse('helpdesk:home'))

        # test ticket deleted
        with self.assertRaises(Ticket.DoesNotExist):
            Ticket.objects.get(pk=ticket_id)

    def test_update_ticket_staff(self):
        """Tests whether staff can update ticket details"""

        # make staff user
        self.loginUser()

        # create second user
        User = get_user_model()
        self.user2 = User.objects.create(
            username='User_2',
            is_staff=True,
        )

        initial_data = {
            'title': 'Private ticket test',
            'queue': self.queue_public,
            'assigned_to': self.user,
            'status': Ticket.OPEN_STATUS,
        }

        # create ticket
        ticket = Ticket.objects.create(**initial_data)
        ticket_id = ticket.id

        # assign new owner
        post_data = {
            'owner': self.user2.id,
        }
        response = self.client.post(reverse('helpdesk:update', kwargs={'ticket_id': ticket_id}), post_data, follow=True)
        self.assertContains(response, 'Changed Owner from User_1 to User_2')

        # change status with users email assigned and submitter email assigned,
        # which triggers emails being sent
        ticket.assigned_to = self.user2
        ticket.submitter_email = 'submitter@test.com'
        ticket.save()
        self.user2.email = 'user2@test.com'
        self.user2.save()
        self.user.email = 'user1@test.com'
        self.user.save()
        post_data = {
            'new_status': Ticket.CLOSED_STATUS,
            'public': True
        }

        # do this also to a newly assigned user (different from logged in one)
        ticket.assigned_to = self.user
        response = self.client.post(reverse('helpdesk:update', kwargs={'ticket_id': ticket_id}), post_data, follow=True)
        self.assertContains(response, 'Changed Status from Open to Closed')
        post_data = {
            'new_status': Ticket.OPEN_STATUS,
            'owner': self.user2.id,
            'public': True
        }
        response = self.client.post(reverse('helpdesk:update', kwargs={'ticket_id': ticket_id}), post_data, follow=True)
        self.assertContains(response, 'Changed Status from Open to Closed')

    def test_can_access_ticket(self):
        """Tests whether non-staff but assigned user still counts as owner"""

        # make non-staff user
        self.loginUser(is_staff=False)

        # create second user
        User = get_user_model()
        self.user2 = User.objects.create(
            username='User_2',
            is_staff=False,
        )

        initial_data = {
            'title': 'Private ticket test',
            'queue': self.queue_private,
            'assigned_to': self.user,
            'status': Ticket.OPEN_STATUS,
        }

        # create ticket
        helpdesk_settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION = True
        ticket = Ticket.objects.create(**initial_data)
        self.assertEqual(HelpdeskUser(self.user).can_access_ticket(ticket), True)
        self.assertEqual(HelpdeskUser(self.user2).can_access_ticket(ticket), False)

    def test_num_to_link(self):
        """Test that we are correctly expanding links to tickets from IDs"""

        # make staff user
        self.loginUser()

        initial_data = {
            'title': 'Some private ticket',
            'queue': self.queue_public,
            'assigned_to': self.user,
            'status': Ticket.OPEN_STATUS,
        }

        # create ticket
        ticket = Ticket.objects.create(**initial_data)
        ticket_id = ticket.id

        # generate the URL text
        result = num_to_link('this is ticket#%s' % ticket_id)
        self.assertEqual(result, "this is ticket <a href='/helpdesk/tickets/%s/' class='ticket_link_status ticket_link_status_Open'>#%s</a>" % (ticket_id, ticket_id))

        result2 = num_to_link('whoa another ticket is here #%s huh' % ticket_id)
        self.assertEqual(result2, "whoa another ticket is here  <a href='/helpdesk/tickets/%s/' class='ticket_link_status ticket_link_status_Open'>#%s</a> huh" % (ticket_id, ticket_id))

    def test_create_ticket_getform(self):
        self.loginUser()
        response = self.client.get(reverse('helpdesk:submit'), follow=True)
        self.assertEqual(response.status_code, 200)

        # TODO this needs to be checked further

    def test_merge_tickets(self):
        self.loginUser()

        # Create two tickets
        ticket_1 = Ticket.objects.create(
            queue=self.queue_public,
            title='Ticket 1',
            description='Description from ticket 1',
            submitter_email='user1@mail.com',
            status=Ticket.RESOLVED_STATUS,
            resolution='Awesome resolution for ticket 1'
        )
        ticket_1_follow_up = ticket_1.followup_set.create(title='Ticket 1 creation')
        ticket_1_cc = ticket_1.ticketcc_set.create(user=self.user)
        ticket_1_created = ticket_1.created
        due_date = timezone.now()
        ticket_2 = Ticket.objects.create(
            queue=self.queue_public,
            title='Ticket 2',
            description='Description from ticket 2',
            submitter_email='user2@mail.com',
            due_date=due_date,
            assigned_to=self.user
        )
        ticket_2_follow_up = ticket_1.followup_set.create(title='Ticket 2 creation')
        ticket_2_cc = ticket_2.ticketcc_set.create(email='random@mail.com')

        # Create custom fields and set values for tickets
        custom_field_1 = CustomField.objects.create(
            name='test',
            label='Test',
            data_type='varchar',
        )
        ticket_1_field_1 = 'This is for the test field'
        ticket_1.ticketcustomfieldvalue_set.create(field=custom_field_1, value=ticket_1_field_1)
        ticket_2_field_1 = 'Another test text'
        ticket_2.ticketcustomfieldvalue_set.create(field=custom_field_1, value=ticket_2_field_1)
        custom_field_2 = CustomField.objects.create(
            name='number',
            label='Number',
            data_type='integer',
        )
        ticket_2_field_2 = '444'
        ticket_2.ticketcustomfieldvalue_set.create(field=custom_field_2, value=ticket_2_field_2)

        # Check that it correctly redirects to the intermediate page
        response = self.client.post(
            reverse('helpdesk:mass_update'),
            data={
                'ticket_id': [str(ticket_1.id), str(ticket_2.id)],
                'action': 'merge'
            },
            follow=True
        )
        redirect_url = '%s?tickets=%s&tickets=%s' % (reverse('helpdesk:merge_tickets'), ticket_1.id, ticket_2.id)
        self.assertRedirects(response, redirect_url)
        self.assertContains(response, ticket_1.description)
        self.assertContains(response, ticket_1.resolution)
        self.assertContains(response, ticket_1.submitter_email)
        self.assertContains(response, ticket_1_field_1)
        self.assertContains(response, ticket_2.description)
        self.assertContains(response, ticket_2.submitter_email)
        self.assertContains(response, ticket_2_field_1)
        self.assertContains(response, ticket_2_field_2)

        # Check that the merge is correctly done
        response = self.client.post(
            redirect_url,
            data={
                'chosen_ticket': str(ticket_1.id),
                'due_date': str(ticket_2.id),
                'status': str(ticket_1.id),
                'submitter_email': str(ticket_2.id),
                'description': str(ticket_2.id),
                'assigned_to': str(ticket_2.id),
                custom_field_1.name: str(ticket_1.id),
                custom_field_2.name: str(ticket_2.id),
            },
            follow=True
        )
        self.assertRedirects(response, ticket_1.get_absolute_url())
        ticket_2.refresh_from_db()
        self.assertEqual(ticket_2.merged_to, ticket_1)
        self.assertEqual(ticket_2.followup_set.count(), 0)
        self.assertEqual(ticket_2.ticketcc_set.count(), 0)
        ticket_1.refresh_from_db()
        self.assertEqual(ticket_1.created, ticket_1_created)
        self.assertEqual(ticket_1.due_date, due_date)
        self.assertEqual(ticket_1.status, Ticket.RESOLVED_STATUS)
        self.assertEqual(ticket_1.submitter_email, ticket_2.submitter_email)
        self.assertEqual(ticket_1.description, ticket_2.description)
        self.assertEqual(ticket_1.assigned_to, ticket_2.assigned_to)
        self.assertEqual(ticket_1.ticketcustomfieldvalue_set.get(field=custom_field_1).value, ticket_1_field_1)
        self.assertEqual(ticket_1.ticketcustomfieldvalue_set.get(field=custom_field_2).value, ticket_2_field_2)
        self.assertEqual(list(ticket_1.followup_set.all()), [ticket_1_follow_up, ticket_2_follow_up])
        self.assertEqual(list(ticket_1.ticketcc_set.all()), [ticket_1_cc, ticket_2_cc])
