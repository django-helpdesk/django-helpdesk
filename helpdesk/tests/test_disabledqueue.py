# -*- coding: utf-8 -*-
from django.core.urlresolvers import reverse
from django.test import TestCase
from helpdesk.models import Ticket, Queue

class TestDisabledQueue(TestCase):
    def setUp(self):
        eq = Queue(title='EnabledQueue',
                   slug='enabledqueue',
                   allow_public_submission=True)
        eq.save()
        # Create another queue, but dont disable it yet
        dq = Queue(title='DisabledQueue',
                   slug='disabledqueue',
                   allow_public_submission=True)
        dq.save()
        # One ticket for each queue
        teq = Ticket(title='Test Ticket EQ',
                     submitter_email='test@domain.com')
        teq.queue = eq
        teq.save()
        tdq = Ticket(title='Test Ticket DQ',
                     submitter_email='test@domain.com')
        tdq.queue = dq
        tdq.save()
        print Queue.objects.all()
        self.tickets = (teq,tdq)

    def test_enabled_queues_are_visible(self):
        """Can a queue be seen in the ui when it is enabled"""
        url = reverse('helpdesk_home')
        response = self.client.get(url)
        teq, tdq = self.tickets
        self.assertContains(response, teq.queue.title)
        self.assertContains(response, tdq.queue.title)
        # Now disable one of the queues
        tdq.queue.enabled = False
        tdq.queue.save()
        print Queue.objects.enabled_queues()
        response = self.client.get(url)
        self.assertContains(response, teq.queue.title)
        self.assertNotContains(response, tdq.queue.title)

    def test_lookupticket_disabledqueue(self):
        """Can we lookup a ticket on a disabled queue"""
        teq, tdq = self.tickets
        url = reverse('helpdesk_public_view')
        # lookup the enabled queue ticket
        response = self.client.get(url, data={'ticket':teq.id, 'email':teq.submitter_email})
        self.assertContains(response, 'Queue: %s' % teq.queue.title)
        # disable the queue
        tdq.queue.enabled = False
        tdq.queue.save()
        # lookup the disabled queue ticket
        response = self.client.get(url, data={'ticket':tdq.id, 'email':tdq.submitter_email})
        self.assertContains(response, 'Queue: %s' % tdq.queue.title)
