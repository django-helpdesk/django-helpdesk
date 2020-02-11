from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from helpdesk.models import KBCategory, KBItem, Queue, Ticket
from helpdesk.query import query_to_base64

from helpdesk.tests.helpers import (get_staff_user, reload_urlconf, User, create_ticket, print_response)


class QueryTests(TestCase):
    def setUp(self):
        self.queue = Queue.objects.create(
            title="Test queue",
            slug="test_queue",
            allow_public_submission=True,
        )
        self.queue.save()
        cat = KBCategory.objects.create(
            title="Test Cat",
            slug="test_cat",
            description="This is a test category",
            queue=self.queue,
        )
        cat.save()
        self.kbitem1 = KBItem.objects.create(
            category=cat,
            title="KBItem 1",
            question="What?",
            answer="A KB Item",
        )
        self.user = get_staff_user()
        self.ticket1 = Ticket.objects.create(
            title="unassigned to kbitem",
            queue=self.queue,
            description="lol",
        )
        self.ticket1.save()
        self.ticket2 = Ticket.objects.create(
            title="assigned to kbitem",
            queue=self.queue,
            description="lol",
            kbitem=self.kbitem1,
        )
        self.ticket2.save()

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

    def test_query_basic(self):
        self.loginUser()
        query = query_to_base64({})
        response = self.client.get(reverse('helpdesk:datatables_ticket_list', args=[query]))
        self.assertEqual(
            response.json(),
            {
                "data":
                [{"ticket": "1 [test_queue-1]", "id": 1, "priority": 3, "title": "unassigned to kbitem", "queue": {"title": "Test queue", "id": 1}, "status": "Open", "created": "now", "due_date": None, "assigned_to": "None", "submitter": None, "row_class": "", "time_spent": "", "kbitem": ""},
                 {"ticket": "2 [test_queue-2]", "id": 2, "priority": 3, "title": "assigned to kbitem", "queue": {"title": "Test queue", "id": 1}, "status": "Open", "created": "now", "due_date": None, "assigned_to": "None", "submitter": None, "row_class": "", "time_spent": "", "kbitem": "KBItem 1"}],
                "recordsFiltered": 2,
                "recordsTotal": 2,
                "draw": 0,
            },
        )

    def test_query_by_kbitem(self):
        self.loginUser()
        query = query_to_base64(
            {'filtering': {'kbitem__in': [self.kbitem1.pk]}}
        )
        response = self.client.get(reverse('helpdesk:datatables_ticket_list', args=[query]))
        self.assertEqual(
            response.json(),
            {
                "data":
                [{"ticket": "2 [test_queue-2]", "id": 2, "priority": 3, "title": "assigned to kbitem", "queue": {"title": "Test queue", "id": 1}, "status": "Open", "created": "now", "due_date": None, "assigned_to": "None", "submitter": None, "row_class": "", "time_spent": "", "kbitem": "KBItem 1"}],
                "recordsFiltered": 1,
                "recordsTotal": 1,
                "draw": 0,
            },
        )

    def test_query_by_no_kbitem(self):
        self.loginUser()
        query = query_to_base64(
            {'filtering_or': {'kbitem__in': [self.kbitem1.pk]}}
        )
        response = self.client.get(reverse('helpdesk:datatables_ticket_list', args=[query]))
        self.assertEqual(
            response.json(),
            {
                "data":
                [{"ticket": "2 [test_queue-2]", "id": 2, "priority": 3, "title": "assigned to kbitem", "queue": {"title": "Test queue", "id": 1}, "status": "Open", "created": "now", "due_date": None, "assigned_to": "None", "submitter": None, "row_class": "", "time_spent": "", "kbitem": "KBItem 1"}],
                "recordsFiltered": 1,
                "recordsTotal": 1,
                "draw": 0,
            },
        )
