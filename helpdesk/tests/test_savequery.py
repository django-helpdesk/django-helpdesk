# -*- coding: utf-8 -*-
from django.core.urlresolvers import reverse
from django.test import TestCase
from helpdesk.models import Ticket, Queue
from helpdesk.tests.helpers import get_staff_user, reload_urlconf

class TestKBDisabled(TestCase):
    def setUp(self):
        q = Queue(title='Q1', slug='q1')
        q.save()
        self.q = q

    def test_cansavequery(self):
        """Can a query be saved"""
        # get the ticket from models
        url = reverse('helpdesk_savequery')
        self.client.login(username=get_staff_user().get_username(),
                          password='password')
        response = self.client.post(url,
                                    data={'title': 'ticket on my queue',
                                    'queue':self.q,
                                    'shared':'on',
                                    'query_encoded':'KGRwMApWZmlsdGVyaW5nCnAxCihkcDIKVnN0YXR1c19faW4KcDMKKGxwNApJMQphSTIKYUkzCmFzc1Zzb3J0aW5nCnA1ClZjcmVhdGVkCnA2CnMu'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/helpdesk/tickets/?saved_query=1')


