# -*- coding: utf-8 -*-
from django.core.urlresolvers import reverse
from django.test import TestCase
from helpdesk.models import Ticket, Queue


class TestKBDisabled(TestCase):
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
