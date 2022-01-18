# -*- coding: utf-8 -*-
from django.urls import reverse
from django.test import TestCase
from seed.lib.superperms.orgs.models import Organization

from helpdesk.models import KBCategory, KBItem, Queue, Ticket, FormType

from helpdesk.tests.helpers import (get_staff_user, reload_urlconf, User, create_ticket, print_response)


class KBTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create()
        self.form = FormType.objects.create(organization=self.org)
        self.queue = Queue.objects.create(
            title="Test queue",
            slug="test_queue",
            allow_public_submission=True,
            organization=self.org,
        )
        self.queue.save()
        cat = KBCategory.objects.create(
            title="Test Cat",
            slug="test_cat",
            description="This is a test category",
            queue=self.queue,
            organization=self.org,
        )
        cat.save()
        self.kbitem1 = KBItem.objects.create(
            category=cat,
            title="KBItem 1",
            question="What?",
            answer="A KB Item",
        )
        self.kbitem1.save()
        self.kbitem2 = KBItem.objects.create(
            category=cat,
            title="KBItem 2",
            question="When?",
            answer="Now",
        )
        self.kbitem2.save()
        self.user = get_staff_user(organization=self.org)

    def test_kb_index(self):
        self.client.login(username=self.user.get_username(), password='password')

        response = self.client.get(reverse('helpdesk:kb_index'))
        self.assertContains(response, 'This is a test category')

    def test_kb_category(self):
        self.client.login(username=self.user.get_username(), password='password')

        response = self.client.get(reverse('helpdesk:kb_category', args=("test_cat", )))
        self.assertContains(response, 'This is a test category')
        response = self.client.get(reverse('helpdesk:kb_article', args=("test_cat", self.kbitem1.pk,)))
        self.assertContains(response, '0 open tickets')
        """
        self.assertContains(response, 'KBItem 1')
        self.assertContains(response, 'KBItem 2')
        self.assertContains(response, 'Create New Ticket Queue:')
        response = self.client.get(reverse('helpdesk:kb_category', args=("test_cat", )))
        self.assertContains(response, '<i class="fa fa-thumbs-up fa-lg"></i>')
        self.assertContains(response, '0 open tickets')
        ticket = Ticket.objects.create(
            title="Test ticket",
            queue=self.queue,
            kbitem=self.kbitem1,
            ticket_form=self.form
        )
        ticket.save()
        response = self.client.get(reverse('helpdesk:kb_category', args=("test_cat",)))
        self.assertContains(response, '1 open tickets')
        """
    """
    def test_kb_vote(self):
        self.client.login(username=self.user.get_username(), password='password')
        response = self.client.get(reverse('helpdesk:kb_vote', args=(self.kbitem1.pk,)) + "?vote=up")
        
        cat_url = reverse('helpdesk:kb_category', args=("test_cat",)) + "?kbitem=1"
        self.assertRedirects(response, cat_url)
        response = self.client.get(cat_url)
        self.assertContains(response, '1 people found this answer useful of 1')
        response = self.client.get(reverse('helpdesk:kb_vote', args=(self.kbitem1.pk,)) + "?vote=down")
        self.assertRedirects(response, cat_url)
        response = self.client.get(cat_url)
        self.assertContains(response, '0 people found this answer useful of 1')
    

    def test_kb_category_iframe(self):
        self.client.login(username=self.user.get_username(), password='password')

        cat_url = reverse('helpdesk:kb_category', args=("test_cat",)) + "?kbitem=1;submitter_email=foo@bar.cz;title=lol;"
        response = self.client.get(cat_url)
        # Assert that query params are passed on to ticket submit form
        self.assertContains(response, "'/helpdesk/tickets/submit/?queue=1;_readonly_fields_=queue;kbitem=1;submitter_email=foo%40bar.cz&amp;title=lol")
    """