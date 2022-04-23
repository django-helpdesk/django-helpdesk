
import email
import uuid

from helpdesk.models import Queue, CustomField, FollowUp, Ticket, TicketCC, KBCategory, KBItem
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ObjectDoesNotExist
from django.forms import ValidationError
from django.test.client import Client
from django.urls import reverse

from helpdesk.email import object_from_message, create_ticket_cc
from helpdesk.tests.helpers import print_response

from urllib.parse import urlparse

import logging


logger = logging.getLogger('helpdesk')


class TicketBasicsTestCase(TestCase):
    fixtures = ['emailtemplate.json']

    def setUp(self):
        self.queue_public = Queue.objects.create(
            title='Queue 1',
            slug='q1',
            allow_public_submission=True,
            new_ticket_cc='new.public@example.com',
            updated_ticket_cc='update.public@example.com')
        self.queue_private = Queue.objects.create(
            title='Queue 2',
            slug='q2',
            allow_public_submission=False,
            new_ticket_cc='new.private@example.com',
            updated_ticket_cc='update.private@example.com')

        self.ticket_data = {
            'title': 'Test Ticket',
            'description': 'Some Test Ticket',
        }

        self.user = get_user_model().objects.create(
            username='User_1',
        )

        self.client = Client()

    def test_create_ticket_instance_from_payload(self):

        """
        Ensure that a <Ticket> instance is created whenever an email is sent to a public queue.
        """

        email_count = len(mail.outbox)
        ticket_data = dict(queue=self.queue_public, **self.ticket_data)
        ticket = Ticket.objects.create(**ticket_data)
        self.assertEqual(ticket.ticket_for_url, "q1-%s" % ticket.id)
        self.assertEqual(email_count, len(mail.outbox))

    def test_create_ticket_public(self):
        email_count = len(mail.outbox)

        response = self.client.get(reverse('helpdesk:home'))
        self.assertEqual(response.status_code, 200)

        post_data = {
            'title': 'Test ticket title',
            'queue': self.queue_public.id,
            'submitter_email': 'ticket1.submitter@example.com',
            'body': 'Test ticket body',
            'priority': 3,
        }

        response = self.client.post(reverse('helpdesk:home'), post_data, follow=True)
        last_redirect = response.redirect_chain[-1]
        last_redirect_url = last_redirect[0]
        # last_redirect_status = last_redirect[1]

        # Ensure we landed on the "View" page.
        # Django 1.9 compatible way of testing this
        # https://docs.djangoproject.com/en/1.9/releases/1.9/#http-redirects-no-longer-forced-to-absolute-uris
        urlparts = urlparse(last_redirect_url)
        self.assertEqual(urlparts.path, reverse('helpdesk:public_view'))

        # Ensure submitter, new-queue + update-queue were all emailed.
        self.assertEqual(email_count + 3, len(mail.outbox))

        ticket = Ticket.objects.last()
        self.assertEqual(ticket.followup_set.count(), 1)
        # Follow up is anonymous
        self.assertIsNone(ticket.followup_set.first().user)


    def test_create_ticket_public_with_hidden_fields(self):
        email_count = len(mail.outbox)

        response = self.client.get(reverse('helpdesk:home'))
        self.assertEqual(response.status_code, 200)

        post_data = {
            'title': 'Test ticket title',
            'queue': self.queue_public.id,
            'submitter_email': 'ticket1.submitter@example.com',
            'body': 'Test ticket body',
            'priority': 4,
        }

        response = self.client.post(reverse('helpdesk:home') + "?_hide_fields_=priority", post_data, follow=True)
        ticket = Ticket.objects.last()
        self.assertEqual(ticket.priority, 4)


    def test_create_ticket_authorized(self):
        email_count = len(mail.outbox)
        self.client.force_login(self.user)

        response = self.client.get(reverse('helpdesk:home'))
        self.assertEqual(response.status_code, 200)

        post_data = {
            'title': 'Test ticket title',
            'queue': self.queue_public.id,
            'submitter_email': 'ticket1.submitter@example.com',
            'body': 'Test ticket body',
            'priority': 3,
        }

        response = self.client.post(reverse('helpdesk:home'), post_data, follow=True)
        last_redirect = response.redirect_chain[-1]
        last_redirect_url = last_redirect[0]
        # last_redirect_status = last_redirect[1]

        # Ensure we landed on the "View" page.
        # Django 1.9 compatible way of testing this
        # https://docs.djangoproject.com/en/1.9/releases/1.9/#http-redirects-no-longer-forced-to-absolute-uris
        urlparts = urlparse(last_redirect_url)
        self.assertEqual(urlparts.path, reverse('helpdesk:public_view'))

        # Ensure submitter, new-queue + update-queue were all emailed.
        self.assertEqual(email_count + 3, len(mail.outbox))

        ticket = Ticket.objects.last()
        self.assertEqual(ticket.followup_set.count(), 1)
        # Follow up is for registered user
        self.assertEqual(ticket.followup_set.first().user, self.user)

    def test_create_ticket_private(self):
        email_count = len(mail.outbox)
        post_data = {
            'title': 'Private ticket test',
            'queue': self.queue_private.id,
            'submitter_email': 'ticket2.submitter@example.com',
            'body': 'Test ticket body',
            'priority': 3,
        }

        response = self.client.post(reverse('helpdesk:home'), post_data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(email_count, len(mail.outbox))
        self.assertContains(response, 'Select a valid choice.')

    def test_create_ticket_customfields(self):
        email_count = len(mail.outbox)
        queue_custom = Queue.objects.create(
            title='Queue 3',
            slug='q3',
            allow_public_submission=True,
            updated_ticket_cc='update.custom@example.com')
        custom_field_1 = CustomField.objects.create(
            name='textfield',
            label='Text Field',
            data_type='varchar',
            max_length=100,
            ordering=10,
            required=False,
            staff_only=False)
        post_data = {
            'queue': queue_custom.id,
            'title': 'Ticket with custom text field',
            'submitter_email': 'ticket3.submitter@example.com',
            'body': 'Test ticket body',
            'priority': 3,
            'custom_textfield': 'This is my custom text.',
        }

        response = self.client.post(reverse('helpdesk:home'), post_data, follow=True)

        custom_field_1.delete()
        last_redirect = response.redirect_chain[-1]
        last_redirect_url = last_redirect[0]
        # last_redirect_status = last_redirect[1]

        # Ensure we landed on the "View" page.
        # Django 1.9 compatible way of testing this
        # https://docs.djangoproject.com/en/1.9/releases/1.9/#http-redirects-no-longer-forced-to-absolute-uris
        urlparts = urlparse(last_redirect_url)
        self.assertEqual(urlparts.path, reverse('helpdesk:public_view'))

        # Ensure only two e-mails were sent - submitter & updated.
        self.assertEqual(email_count + 2, len(mail.outbox))

    def test_create_ticket_public_no_loopback(self):
        """
        Don't send emails to the queue's own inbox. It'll create a loop.
        """
        email_count = len(mail.outbox)

        self.queue_public.email_address = "queue@example.com"
        self.queue_public.save()

        post_data = {
            'title': 'Test ticket title',
            'queue': self.queue_public.id,
            'submitter_email': 'queue@example.com',
            'body': 'Test ticket body',
            'priority': 3,
        }

        response = self.client.post(reverse('helpdesk:home'), post_data, follow=True)
        last_redirect = response.redirect_chain[-1]
        last_redirect_url = last_redirect[0]
        # last_redirect_status = last_redirect[1]

        # Ensure we landed on the "View" page.
        # Django 1.9 compatible way of testing this
        # https://docs.djangoproject.com/en/1.9/releases/1.9/#http-redirects-no-longer-forced-to-absolute-uris
        urlparts = urlparse(last_redirect_url)
        self.assertEqual(urlparts.path, reverse('helpdesk:public_view'))

        # Ensure submitter, new-queue + update-queue were all emailed.
        self.assertEqual(email_count + 2, len(mail.outbox))


class EmailInteractionsTestCase(TestCase):
    fixtures = ['emailtemplate.json']

    def setUp(self):
        self.queue_public = Queue.objects.create(
            title='Mail Queue 1',
            slug='mq1',
            email_address='queue-1@example.com',
            allow_public_submission=True,
            new_ticket_cc='new.public.with.notifications@example.com',
            updated_ticket_cc='update.public.with.notifications@example.com',
            enable_notifications_on_email_events=True,
        )

        self.queue_public_with_notifications_disabled = Queue.objects.create(
            title='Mail Queue 2',
            slug='mq2',
            email_address='queue-2@example.com',
            allow_public_submission=True,
            new_ticket_cc='new.public.without.notifications@example.com',
            updated_ticket_cc='update.public.without.notifications@example.com',
            enable_notifications_on_email_events=False,
        )

        self.ticket_data = {
            'title': 'Test Ticket',
            'description': 'Some Test Ticket',
        }

    def test_create_ticket_from_email_with_message_id(self):

        """
        Ensure that a <Ticket> instance is created whenever an email is sent to a public queue.
        Also, make sure that the RFC 2822 field "message-id" is stored on the <Ticket.submitter_email_id>
        field.
        """

        msg = email.message.Message()

        message_id = uuid.uuid4().hex
        submitter_email = 'foo@bar.py'

        msg.__setitem__('Message-ID', message_id)
        msg.__setitem__('Subject', self.ticket_data['title'])
        msg.__setitem__('From', submitter_email)
        msg.__setitem__('To', self.queue_public.email_address)
        msg.__setitem__('Content-Type', 'text/plain;')
        msg.set_payload(self.ticket_data['description'])

        email_count = len(mail.outbox)

        object_from_message(str(msg), self.queue_public, logger=logger)

        followup = FollowUp.objects.get(message_id=message_id)
        ticket = Ticket.objects.get(id=followup.ticket.id)

        self.assertEqual(ticket.ticket_for_url, "mq1-%s" % ticket.id)

        # As we have created an Ticket from an email, we notify the sender (+1)
        # and the new and update queues (+2)
        self.assertEqual(email_count + 1 + 2, len(mail.outbox))

        # Ensure that the submitter is notified
        self.assertIn(submitter_email, mail.outbox[0].to)

    def test_create_ticket_from_email_without_message_id(self):

        """
        Ensure that a <Ticket> instance is created whenever an email is sent to a public queue.
        Also, make sure that the RFC 2822 field "message-id" is stored on the <Ticket.submitter_email_id>
        field.
        """

        msg = email.message.Message()
        submitter_email = 'foo@bar.py'

        msg.__setitem__('Subject', self.ticket_data['title'])
        msg.__setitem__('From', submitter_email)
        msg.__setitem__('To', self.queue_public.email_address)
        msg.__setitem__('Content-Type', 'text/plain;')
        msg.set_payload(self.ticket_data['description'])

        email_count = len(mail.outbox)

        object_from_message(str(msg), self.queue_public, logger=logger)

        ticket = Ticket.objects.get(title=self.ticket_data['title'], queue=self.queue_public, submitter_email=submitter_email)

        self.assertEqual(ticket.ticket_for_url, "mq1-%s" % ticket.id)

        # As we have created an Ticket from an email, we notify the sender (+1)
        # and the new and update queues (+2)
        self.assertEqual(email_count + 1 + 2, len(mail.outbox))

        # Ensure that the submitter is notified
        self.assertIn(submitter_email, mail.outbox[0].to)

    def test_create_ticket_from_email_with_carbon_copy(self):
        """
        Ensure that an instance of <TicketCC> is created for every valid element of the
        "rfc_2822_cc" field when creating a <Ticket> instance.
        """

        msg = email.message.Message()

        message_id = uuid.uuid4().hex
        submitter_email = 'foo@bar.py'
        cc_list = ['bravo@example.net', 'charlie@foobar.com']

        msg.__setitem__('Message-ID', message_id)
        msg.__setitem__('Subject', self.ticket_data['title'])
        msg.__setitem__('From', submitter_email)
        msg.__setitem__('To', self.queue_public.email_address)
        msg.__setitem__('Cc', ','.join(cc_list))
        msg.__setitem__('Content-Type', 'text/plain;')
        msg.set_payload(self.ticket_data['description'])

        email_count = len(mail.outbox)

        object_from_message(str(msg), self.queue_public, logger=logger)

        followup = FollowUp.objects.get(message_id=message_id)
        ticket = Ticket.objects.get(id=followup.ticket.id)
        self.assertEqual(ticket.ticket_for_url, "mq1-%s" % ticket.id)

        # As we have created an Ticket from an email, we notify:
        # the sender (+1),
        # contacts on the cc_list (+2),
        # the new and update queues (+2)
        self.assertEqual(email_count + 1 + 2 + 2, len(mail.outbox))

        # Ensure that the submitter is notified
        self.assertIn(submitter_email, mail.outbox[0].to)

        for cc_email in cc_list:

            # Ensure that contacts on cc_list will be notified on the same email (index 0)
            # self.assertIn(cc_email, mail.outbox[0].to)

            # Ensure that <TicketCC> exists
            ticket_cc = TicketCC.objects.get(ticket=ticket, email=cc_email)
            self.assertTrue(ticket_cc.ticket, ticket)
            self.assertTrue(ticket_cc.email, cc_email)

    def test_create_ticket_from_email_to_multiple_emails(self):
        """
        Ensure that an instance of <TicketCC> is created for every valid element of the
        "rfc_2822_cc" field when creating a <Ticket> instance.
        """

        msg = email.message.Message()

        message_id = uuid.uuid4().hex
        submitter_email = 'foo@bar.py'
        to_list = [self.queue_public.email_address]
        cc_list = ['bravo@example.net', 'charlie@foobar.com']

        msg.__setitem__('Message-ID', message_id)
        msg.__setitem__('Subject', self.ticket_data['title'])
        msg.__setitem__('From', submitter_email)
        msg.__setitem__('To', ','.join(to_list + cc_list))
        msg.__setitem__('Content-Type', 'text/plain;')
        msg.set_payload(self.ticket_data['description'])

        email_count = len(mail.outbox)

        object_from_message(str(msg), self.queue_public, logger=logger)

        followup = FollowUp.objects.get(message_id=message_id)
        ticket = Ticket.objects.get(id=followup.ticket.id)
        self.assertEqual(ticket.ticket_for_url, "mq1-%s" % ticket.id)

        # As we have created an Ticket from an email, we notify:
        # the sender (+1),
        # contacts on the cc_list (+2),
        # the new and update queues (+2)
        self.assertEqual(email_count + 1 + 2 + 2, len(mail.outbox))

        # Ensure that the submitter is notified
        self.assertIn(submitter_email, mail.outbox[0].to)

        # Ensure that the queue's email was not subscribed to the event notifications.
        self.assertRaises(TicketCC.DoesNotExist, TicketCC.objects.get, ticket=ticket, email=to_list[0])

        for cc_email in cc_list:

            # Ensure that contacts on cc_list will be notified on the same email (index 0)
            # self.assertIn(cc_email, mail.outbox[0].to)

            # Ensure that <TicketCC> exists
            ticket_cc = TicketCC.objects.get(ticket=ticket, email=cc_email)
            self.assertTrue(ticket_cc.ticket, ticket)
            self.assertTrue(ticket_cc.email, cc_email)

    def test_create_ticket_from_email_with_invalid_carbon_copy(self):
        """
        Ensure that no <TicketCC> instance is created if an invalid element of the
        "rfc_2822_cc" field is provided when creating a <Ticket> instance.
        """

        msg = email.message.Message()

        message_id = uuid.uuid4().hex
        submitter_email = 'foo@bar.py'
        cc_list = ['null@example', 'invalid@foobar']

        msg.__setitem__('Message-ID', message_id)
        msg.__setitem__('Subject', self.ticket_data['title'])
        msg.__setitem__('From', submitter_email)
        msg.__setitem__('To', self.queue_public.email_address)
        msg.__setitem__('Cc', ','.join(cc_list))
        msg.__setitem__('Content-Type', 'text/plain;')
        msg.set_payload(self.ticket_data['description'])

        email_count = len(mail.outbox)

        object_from_message(str(msg), self.queue_public, logger=logger)

        followup = FollowUp.objects.get(message_id=message_id)
        ticket = Ticket.objects.get(id=followup.ticket.id)
        self.assertEqual(ticket.ticket_for_url, "mq1-%s" % ticket.id)

        # As we have created an Ticket from an email, we notify:
        # the submitter (+1)
        # contacts on the cc_list (+2),
        # the new and update queues (+2)
        self.assertEqual(email_count + 1 + 2 + 2, len(mail.outbox))

        # Ensure that the submitter is notified
        self.assertIn(submitter_email, mail.outbox[0].to)

        for cc_email in cc_list:

            # Ensure that contacts on cc_list will be notified on the same email (index 0)
            # self.assertIn(cc_email, mail.outbox[0].to)

            # Ensure that <TicketCC> exists. Even if it's an invalid email.
            ticket_cc = TicketCC.objects.get(ticket=ticket, email=cc_email)
            self.assertTrue(ticket_cc.ticket, ticket)
            self.assertTrue(ticket_cc.email, cc_email)

    def test_create_followup_from_email_with_valid_message_id_with_no_initial_cc_list(self):
        """
        Ensure that if a message is received with an valid In-Reply-To ID,
        the expected <TicketCC> instances are created even if the there were
        no <TicketCC>s so far.
        """
        # Ticket and TicketCCs creation #
        msg = email.message.Message()

        message_id = uuid.uuid4().hex
        submitter_email = 'foo@bar.py'

        msg.__setitem__('Message-ID', message_id)
        msg.__setitem__('Subject', self.ticket_data['title'])
        msg.__setitem__('From', submitter_email)
        msg.__setitem__('To', self.queue_public.email_address)
        msg.__setitem__('Content-Type', 'text/plain;')
        msg.set_payload(self.ticket_data['description'])

        email_count = len(mail.outbox)

        object_from_message(str(msg), self.queue_public, logger=logger)

        followup = FollowUp.objects.get(message_id=message_id)
        ticket = Ticket.objects.get(id=followup.ticket.id)

        # As we have created an Ticket from an email, we notify the sender
        # and contacts on the cc_list (+1 as it's treated as a list),
        # the new and update queues (+2)

        # Ensure that the submitter is notified
        self.assertIn(submitter_email, mail.outbox[0].to)

        # As we have created an Ticket from an email, we notify the sender (+1)
        # and the new and update queues (+2)
        expected_email_count = 1 + 2
        self.assertEqual(expected_email_count, len(mail.outbox))
        # end of the Ticket and TicketCCs creation #

        # Reply message
        reply = email.message.Message()

        reply_message_id = uuid.uuid4().hex
        submitter_email = 'foo@bar.py'
        cc_list = ['bravo@example.net', 'charlie@foobar.com']

        reply.__setitem__('Message-ID', reply_message_id)
        reply.__setitem__('In-Reply-To', message_id)
        reply.__setitem__('Subject', self.ticket_data['title'])
        reply.__setitem__('From', submitter_email)
        reply.__setitem__('To', self.queue_public.email_address)
        reply.__setitem__('Cc', ','.join(cc_list))
        reply.__setitem__('Content-Type', 'text/plain;')
        reply.set_payload(self.ticket_data['description'])

        object_from_message(str(reply), self.queue_public, logger=logger)

        followup = FollowUp.objects.get(message_id=message_id)
        ticket = Ticket.objects.get(id=followup.ticket.id)
        self.assertEqual(ticket.ticket_for_url, "mq1-%s" % ticket.id)

        # Ensure that <TicketCC> is created
        for cc_email in cc_list:
            # Even after 2 messages with the same cc_list, <get> MUST return only
            # one object
            ticket_cc = TicketCC.objects.get(ticket=ticket, email=cc_email)
            self.assertTrue(ticket_cc.ticket, ticket)
            self.assertTrue(ticket_cc.email, cc_email)

        # As an update was made, we increase the expected_email_count with:
        # submitter: +1
        # cc_list: +2
        # public_update_queue: +1
        expected_email_count += 1 + 2 + 1
        self.assertEqual(expected_email_count, len(mail.outbox))

        # As we have created a FollowUp from an email, we notify:
        # the sender (+1),
        # contacts on the cc_list (+2),
        # the new and update queues (+2)

        # Ensure that the submitter is notified
        # self.assertIn(submitter_email, mail.outbox[expected_email_count - 3].to)

        # Ensure that contacts on cc_list will be notified on the same email (index 0)
        # for cc_email in cc_list:
        # self.assertIn(cc_email, mail.outbox[expected_email_count - 1].to)

    def test_create_followup_from_email_with_valid_message_id_with_original_cc_list_included(self):
        """
        Ensure that if a message is received with an valid In-Reply-To ID,
        the expected <TicketCC> instances are created but if there's any
        overlap with the previous Cc list, no duplicates are created.
        """
        # Ticket and TicketCCs creation #
        msg = email.message.Message()

        message_id = uuid.uuid4().hex
        submitter_email = 'foo@bar.py'
        cc_list = ['bravo@example.net', 'charlie@foobar.com']

        msg.__setitem__('Message-ID', message_id)
        msg.__setitem__('Subject', self.ticket_data['title'])
        msg.__setitem__('From', submitter_email)
        msg.__setitem__('To', self.queue_public.email_address)
        msg.__setitem__('Cc', ','.join(cc_list))
        msg.__setitem__('Content-Type', 'text/plain;')
        msg.set_payload(self.ticket_data['description'])

        email_count = len(mail.outbox)

        object_from_message(str(msg), self.queue_public, logger=logger)

        followup = FollowUp.objects.get(message_id=message_id)
        ticket = Ticket.objects.get(id=followup.ticket.id)

        # Ensure that <TicketCC> is created
        for cc_email in cc_list:
            ticket_cc = TicketCC.objects.get(ticket=ticket, email=cc_email)
            self.assertTrue(ticket_cc.ticket, ticket)
            self.assertTrue(ticket_cc.email, cc_email)
            self.assertTrue(ticket_cc.can_view, True)

        # As we have created a Ticket from an email, we notify the sender
        # and contacts on the cc_list (+1 as it's treated as a list),
        # the new and update queues (+2)
        # then each cc gets its own email? (+2)
        # TODO: check this is correct!

        # Ensure that the submitter is notified
        self.assertIn(submitter_email, mail.outbox[0].to)

        # As we have created an Ticket from an email, we notify the sender (+1)
        # and the new and update queues (+2)
        # then each cc gets its own email? (+2)
        expected_email_count = 1 + 2 + 2
        self.assertEqual(expected_email_count, len(mail.outbox))
        # end of the Ticket and TicketCCs creation #

        # Reply message
        reply = email.message.Message()

        reply_message_id = uuid.uuid4().hex
        submitter_email = 'foo@bar.py'
        cc_list = ['bravo@example.net', 'charlie@foobar.com']

        reply.__setitem__('Message-ID', reply_message_id)
        reply.__setitem__('In-Reply-To', message_id)
        reply.__setitem__('Subject', self.ticket_data['title'])
        reply.__setitem__('From', submitter_email)
        reply.__setitem__('To', self.queue_public.email_address)
        reply.__setitem__('Cc', ','.join(cc_list))
        reply.__setitem__('Content-Type', 'text/plain;')
        reply.set_payload(self.ticket_data['description'])

        object_from_message(str(reply), self.queue_public, logger=logger)

        followup = FollowUp.objects.get(message_id=message_id)
        ticket = Ticket.objects.get(id=followup.ticket.id)
        self.assertEqual(ticket.ticket_for_url, "mq1-%s" % ticket.id)

        # As an update was made, we increase the expected_email_count with:
        # public_update_queue: +1
        # since the submitter and the two ccs each get an email
        expected_email_count += 1 + 3
        self.assertEqual(expected_email_count, len(mail.outbox))

        # As we have created a FollowUp from an email, we notify the sender
        # and contacts on the cc_list (+1 as it's treated as a list),
        # the new and update queues (+2)

        # Ensure that the submitter is notified
        self.assertIn(submitter_email, mail.outbox[expected_email_count - 1].to)

        # Ensure that contacts on cc_list will be notified on the same email (index 0)
        for cc_email in cc_list:
            self.assertIn(cc_email, mail.outbox[expected_email_count - 1].to)

            # Even after 2 messages with the same cc_list,
            # <get> MUST return only one object
            ticket_cc = TicketCC.objects.get(ticket=ticket, email=cc_email)
            self.assertTrue(ticket_cc.ticket, ticket)
            self.assertTrue(ticket_cc.email, cc_email)

    def test_create_followup_from_email_with_invalid_message_id(self):
        """
        Ensure that if a message is received with an invalid In-Reply-To
        ID and we can infer the original Ticket ID by the message's subject,
        the expected <TicketCC> instances are created.
        """

        # Ticket and TicketCCs creation #
        msg = email.message.Message()

        message_id = uuid.uuid4().hex
        submitter_email = 'foo@bar.py'
        cc_list = ['bravo@example.net', 'charlie@foobar.com']

        msg.__setitem__('Message-ID', message_id)
        msg.__setitem__('Subject', self.ticket_data['title'])
        msg.__setitem__('From', submitter_email)
        msg.__setitem__('To', self.queue_public.email_address)
        msg.__setitem__('Cc', ','.join(cc_list))
        msg.__setitem__('Content-Type', 'text/plain;')
        msg.set_payload(self.ticket_data['description'])

        email_count = len(mail.outbox)

        object_from_message(str(msg), self.queue_public, logger=logger)

        followup = FollowUp.objects.get(message_id=message_id)
        ticket = Ticket.objects.get(id=followup.ticket.id)

        # Ensure that <TicketCC> is created
        for cc_email in cc_list:
            ticket_cc = TicketCC.objects.get(ticket=ticket, email=cc_email)
            self.assertTrue(ticket_cc.ticket, ticket)
            self.assertTrue(ticket_cc.email, cc_email)
            self.assertTrue(ticket_cc.can_view, True)

        # As we have created an Ticket from an email, we notify:
        # the sender (+1),
        # contacts on the cc_list (+2),
        # the new and update queues (+2)
        expected_email_count = 1 + 2 + 2
        self.assertEqual(expected_email_count, len(mail.outbox))

        # Ensure that the submitter is notified
        self.assertIn(submitter_email, mail.outbox[0].to)

        # Ensure that <TicketCC> is created
        for cc_email in cc_list:

            # Ensure that contacts on cc_list will be notified on the same email (index 0)
            # self.assertIn(cc_email, mail.outbox[0].to)

            ticket_cc = TicketCC.objects.get(ticket=ticket, email=cc_email)
            self.assertTrue(ticket_cc.ticket, ticket)
            self.assertTrue(ticket_cc.email, cc_email)

        # end of the Ticket and TicketCCs creation #

        # Reply message
        reply = email.message.Message()

        reply_message_id = uuid.uuid4().hex
        submitter_email = 'foo@bar.py'
        cc_list = ['bravo@example.net', 'charlie@foobar.com']

        invalid_message_id = 'INVALID'
        reply_subject = 'Re: ' + self.ticket_data['title']

        reply.__setitem__('Message-ID', reply_message_id)
        reply.__setitem__('In-Reply-To', invalid_message_id)
        reply.__setitem__('Subject', reply_subject)
        reply.__setitem__('From', submitter_email)
        reply.__setitem__('To', self.queue_public.email_address)
        reply.__setitem__('Cc', ','.join(cc_list))
        reply.__setitem__('Content-Type', 'text/plain;')
        reply.set_payload(self.ticket_data['description'])

        email_count = len(mail.outbox)

        object_from_message(str(reply), self.queue_public, logger=logger)

        followup = FollowUp.objects.get(message_id=message_id)
        ticket = Ticket.objects.get(id=followup.ticket.id)
        self.assertEqual(ticket.ticket_for_url, "mq1-%s" % ticket.id)

        # Ensure that <TicketCC> is created
        for cc_email in cc_list:
            # Even after 2 messages with the same cc_list, <get> MUST return only
            # one object
            ticket_cc = TicketCC.objects.get(ticket=ticket, email=cc_email)
            self.assertTrue(ticket_cc.ticket, ticket)
            self.assertTrue(ticket_cc.email, cc_email)

        # As we have created an Ticket from an email, we notify:
        # the sender (+1),
        # contacts on the cc_list (+2),
        # the new and update queues (+2)
        self.assertEqual(email_count + 1 + 2 + 2, len(mail.outbox))

    def test_create_ticket_from_email_to_a_notification_enabled_queue(self):
        """
            Ensure that when an email is sent to a Queue with
            notifications_enabled turned ON, and a <Ticket> is created, all
            contacts in the TicketCC list are notified.
        """

        msg = email.message.Message()

        message_id = uuid.uuid4().hex
        submitter_email = 'foo@bar.py'
        cc_list = ['bravo@example.net', 'charlie@foobar.com']

        msg.__setitem__('Message-ID', message_id)
        msg.__setitem__('Subject', self.ticket_data['title'])
        msg.__setitem__('From', submitter_email)
        msg.__setitem__('To', self.queue_public.email_address)
        msg.__setitem__('Cc', ','.join(cc_list))
        msg.__setitem__('Content-Type', 'text/plain;')
        msg.set_payload(self.ticket_data['description'])

        email_count = len(mail.outbox)
        object_from_message(str(msg), self.queue_public, logger=logger)

        followup = FollowUp.objects.get(message_id=message_id)
        ticket = Ticket.objects.get(id=followup.ticket.id)
        self.assertEqual(ticket.ticket_for_url, "mq1-%s" % ticket.id)

        # As we have created an Ticket from an email, we notify:
        # the sender (+1),
        # contacts on the cc_list (+2),
        # the new and update queues (+2)
        self.assertEqual(email_count + 1 + 2 + 2, len(mail.outbox))

        # Ensure that the submitter is notified
        self.assertIn(submitter_email, mail.outbox[0].to)

        # Ensure that <TicketCC> exist
        for cc_email in cc_list:

            # Ensure that contacts on cc_list will be notified on the same email (index 0)
            # self.assertIn(cc_email, mail.outbox[0].to)

            ticket_cc = TicketCC.objects.get(ticket=ticket, email=cc_email)
            self.assertTrue(ticket_cc.ticket, ticket)
            self.assertTrue(ticket_cc.email, cc_email)

    def test_create_ticket_from_email_to_a_notification_disabled_queue(self):
        """
            Ensure that when an email is sent to a Queue with notifications_enabled
            turned OFF, only the new_ticket_cc and updated_ticket_cc contacts (if
            they are set) are notified. No contact from the TicketCC list should
            be notified.
        """

        msg = email.message.Message()

        message_id = uuid.uuid4().hex
        submitter_email = 'foo@bar.py'
        cc_list = ['bravo@example.net', 'charlie@foobar.com']

        msg.__setitem__('Message-ID', message_id)
        msg.__setitem__('Subject', self.ticket_data['title'])
        msg.__setitem__('From', submitter_email)
        msg.__setitem__('To', self.queue_public_with_notifications_disabled.email_address)
        msg.__setitem__('Cc', ','.join(cc_list))
        msg.__setitem__('Content-Type', 'text/plain;')
        msg.set_payload(self.ticket_data['description'])

        email_count = len(mail.outbox)

        object_from_message(str(msg), self.queue_public_with_notifications_disabled, logger=logger)

        followup = FollowUp.objects.get(message_id=message_id)
        ticket = Ticket.objects.get(id=followup.ticket.id)
        self.assertEqual(ticket.ticket_for_url, "mq2-%s" % ticket.id)

        # As we have created an Ticket from an email, we notify:
        # the sender (+1),
        # the new and update queues (+2),
        # and that's it because we've disabled queue notifications
        self.assertEqual(email_count + 1 + 2, len(mail.outbox))

        # Ensure that <TicketCC> is created even if the Queue notifications are disabled
        # so when staff members interact with the <Ticket>, they get notified
        for cc_email in cc_list:

            # Ensure that contacts on the cc_list are not notified
            self.assertNotIn(cc_email, mail.outbox[0].to)

            ticket_cc = TicketCC.objects.get(ticket=ticket, email=cc_email)
            self.assertTrue(ticket_cc.ticket, ticket)
            self.assertTrue(ticket_cc.email, cc_email)

    def test_create_followup_from_email_to_a_notification_enabled_queue(self):
        """
            Ensure that when an email is sent to a Queue with notifications_enabled
            turned ON, and a <FollowUp> is created, all contacts n the TicketCC
            list are notified.
        """
        # Ticket and TicketCCs creation #
        msg = email.message.Message()

        message_id = uuid.uuid4().hex
        submitter_email = 'foo@bar.py'
        cc_list = ['bravo@example.net', 'charlie@foobar.com']

        msg.__setitem__('Message-ID', message_id)
        msg.__setitem__('Subject', self.ticket_data['title'])
        msg.__setitem__('From', submitter_email)
        msg.__setitem__('To', self.queue_public.email_address)
        msg.__setitem__('Cc', ','.join(cc_list))
        msg.__setitem__('Content-Type', 'text/plain;')
        msg.set_payload(self.ticket_data['description'])

        email_count = len(mail.outbox)

        object_from_message(str(msg), self.queue_public, logger=logger)

        followup = FollowUp.objects.get(message_id=message_id)
        ticket = Ticket.objects.get(id=followup.ticket.id)
        self.assertEqual(ticket.ticket_for_url, "mq1-%s" % ticket.id)

        # As we have created an Ticket from an email, we notify:
        # the sender (+1),
        # contacts on the cc_list (+2),
        # the new and update queues (+2)
        expected_email_count = email_count + 1 + 2 + 2
        self.assertEqual(expected_email_count, len(mail.outbox))

        # Ensure that <TicketCC> is created
        for cc_email in cc_list:

            # Ensure that contacts on cc_list will be notified on the same email (index 0)
            # self.assertIn(cc_email, mail.outbox[0].to)

            ticket_cc = TicketCC.objects.get(ticket=ticket, email=cc_email)
            self.assertTrue(ticket_cc.ticket, ticket)
            self.assertTrue(ticket_cc.email, cc_email)
        # end of the Ticket and TicketCCs creation #

        # Reply message
        reply = email.message.Message()

        reply_message_id = uuid.uuid4().hex
        submitter_email = 'bravo@example.net'

        reply.__setitem__('Message-ID', reply_message_id)
        reply.__setitem__('In-Reply-To', message_id)
        reply.__setitem__('Subject', self.ticket_data['title'])
        reply.__setitem__('From', submitter_email)
        reply.__setitem__('To', self.queue_public.email_address)
        reply.__setitem__('Content-Type', 'text/plain;')
        reply.set_payload(self.ticket_data['description'])

        object_from_message(str(reply), self.queue_public, logger=logger)

        followup = FollowUp.objects.get(message_id=message_id)
        ticket = Ticket.objects.get(id=followup.ticket.id)
        self.assertEqual(ticket.ticket_for_url, "mq1-%s" % ticket.id)

        # As an update was made, we increase the expected_email_count with:
        # submitter: +1
        # a new email to all TicketCC subscribers : +2
        # public_update_queue: +1
        expected_email_count += 1 + 2 + 1
        self.assertEqual(expected_email_count, len(mail.outbox))

        # Ensure that <TicketCC> exist
        for cc_email in cc_list:

            # Ensure that contacts on cc_list will be notified on the same email (index 0)
            # self.assertIn(cc_email, mail.outbox[expected_email_count - 1].to)

            ticket_cc = TicketCC.objects.get(ticket=ticket, email=cc_email)
            self.assertTrue(ticket_cc.ticket, ticket)
            self.assertTrue(ticket_cc.email, cc_email)

    def test_create_followup_from_email_to_a_notification_disabled_queue(self):
        """
            Ensure that when an email is sent to a Queue with notifications_enabled
            turned OFF, and a <FollowUp> is created, TicketCC is NOT notified.
        """
        # Ticket and TicketCCs creation #
        msg = email.message.Message()

        message_id = uuid.uuid4().hex
        submitter_email = 'foo@bar.py'
        cc_list = ['bravo@example.net', 'charlie@foobar.com']

        msg.__setitem__('Message-ID', message_id)
        msg.__setitem__('Subject', self.ticket_data['title'])
        msg.__setitem__('From', submitter_email)
        msg.__setitem__('To', self.queue_public_with_notifications_disabled.email_address)
        msg.__setitem__('Cc', ','.join(cc_list))
        msg.__setitem__('Content-Type', 'text/plain;')
        msg.set_payload(self.ticket_data['description'])

        email_count = len(mail.outbox)

        object_from_message(str(msg), self.queue_public_with_notifications_disabled, logger=logger)

        followup = FollowUp.objects.get(message_id=message_id)
        ticket = Ticket.objects.get(id=followup.ticket.id)
        self.assertEqual(ticket.ticket_for_url, "mq2-%s" % ticket.id)

        # As we have created an Ticket from an email, we notify:
        # the sender (+1),
        # the new and update queues (+2)
        expected_email_count = email_count + 1 + 2
        self.assertEqual(expected_email_count, len(mail.outbox))

        # Ensure that <TicketCC> is created
        for cc_email in cc_list:

            # Ensure that contacts on cc_list will not be notified
            self.assertNotIn(cc_email, mail.outbox[0].to)

            ticket_cc = TicketCC.objects.get(ticket=ticket, email=cc_email)
            self.assertTrue(ticket_cc.ticket, ticket)
            self.assertTrue(ticket_cc.email, cc_email)
        # end of the Ticket and TicketCCs creation #

        # Reply message
        reply = email.message.Message()

        reply_message_id = uuid.uuid4().hex
        submitter_email = 'bravo@example.net'

        reply.__setitem__('Message-ID', reply_message_id)
        reply.__setitem__('In-Reply-To', message_id)
        reply.__setitem__('Subject', self.ticket_data['title'])
        reply.__setitem__('From', submitter_email)
        reply.__setitem__('To', self.queue_public_with_notifications_disabled.email_address)
        reply.__setitem__('Content-Type', 'text/plain;')
        reply.set_payload(self.ticket_data['description'])

        object_from_message(str(reply), self.queue_public_with_notifications_disabled, logger=logger)

        followup = FollowUp.objects.get(message_id=message_id)
        ticket = Ticket.objects.get(id=followup.ticket.id)
        self.assertEqual(ticket.ticket_for_url, "mq2-%s" % ticket.id)

        # As an update was made, we increase the expected_email_count with:
        # public_update_queue: +1
        expected_email_count += 1
        self.assertEqual(expected_email_count, len(mail.outbox))

    def test_create_followup_from_email_with_valid_message_id_with_expected_cc(self):
        """
        Ensure that if a message is received with an valid In-Reply-To ID,
        the expected <TicketCC> instances are created even if the there were
        no <TicketCC>s so far.
        """

        # Ticket and TicketCCs creation #
        msg = email.message.Message()

        message_id = uuid.uuid4().hex
        submitter_email = 'foo@bar.py'

        msg.__setitem__('Message-ID', message_id)
        msg.__setitem__('Subject', self.ticket_data['title'])
        msg.__setitem__('From', submitter_email)
        msg.__setitem__('To', self.queue_public.email_address)
        msg.__setitem__('Content-Type', 'text/plain;')
        msg.set_payload(self.ticket_data['description'])

        email_count = len(mail.outbox)

        object_from_message(str(msg), self.queue_public, logger=logger)

        followup = FollowUp.objects.get(message_id=message_id)
        ticket = Ticket.objects.get(id=followup.ticket.id)
        # end of the Ticket and TicketCCs creation #

        # Reply message
        reply = email.message.Message()

        reply_message_id = uuid.uuid4().hex
        submitter_email = 'bravo@example.net'
        cc_list = ['foo@bar.py', 'charlie@foobar.com']

        reply.__setitem__('Message-ID', reply_message_id)
        reply.__setitem__('In-Reply-To', message_id)
        reply.__setitem__('Subject', self.ticket_data['title'])
        reply.__setitem__('From', submitter_email)
        reply.__setitem__('To', self.queue_public.email_address)
        reply.__setitem__('Cc', ','.join(cc_list))
        reply.__setitem__('Content-Type', 'text/plain;')
        reply.set_payload(self.ticket_data['description'])

        object_from_message(str(reply), self.queue_public, logger=logger)

        followup = FollowUp.objects.get(message_id=message_id)
        ticket = Ticket.objects.get(id=followup.ticket.id)
        self.assertEqual(ticket.ticket_for_url, "mq1-%s" % ticket.id)

        # Ensure that <TicketCC> is created
        for cc_email in cc_list:
            # Even after 2 messages with the same cc_list, <get> MUST return only
            # one object
            ticket_cc = TicketCC.objects.get(ticket=ticket, email=cc_email)
            self.assertTrue(ticket_cc.ticket, ticket)
            self.assertTrue(ticket_cc.email, cc_email)

        # As we have created an Ticket from an email, we notify the sender (+1)
        # and the new and update queues (+2)
        expected_email_count = 1 + 2

        # As an update was made, we increase the expected_email_count with:
        # submitter: +1
        # cc_list: +2
        # public_update_queue: +1
        expected_email_count += 1 + 2 + 1
        self.assertEqual(expected_email_count, len(mail.outbox))

    def test_ticket_field_autofill(self):
        cat = KBCategory.objects.create(
            title="Test Cat",
            slug="test_cat",
            description="This is a test category",
            queue=self.queue_public,
        )
        cat.save()
        self.kbitem1 = KBItem.objects.create(
            category=cat,
            title="KBItem 1",
            question="What?",
            answer="A KB Item",
        )
        self.kbitem1.save()
        cat_url = reverse('helpdesk:submit') + "?kbitem=1&submitter_email=foo@bar.cz&title=lol"
        response = self.client.get(cat_url)
        self.assertContains(response, '<option value="1" selected>KBItem 1</option>')
        self.assertContains(response, '<input type="email" name="submitter_email" value="foo@bar.cz" class="form-control form-control" required id="id_submitter_email">')
        self.assertContains(response, '<input type="text" name="title" value="lol" class="form-control form-control" maxlength="100" required id="id_title">')
