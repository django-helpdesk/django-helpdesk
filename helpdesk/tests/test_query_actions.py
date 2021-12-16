# -*- coding: utf-8 -*-
from django.urls import reverse
from django.test import TestCase
from helpdesk.models import Queue, SavedSearch
from helpdesk.tests.helpers import get_user
from helpdesk.decorators import is_helpdesk_staff
from seed.lib.superperms.orgs.models import Organization


class TestQueryActions(TestCase):
    def setUp(self):
        # Create two users to test various query actions
        org = Organization.objects.create(name='org1')

        self.user1 = get_user(username='user1')
        self.user1.default_organization = org
        self.user1.save()
        org.users.add(self.user1)

        self.user2 = get_user(username='user2')
        self.user2.default_organization = org
        self.user2.save()
        org.users.add(self.user2)  # Gets added as an owner

        q = Queue(title='Q1', slug='q1', organization=org)
        q.save()
        self.q = q

    def test_cansavequery(self):
        """Can a query be saved"""
        self.client.login(username=self.user1.username, password='password')
        url = reverse('helpdesk:savequery')
        response = self.client.post(
            url,
            data={
                'title': 'ticket on my queue',
                'queue': self.q,
                'shared': 'on',
                'query_encoded':
                    'KGRwMApWZmlsdGVyaW5nCnAxCihkcDIKVnN0YXR1c19faW4KcDMKKG'
                    'xwNApJMQphSTIKYUkzCmFzc1Zzb3J0aW5nCnA1ClZjcmVhdGVkCnA2CnMu'
            })
        self.assertTrue(is_helpdesk_staff(self.user1))
        self.assertEqual(response.status_code, 302)
        self.assertTrue('tickets/?saved_query=1' in response.url)

    def test_delete_query(self):
        """Can a query be deleted"""
        self.client.login(username=self.user1.username, password='password')
        # Create sample Query
        query = SavedSearch(user=self.user1, shared=False)
        query.save()
        response = self.client.get(reverse('helpdesk:delete_query', kwargs={'id': query.id}))
        self.assertTemplateUsed(response, 'helpdesk/confirm_delete_saved_query.html')

        # Actually deleting it
        response = self.client.post(reverse('helpdesk:delete_query', kwargs={'id': query.id}))
        self.assertRedirects(response, reverse('helpdesk:list'))

        # Recreate the query

    def test_reshare_query(self):
        """Can a query be reshared"""
        self.client.login(username=self.user1.username, password='password')
        # Create sample Query
        query = SavedSearch(user=self.user1, shared=False, title='query a')
        query.save()
        # Share the query
        response = self.client.get(reverse('helpdesk:reshare_query', kwargs={'id': query.id}))

        # check to see if user2 can access it
        self.client.login(username=self.user2.username, password='password')
        response = self.client.get(reverse('helpdesk:list'))
        queries = response.context['user_saved_queries']
        self.assertTrue(query in queries)

    def test_reject_query(self):
        """Can a query be rejected"""
        self.client.login(username=self.user1.username, password='password')
        # Create sample Query
        query = SavedSearch(user=self.user1, shared=False, title='query a')
        query.save()
        # Share the query
        response = self.client.get(reverse('helpdesk:reshare_query', kwargs={'id': query.id}))

        # Reject the query
        self.client.login(username=self.user2.username, password='password')
        response = self.client.get(reverse('helpdesk:reject_query', kwargs={'id': query.id}))
        # User should be in query's list of users to omit
        self.assertTrue(self.user2 in query.opted_out_users.all())

        # Should not be in query list in ticket_list page
        response = self.client.get(reverse('helpdesk:list'))
        queries = response.context['user_saved_queries']
        self.assertTrue(query not in queries)

    def test_unshare_query(self):
        """Can a query be unshared"""
        self.client.login(username=self.user1.username, password='password')
        # Create sample Query
        query = SavedSearch(user=self.user1, shared=False, title='query a')
        query.save()
        # Share the query
        response = self.client.get(reverse('helpdesk:reshare_query', kwargs={'id': query.id}))

        # Check that user2 has access to it
        self.client.login(username=self.user2.username, password='password')
        response = self.client.get(reverse('helpdesk:list'))
        queries = response.context['user_saved_queries']
        self.assertTrue(query in queries)

        # Unshare query
        self.client.login(username=self.user1.username, password='password')
        response = self.client.get(reverse('helpdesk:unshare_query', kwargs={'id': query.id}))

        # Check that user2 no longer has access to it
        self.client.login(username=self.user2.username, password='password')
        response = self.client.get(reverse('helpdesk:reject_query', kwargs={'id': query.id}))
        # User should be in query's list of users to omit
        self.assertTrue(self.user2 in query.opted_out_users.all())

        response = self.client.get(reverse('helpdesk:list'))
        queries = response.context['user_saved_queries']
        self.assertTrue(query not in queries)
