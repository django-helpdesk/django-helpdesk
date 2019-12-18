# vim: set fileencoding=utf-8 :
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.test import override_settings, TestCase
from django.utils.encoding import smart_text

from helpdesk import lib, models

import os
import shutil
from tempfile import gettempdir

from unittest import mock


MEDIA_DIR = os.path.join(gettempdir(), 'helpdesk_test_media')


@override_settings(MEDIA_ROOT=MEDIA_DIR)
class AttachmentIntegrationTests(TestCase):

    fixtures = ['emailtemplate.json']

    def setUp(self):
        self.queue_public = models.Queue.objects.create(
            title='Public Queue',
            slug='pub_q',
            allow_public_submission=True,
            new_ticket_cc='new.public@example.com',
            updated_ticket_cc='update.public@example.com',
        )

        self.queue_private = models.Queue.objects.create(
            title='Private Queue',
            slug='priv_q',
            allow_public_submission=False,
            new_ticket_cc='new.private@example.com',
            updated_ticket_cc='update.private@example.com',
        )

        self.ticket_data = {
            'title': 'Test Ticket Title',
            'body': 'Test Ticket Desc',
            'priority': 3,
            'submitter_email': 'submitter@example.com',
        }

    def test_create_pub_ticket_with_attachment(self):
        test_file = SimpleUploadedFile('test_att.txt', b'attached file content', 'text/plain')
        post_data = self.ticket_data.copy()
        post_data.update({
            'queue': self.queue_public.id,
            'attachment': test_file,
        })

        # Ensure ticket form submits with attachment successfully
        response = self.client.post(reverse('helpdesk:home'), post_data, follow=True)
        self.assertContains(response, test_file.name)

        # Ensure attachment is available with correct content
        att = models.FollowUpAttachment.objects.get(followup__ticket=response.context['ticket'])
        with open(os.path.join(MEDIA_DIR, att.file.name)) as file_on_disk:
            disk_content = file_on_disk.read()
        self.assertEqual(disk_content, 'attached file content')

    def test_create_pub_ticket_with_attachment_utf8(self):
        test_file = SimpleUploadedFile('ß°äöü.txt', 'โจ'.encode('utf-8'), 'text/utf-8')
        post_data = self.ticket_data.copy()
        post_data.update({
            'queue': self.queue_public.id,
            'attachment': test_file,
        })

        # Ensure ticket form submits with attachment successfully
        response = self.client.post(reverse('helpdesk:home'), post_data, follow=True)
        self.assertContains(response, test_file.name)

        # Ensure attachment is available with correct content
        att = models.FollowUpAttachment.objects.get(followup__ticket=response.context['ticket'])
        with open(os.path.join(MEDIA_DIR, att.file.name)) as file_on_disk:
            disk_content = smart_text(file_on_disk.read(), 'utf-8')
        self.assertEqual(disk_content, 'โจ')


@mock.patch.object(models.FollowUp, 'save', autospec=True)
@mock.patch.object(models.Ticket, 'save', autospec=True)
@mock.patch.object(models.Queue, 'save', autospec=True)
class AttachmentUnitTests(TestCase):

    def setUp(self):
        self.file_attrs = {
            'filename': '°ßäöü.txt',
            'content': 'โจ'.encode('utf-8'),
            'content-type': 'text/utf8',
        }
        self.test_file = SimpleUploadedFile.from_dict(self.file_attrs)
        self.follow_up = models.FollowUp(ticket=models.Ticket(queue=models.Queue()))

    @mock.patch('helpdesk.lib.FollowUpAttachment', autospec=True)
    def test_unicode_attachment_filename(self, mock_att_save, mock_queue_save, mock_ticket_save, mock_follow_up_save):
        """ check utf-8 data is parsed correctly """
        filename, fileobj = lib.process_attachments(self.follow_up, [self.test_file])[0]
        mock_att_save.assert_called_with(
            file=self.test_file,
            filename=self.file_attrs['filename'],
            mime_type=self.file_attrs['content-type'],
            size=len(self.file_attrs['content']),
            followup=self.follow_up
        )
        self.assertEqual(filename, self.file_attrs['filename'])

    # TODO: FIXME: what's wrong with this test that we get integrity errors?
    # @mock.patch('helpdesk.lib.FollowUpAttachment', autospec=True)
    # def test_autofill(self, mock_att_save, mock_queue_save, mock_ticket_save, mock_follow_up_save):
    #     """ check utf-8 data is parsed correctly """
    #     self.follow_up.pk = 100
    #     self.follow_up.save()
    #     obj = models.FollowUpAttachment.objects.create(
    #         followup=self.follow_up,
    #         file=self.test_file
    #     )
    #     self.assertEqual(obj.filename, self.file_attrs['filename'])
    #     self.assertEqual(obj.size, len(self.file_attrs['content']))
    #     self.assertEqual(obj.mime_type, "text/plain")

    def test_kbi_attachment(self, mock_att_save, mock_queue_save, mock_ticket_save):
        """ check utf-8 data is parsed correctly """

        kbcategory = models.KBCategory.objects.create(
            title="Title",
            slug="slug",
            description="Description"
        )
        kbitem = models.KBItem.objects.create(
            category=kbcategory,
            title="Title",
            question="Question",
            answer="Answer"
        )

        obj = models.KBIAttachment.objects.create(
            kbitem=kbitem,
            file=self.test_file
        )
        self.assertEqual(obj.filename, self.file_attrs['filename'])
        self.assertEqual(obj.size, len(self.file_attrs['content']))
        self.assertEqual(obj.mime_type, "text/plain")

    @mock.patch.object(lib.FollowUpAttachment, 'save', autospec=True)
    @override_settings(MEDIA_ROOT=MEDIA_DIR)
    def test_unicode_filename_to_filesystem(self, mock_att_save, mock_queue_save, mock_ticket_save, mock_follow_up_save):
        """ don't mock saving to filesystem to test file renames caused by storage layer """
        filename, fileobj = lib.process_attachments(self.follow_up, [self.test_file])[0]
        # Attachment object was zeroth positional arg (i.e. self) of att.save call
        attachment_obj = mock_att_save.call_args[0][0]

        mock_att_save.assert_called_once_with(attachment_obj)
        self.assertIsInstance(attachment_obj, models.FollowUpAttachment)
        self.assertEqual(attachment_obj.filename, self.file_attrs['filename'])


def tearDownModule():
    try:
        shutil.rmtree(MEDIA_DIR)
    except OSError:
        pass
