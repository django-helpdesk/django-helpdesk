from django.contrib.auth.models import User
from helpdesk.models import Queue, CustomField, TicketCustomFieldValue, Ticket
from helpdesk.serializers import TicketSerializer
from rest_framework.status import (
    HTTP_201_CREATED
)
from rest_framework.test import APITestCase
import json
import os
import requests
import logging

# Set up a test weberver listeining on localhost:8123 for webhooks
import http.server
import threading
from http import HTTPStatus

class WebhookRequestHandler(http.server.BaseHTTPRequestHandler):
    server: "WebhookServer"

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length)
        self.server.requests.append({
            'path': self.path,
            'headers': self.headers,
            'body': body
        })
        if self.path == '/new-ticket':
            self.server.handled_new_ticket_requests.append(json.loads(body.decode('utf-8')))
        if self.path == '/new-ticket-1':
            self.server.handled_new_ticket_requests_1.append(json.loads(body.decode('utf-8')))
        elif self.path == '/followup':
            self.server.handled_follow_up_requests.append(json.loads(body.decode('utf-8')))
        elif self.path == '/followup-1':
            self.server.handled_follow_up_requests_1.append(json.loads(body.decode('utf-8')))
        self.send_response(HTTPStatus.OK)
        self.end_headers()

    def do_GET(self):
        if not self.path == '/get-past-requests':
            self.send_response(HTTPStatus.NOT_FOUND)
            self.end_headers()
            return
        self.send_response(HTTPStatus.OK)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({
            'new_ticket_requests': self.server.handled_new_ticket_requests,
            'new_ticket_requests_1': self.server.handled_new_ticket_requests_1,
            'follow_up_requests': self.server.handled_follow_up_requests,
            'follow_up_requests_1': self.server.handled_follow_up_requests_1
        }).encode('utf-8'))


class WebhookServer(http.server.HTTPServer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.requests = []
        self.handled_new_ticket_requests = []
        self.handled_new_ticket_requests_1 = []
        self.handled_follow_up_requests = []
        self.handled_follow_up_requests_1 = []

    def start(self):
        self.thread = threading.Thread(target=self.serve_forever)
        self.thread.daemon = True  # Set as a daemon so it will be killed once the main thread is dead
        self.thread.start()

    def stop(self):
        self.shutdown()
        self.server_close()
        self.thread.join()


class WebhookTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.queue = Queue.objects.create(
            title='Test Queue',
            slug='test-queue',
        )

    def setUp(self):
        staff_user = User.objects.create_user(username='test', is_staff=True)
        CustomField(
            name="my_custom_field",
            data_type="varchar",
            required=False,
        ).save()
        self.client.force_authenticate(staff_user)

    def test_test_server(self):
        server = WebhookServer(('localhost', 8123), WebhookRequestHandler)
        server.start()
        requests.post('http://localhost:8123/new-ticket', json={
            "foo": "bar"})
        handled_webhook_requests = requests.get('http://localhost:8123/get-past-requests').json()
        self.assertEqual(handled_webhook_requests['new_ticket_requests'][-1]["foo"], "bar")
        server.stop()

    def test_create_ticket_and_followup_via_api(self):
        server = WebhookServer(('localhost', 8124), WebhookRequestHandler)
        os.environ['HELPDESK_NEW_TICKET_WEBHOOK_URLS'] = 'http://localhost:8124/new-ticket, http://localhost:8124/new-ticket-1'
        os.environ["HELPDESK_FOLLOWUP_WEBHOOK_URLS"] = 'http://localhost:8124/followup ,  http://localhost:8124/followup-1'
        server.start()

        response = self.client.post('/api/tickets/', {
            'queue': self.queue.id,
            'title': 'Test title',
            'description': 'Test description\nMulti lines',
            'submitter_email': 'test@mail.com',
            'priority': 4,
            'custom_my_custom_field': 'custom value',
        })
        self.assertEqual(CustomField.objects.all().first().name, "my_custom_field")
        self.assertEqual(TicketCustomFieldValue.objects.get(ticket=response.data['id']).value, 'custom value')
        self.assertEqual(response.status_code, HTTP_201_CREATED)
        handled_webhook_requests = requests.get('http://localhost:8124/get-past-requests')
        handled_webhook_requests = handled_webhook_requests.json()
        self.assertTrue(len(handled_webhook_requests['new_ticket_requests']) == 1)
        self.assertTrue(len(handled_webhook_requests['new_ticket_requests_1']) == 1)
        self.assertEqual(len(handled_webhook_requests['follow_up_requests']), 0)
        self.assertEqual(handled_webhook_requests['new_ticket_requests'][-1]["ticket"]["title"], "Test title")
        self.assertEqual(handled_webhook_requests['new_ticket_requests_1'][-1]["ticket"]["title"], "Test title")
        self.assertEqual(handled_webhook_requests['new_ticket_requests'][-1]["ticket"]["description"], "Test description\nMulti lines")
        ticket = Ticket.objects.get(id=handled_webhook_requests["new_ticket_requests"][-1]["ticket"]["id"])
        ticket.set_custom_field_values()
        serializer = TicketSerializer(ticket)
        self.assertEqual(
            list(sorted(serializer.fields.keys())),
            ['assigned_to',
             'attachment',
             'custom_my_custom_field',
             'description',
             'due_date',
             'followup_set',
             'id',
             'merged_to',
             'on_hold',
             'priority',
             'queue',
             'resolution',
             'status',
             'submitter_email',
             'title']
        )
        self.assertEqual(serializer.data, handled_webhook_requests["new_ticket_requests"][-1]["ticket"])
        response = self.client.post('/api/followups/', {
            'ticket': handled_webhook_requests['new_ticket_requests'][-1]["ticket"]["id"],
            "comment": "Test comment",
        })
        self.assertEqual(response.status_code, HTTP_201_CREATED)
        handled_webhook_requests = requests.get('http://localhost:8124/get-past-requests')
        handled_webhook_requests = handled_webhook_requests.json()
        self.assertEqual(len(handled_webhook_requests['follow_up_requests']), 1)
        self.assertEqual(len(handled_webhook_requests['follow_up_requests_1']), 1)
        self.assertEqual(handled_webhook_requests['follow_up_requests'][-1]["ticket"]["followup_set"][-1]["comment"], "Test comment")
        self.assertEqual(handled_webhook_requests['follow_up_requests_1'][-1]["ticket"]["followup_set"][-1]["comment"], "Test comment")
        
        server.stop()

    def test_create_ticket_and_followup_via_email(self):
        from .. import email

        server = WebhookServer(('localhost', 8125), WebhookRequestHandler)
        os.environ['HELPDESK_NEW_TICKET_WEBHOOK_URLS'] = 'http://localhost:8125/new-ticket'
        os.environ["HELPDESK_FOLLOWUP_WEBHOOK_URLS"] = 'http://localhost:8125/followup'
        server.start()
        class MockMessage(dict):
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

            def get_all(self, key, default=None):
                return self.__dict__.get(key, default)

        payload = {
          'body': "hello",
          'full_body': "hello",
          'subject': "Test subject",
          'queue': self.queue,
          'sender_email': "user@example.com",
          'priority': "1",
          'files': [],
        }

        message = {
            "To": ["info@example.com"],
            "Cc": [],
            "Message-Id": "random1",
            "In-Reply-To": "",
        }
        email.create_object_from_email_message(
            message=MockMessage(**message),
            ticket_id=None,
            payload=payload,
            files=[],
            logger=logging.getLogger('helpdesk'),
        )

        handled_webhook_requests = requests.get('http://localhost:8125/get-past-requests')
        handled_webhook_requests = handled_webhook_requests.json()
        self.assertEqual(len(handled_webhook_requests['new_ticket_requests']), 1)
        self.assertEqual(len(handled_webhook_requests['follow_up_requests']), 0)

        ticket_id = handled_webhook_requests['new_ticket_requests'][-1]["ticket"]['id']
        from .. import models
        ticket = models.Ticket.objects.get(id=ticket_id)

        payload = {
          'body': "hello",
          'full_body': "hello",
          'subject': f"[test-queue-{ticket_id}]  Test subject",
          'queue': self.queue,
          'sender_email': "user@example.com",
          'priority': "1",
          'files': [],
        }

        message = {
            "To": ["info@example.com"],
            "Cc": [],
            "Message-Id": "random",
            "In-Reply-To": "123",
        }
        email.create_object_from_email_message(
            message=MockMessage(**message),
            ticket_id=ticket_id,
            payload=payload,
            files=[],
            logger=logging.getLogger('helpdesk'),
        )
        handled_webhook_requests = requests.get('http://localhost:8125/get-past-requests')
        handled_webhook_requests = handled_webhook_requests.json()
        self.assertEqual(len(handled_webhook_requests['follow_up_requests']), 1)
        self.assertEqual(handled_webhook_requests['follow_up_requests'][-1]["ticket"]["followup_set"][-1]["comment"], "hello")
        self.assertEqual(handled_webhook_requests['follow_up_requests'][-1]["ticket"]["id"], ticket_id)

        server.stop()
