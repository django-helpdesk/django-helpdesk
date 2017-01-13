from django.contrib.auth import get_user_model
from django.core import mail
from django.core.urlresolvers import reverse
from django.test import TestCase
from django.test.client import Client
from helpdesk.models import CustomField, Queue, Ticket

try:  # python 3
    from urllib.parse import urlparse
except ImportError:  # python 2
    from urlparse import urlparse


class TicketActionsTestCase(TestCase):
    fixtures = ['emailtemplate.json']

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create(
            username='User_1',
            is_staff=True,
        )
        self.user.set_password('pass')
        self.user.save()
        self.client.login(username='User_1', password='pass')

    def test_get_user_settings(self):

        response = self.client.get(reverse('helpdesk:user_settings'), follow=True)
        self.assertContains(response, "Use the following options")
