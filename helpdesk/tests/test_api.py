import base64
from datetime import datetime

from django.contrib.auth.models import User
from pytz import UTC
from rest_framework import HTTP_HEADER_ENCODING
from rest_framework.exceptions import ErrorDetail
from rest_framework.status import HTTP_201_CREATED, HTTP_200_OK, HTTP_204_NO_CONTENT, HTTP_400_BAD_REQUEST
from rest_framework.test import APITestCase

from helpdesk.models import Queue, Ticket, CustomField


class TicketTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.queue = Queue.objects.create(
            title='Test Queue',
            slug='test-queue',
        )

    def test_create_api_ticket_not_authenticated_user(self):
        response = self.client.post('/api/tickets/')
        self.assertEqual(response.status_code, 403)

    def test_create_api_ticket_authenticated_non_staff_user(self):
        non_staff_user = User.objects.create_user(username='test')
        self.client.force_authenticate(non_staff_user)
        response = self.client.post('/api/tickets/')
        self.assertEqual(response.status_code, 403)

    def test_create_api_ticket_no_data(self):
        staff_user = User.objects.create_user(username='test', is_staff=True)
        self.client.force_authenticate(staff_user)
        response = self.client.post('/api/tickets/')
        self.assertEqual(response.status_code, HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {
            'queue': [ErrorDetail(string='This field is required.', code='required')],
            'title': [ErrorDetail(string='This field is required.', code='required')]
        })
        self.assertFalse(Ticket.objects.exists())

    def test_create_api_ticket_wrong_date_format(self):
        staff_user = User.objects.create_user(username='test', is_staff=True)
        self.client.force_authenticate(staff_user)
        response = self.client.post('/api/tickets/', {
            'queue': self.queue.id,
            'title': 'Test title',
            'due_date': 'monday, 1st of may 2022'
        })
        self.assertEqual(response.status_code, HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {
            'due_date': [ErrorDetail(string='Datetime has wrong format. Use one of these formats instead: YYYY-MM-DDThh:mm[:ss[.uuuuuu]][+HH:MM|-HH:MM|Z].', code='invalid')]
        })
        self.assertFalse(Ticket.objects.exists())

    def test_create_api_ticket_authenticated_staff_user(self):
        staff_user = User.objects.create_user(username='test', is_staff=True)
        self.client.force_authenticate(staff_user)
        response = self.client.post('/api/tickets/', {
            'queue': self.queue.id,
            'title': 'Test title',
            'description': 'Test description\nMulti lines',
            'submitter_email': 'test@mail.com',
            'priority': 4
        })
        self.assertEqual(response.status_code, HTTP_201_CREATED)
        created_ticket = Ticket.objects.get()
        self.assertEqual(created_ticket.title, 'Test title')
        self.assertEqual(created_ticket.description, 'Test description\nMulti lines')
        self.assertEqual(created_ticket.submitter_email, 'test@mail.com')
        self.assertEqual(created_ticket.priority, 4)

    def test_create_api_ticket_with_basic_auth(self):
        username = 'admin'
        password = 'admin'
        User.objects.create_user(username=username, password=password, is_staff=True)

        test_user = User.objects.create_user(username='test')
        merge_ticket = Ticket.objects.create(queue=self.queue, title='merge ticket')

        # Generate base64 credentials string
        credentials = f"{username}:{password}"
        base64_credentials = base64.b64encode(credentials.encode(HTTP_HEADER_ENCODING)).decode(HTTP_HEADER_ENCODING)

        self.client.credentials(HTTP_AUTHORIZATION=f"Basic {base64_credentials}")
        response = self.client.post(
            '/api/tickets/',
            {
                'queue': self.queue.id,
                'title': 'Title',
                'description': 'Description',
                'resolution': 'Resolution',
                'assigned_to': test_user.id,
                'submitter_email': 'test@mail.com',
                'status': Ticket.RESOLVED_STATUS,
                'priority': 1,
                'on_hold': True,
                'due_date': datetime(2022, 4, 10, 15, 6),
                'merged_to': merge_ticket.id
            }
        )

        self.assertEqual(response.status_code, HTTP_201_CREATED)
        created_ticket = Ticket.objects.last()
        self.assertEqual(created_ticket.title, 'Title')
        self.assertEqual(created_ticket.description, 'Description')
        self.assertIsNone(created_ticket.resolution)  # resolution can not be set on creation
        self.assertEqual(created_ticket.assigned_to, test_user)
        self.assertEqual(created_ticket.submitter_email, 'test@mail.com')
        self.assertEqual(created_ticket.priority, 1)
        self.assertFalse(created_ticket.on_hold)  # on_hold is False on creation
        self.assertEqual(created_ticket.status, Ticket.OPEN_STATUS)  # status is always open on creation
        self.assertEqual(created_ticket.due_date, datetime(2022, 4, 10, 15, 6, tzinfo=UTC))
        self.assertIsNone(created_ticket.merged_to)  # merged_to can not be set on creation

    def test_edit_api_ticket(self):
        staff_user = User.objects.create_user(username='admin', is_staff=True)
        test_ticket = Ticket.objects.create(queue=self.queue, title='Test ticket')

        test_user = User.objects.create_user(username='test')
        merge_ticket = Ticket.objects.create(queue=self.queue, title='merge ticket')

        self.client.force_authenticate(staff_user)
        response = self.client.put(
            '/api/tickets/%d/' % test_ticket.id,
            {
                'queue': self.queue.id,
                'title': 'Title',
                'description': 'Description',
                'resolution': 'Resolution',
                'assigned_to': test_user.id,
                'submitter_email': 'test@mail.com',
                'status': Ticket.RESOLVED_STATUS,
                'priority': 1,
                'on_hold': True,
                'due_date': datetime(2022, 4, 10, 15, 6),
                'merged_to': merge_ticket.id
            }
        )

        self.assertEqual(response.status_code, HTTP_200_OK)
        test_ticket.refresh_from_db()
        self.assertEqual(test_ticket.title, 'Title')
        self.assertEqual(test_ticket.description, 'Description')
        self.assertEqual(test_ticket.resolution, 'Resolution')
        self.assertEqual(test_ticket.assigned_to, test_user)
        self.assertEqual(test_ticket.submitter_email, 'test@mail.com')
        self.assertEqual(test_ticket.priority, 1)
        self.assertTrue(test_ticket.on_hold)
        self.assertEqual(test_ticket.status, Ticket.RESOLVED_STATUS)
        self.assertEqual(test_ticket.due_date, datetime(2022, 4, 10, 15, 6, tzinfo=UTC))
        self.assertEqual(test_ticket.merged_to, merge_ticket)

    def test_partial_edit_api_ticket(self):
        staff_user = User.objects.create_user(username='admin', is_staff=True)
        test_ticket = Ticket.objects.create(queue=self.queue, title='Test ticket')

        self.client.force_authenticate(staff_user)
        response = self.client.patch(
            '/api/tickets/%d/' % test_ticket.id,
            {
                'description': 'New description',
            }
        )

        self.assertEqual(response.status_code, HTTP_200_OK)
        test_ticket.refresh_from_db()
        self.assertEqual(test_ticket.description, 'New description')

    def test_delete_api_ticket(self):
        staff_user = User.objects.create_user(username='admin', is_staff=True)
        test_ticket = Ticket.objects.create(queue=self.queue, title='Test ticket')
        self.client.force_authenticate(staff_user)
        response = self.client.delete('/api/tickets/%d/' % test_ticket.id)
        self.assertEqual(response.status_code, HTTP_204_NO_CONTENT)
        self.assertFalse(Ticket.objects.exists())

    def test_create_api_ticket_with_custom_fields(self):
        # Create custom fields
        for field_type, field_display in CustomField.DATA_TYPE_CHOICES:
            extra_data = {}
            if field_type in ('varchar', 'text'):
                extra_data['max_length'] = 10
            if field_type == 'integer':
                # Set one field as required to test error if not provided
                extra_data['required'] = True
            if field_type == 'decimal':
                extra_data['max_length'] = 7
                extra_data['decimal_places'] = 3
            if field_type == 'list':
                extra_data['list_values'] = '''Green
                Blue
                Red
                Yellow'''
            CustomField.objects.create(name=field_type, label=field_display, data_type=field_type, **extra_data)

        staff_user = User.objects.create_user(username='test', is_staff=True)
        self.client.force_authenticate(staff_user)

        # Test creation without providing required field
        response = self.client.post('/api/tickets/', {
            'queue': self.queue.id,
            'title': 'Test title',
            'description': 'Test description\nMulti lines',
            'submitter_email': 'test@mail.com',
            'priority': 4
        })
        self.assertEqual(response.status_code, HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {'custom_integer': [ErrorDetail(string='This field is required.', code='required')]})

        # Test creation with custom field values
        response = self.client.post('/api/tickets/', {
            'queue': self.queue.id,
            'title': 'Test title',
            'description': 'Test description\nMulti lines',
            'submitter_email': 'test@mail.com',
            'priority': 4,
            'custom_varchar': 'test',
            'custom_text': 'multi\nline',
            'custom_integer': '1',
            'custom_decimal': '42.987',
            'custom_list': 'Red',
            'custom_boolean': True,
            'custom_date': '2022-4-11',
            'custom_time': '23:59:59',
            'custom_datetime': '2022-4-10 18:27',
            'custom_email': 'email@test.com',
            'custom_url': 'http://django-helpdesk.readthedocs.org/',
            'custom_ipaddress': '127.0.0.1',
            'custom_slug': 'test-slug',
        })
        self.assertEqual(response.status_code, HTTP_201_CREATED)
        # Check all fields with data returned from the response
        self.assertEqual(response.data, {
            'id': 1,
            'queue': 1,
            'title': 'Test title',
            'description': 'Test description\nMulti lines',
            'resolution': None,
            'submitter_email': 'test@mail.com',
            'assigned_to': None,
            'status': 1,
            'on_hold': False,
            'priority': 4,
            'due_date': None,
            'merged_to': None,
            'custom_varchar': 'test',
            'custom_text': 'multi\nline',
            'custom_integer': 1,
            'custom_decimal': '42.987',
            'custom_list': 'Red',
            'custom_boolean': True,
            'custom_date': '2022-04-11',
            'custom_time': '23:59:59',
            'custom_datetime': '2022-04-10T18:27',
            'custom_email': 'email@test.com',
            'custom_url': 'http://django-helpdesk.readthedocs.org/',
            'custom_ipaddress': '127.0.0.1',
            'custom_slug': 'test-slug'
        })

