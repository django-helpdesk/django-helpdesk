# -*- coding: utf-8 -*-
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import TestCase
from helpdesk.models import Ticket, Queue
from django.test.utils import override_settings


User = get_user_model()


@override_settings(
    HELPDESK_VIEW_A_TICKET_PUBLIC=True
)
class TestTicketLookupPublicEnabled(TestCase):
    def setUp(self):
        q = Queue(title='Q1', slug='q1')
        q.save()
        t = Ticket(title='Test Ticket', submitter_email='test@domain.com')
        t.queue = q
        t.save()
        self.ticket = t

    def test_ticket_by_id(self):
        """Can a ticket be looked up by its ID"""
        # get the ticket from models
        t = Ticket.objects.get(id=self.ticket.id)
        self.assertEqual(t.title, self.ticket.title)

    def test_ticket_by_link(self):
        """Can a ticket be looked up by its link from (eg) an email"""
        # Instead of using the ticket_for_url link,
        # we will exercise 'reverse' to lookup/build the URL
        # from the ticket info we have
        # http://example.com/helpdesk/view/?ticket=q1-1&email=None
        response = self.client.get(reverse('helpdesk:public_view'),
                                   {'ticket': self.ticket.ticket_for_url,
                                    'email': self.ticket.submitter_email})
        self.assertEqual(response.status_code, 200)

    def test_ticket_with_changed_queue(self):
        # Make a ticket (already done in setup() )
        # Now make another queue
        q2 = Queue(title='Q2', slug='q2')
        q2.save()
        # grab the URL / params which would have been emailed out to submitter.
        url = reverse('helpdesk:public_view')
        params = {'ticket': self.ticket.ticket_for_url,
                  'email': self.ticket.submitter_email}
        # Pickup the ticket created in setup() and change its queue
        self.ticket.queue = q2
        self.ticket.save()

        # confirm that we can still get to a url which was emailed earlier
        response = self.client.get(url, params)
        self.assertNotContains(response, "Invalid ticket ID")

    def test_add_email_to_ticketcc_if_not_in(self):
        staff_email = 'staff@mail.com'
        staff_user = User.objects.create(username='staff', email=staff_email, is_staff=True)
        self.ticket.assigned_to = staff_user
        self.ticket.save()
        email_1 = 'user1@mail.com'
        ticketcc_1 = self.ticket.ticketcc_set.create(email=email_1)

        # Add new email to CC
        email_2 = 'user2@mail.com'
        ticketcc_2 = self.ticket.add_email_to_ticketcc_if_not_in(email=email_2)
        self.assertEqual(list(self.ticket.ticketcc_set.all()), [ticketcc_1, ticketcc_2])

        # Add existing email, doesn't change anything
        self.ticket.add_email_to_ticketcc_if_not_in(email=email_1)
        self.assertEqual(list(self.ticket.ticketcc_set.all()), [ticketcc_1, ticketcc_2])

        # Add mail from assigned user, doesn't change anything
        self.ticket.add_email_to_ticketcc_if_not_in(email=staff_email)
        self.assertEqual(list(self.ticket.ticketcc_set.all()), [ticketcc_1, ticketcc_2])
        self.ticket.add_email_to_ticketcc_if_not_in(user=staff_user)
        self.assertEqual(list(self.ticket.ticketcc_set.all()), [ticketcc_1, ticketcc_2])

        # Move a ticketCC from ticket 1 to ticket 2
        ticket_2 = Ticket.objects.create(queue=self.ticket.queue, title='Ticket 2', submitter_email=email_2)
        self.assertEqual(ticket_2.ticketcc_set.count(), 0)
        ticket_2.add_email_to_ticketcc_if_not_in(ticketcc=ticketcc_1)
        self.assertEqual(ticketcc_1.ticket, ticket_2)
        self.assertEqual(ticket_2.ticketcc_set.count(), 1)

        # Adding email_2 doesn't change since it is already submitter email
        ticket_2.add_email_to_ticketcc_if_not_in(email=email_2)
        self.assertEqual(ticket_2.ticketcc_set.get(), ticketcc_1)
        ticket_2.add_email_to_ticketcc_if_not_in(ticketcc=ticketcc_2)
        self.assertEqual(ticket_2.ticketcc_set.get(), ticketcc_1)

        # Finally test function raises a Value error when no parameter is given
        self.assertRaises(ValueError, ticket_2.add_email_to_ticketcc_if_not_in)
