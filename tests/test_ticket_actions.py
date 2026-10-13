from typing import ClassVar

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.client import Client
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from helpdesk import settings as helpdesk_settings
from helpdesk.models import CustomField, Queue, Ticket
from helpdesk.templatetags.ticket_to_link import num_to_link
from helpdesk.user import HelpdeskUser

try:  # python 3
    from urllib.parse import urlparse
except ImportError:  # python 2
    from urlparse import urlparse

changed_field_msg_format = "Changed {0} from {1} to {2}."
status_value_to_title = {i[0]: i[1] for i in helpdesk_settings.TICKET_STATUS_CHOICES}


class TicketActionsTestCase(TestCase):
    fixtures: ClassVar[list] = ["emailtemplate.json"]

    def setUp(self):
        self.queue_public = Queue.objects.create(
            title="Queue 1",
            slug="q1",
            allow_public_submission=True,
            new_ticket_cc="new.public@example.com",
            updated_ticket_cc="update.public@example.com",
        )

        self.queue_private = Queue.objects.create(
            title="Queue 2",
            slug="q2",
            allow_public_submission=False,
            new_ticket_cc="new.private@example.com",
            updated_ticket_cc="update.private@example.com",
        )

        self.ticket_data = {
            "queue": self.queue_public,
            "title": "Test Ticket",
            "description": "Some Test Ticket",
        }

        self.client = Client()
        helpdesk_settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION = False

    def loginUser(self, is_staff=True):
        """Create a staff user and login"""
        User = get_user_model()
        self.user = User.objects.create(
            username="User_1",
            is_staff=is_staff,
        )
        self.user.set_password("pass")
        self.user.save()
        self.client.login(username="User_1", password="pass")

    def get_public_view_response(self, ticket):
        response = self.client.get(
            reverse("helpdesk:public_view"),
            {
                "ticket": ticket.ticket_for_url,
                "email": ticket.submitter_email,
                "key": ticket.secret_key,
            },
        )
        self.assertTemplateUsed(response, "helpdesk/public_view_ticket.html")
        return response

    def test_ticket_markdown(self):
        ticket_data = {
            "queue": self.queue_public,
            "title": "Test Ticket",
            "description": "*bold*",
        }

        ticket = Ticket.objects.create(**ticket_data)
        self.assertEqual(ticket.get_markdown(), "<p><em>bold</em></p>")

    def test_delete_ticket_staff(self):
        # make staff user
        self.loginUser()

        """Tests whether staff can delete tickets"""
        ticket = Ticket.objects.create(**self.ticket_data)
        ticket_id = ticket.id

        response = self.client.get(
            reverse("helpdesk:delete", kwargs={"ticket_id": ticket_id}), follow=True
        )
        self.assertContains(response, "Are you sure you want to delete this ticket")

        response = self.client.post(
            reverse("helpdesk:delete", kwargs={"ticket_id": ticket_id}), follow=True
        )
        first_redirect = response.redirect_chain[0]
        first_redirect_url = first_redirect[0]

        # Ensure we landed on the "View" page.
        # Django 1.9 compatible way of testing this
        # https://docs.djangoproject.com/en/1.9/releases/1.9/#http-redirects-no-longer-forced-to-absolute-uris
        urlparts = urlparse(first_redirect_url)
        self.assertEqual(urlparts.path, reverse("helpdesk:home"))

        # test ticket deleted
        with self.assertRaises(Ticket.DoesNotExist):
            Ticket.objects.get(pk=ticket_id)

    def test_update_ticket_staff(self):
        """Tests whether staff can update ticket details"""

        # make staff user
        self.loginUser()

        # create second user
        User = get_user_model()
        self.user2 = User.objects.create(
            username="User_2",
            is_staff=True,
        )

        initial_data = {
            "title": "Private ticket test",
            "queue": self.queue_public,
            "assigned_to": self.user,
            "status": Ticket.OPEN_STATUS,
        }

        # create ticket
        ticket = Ticket.objects.create(**initial_data)
        ticket_id = ticket.id

        default_post_data = {
            "title": ticket.title,
            "priority": ticket.priority,
            "queue": ticket.queue_id,
        }
        # assign new owner
        post_data = {
            "owner": self.user2.id,
            **default_post_data,
        }
        response = self.client.post(
            reverse("helpdesk:update", kwargs={"ticket_id": ticket_id}),
            post_data,
            follow=True,
        )
        self.assertContains(
            response,
            changed_field_msg_format.format(
                "Owner", self.user.username, self.user2.username
            ),
        )

        # change status with users email assigned and submitter email assigned,
        # which triggers emails being sent
        ticket.assigned_to = self.user2
        ticket.submitter_email = "submitter@test.com"
        ticket.save()
        self.user2.email = "user2@test.com"
        self.user2.save()
        self.user.email = "user1@test.com"
        self.user.save()
        post_data = {
            "new_status": Ticket.CLOSED_STATUS,
            "public": True,
            **default_post_data,
        }

        # do this also to a newly assigned user (different from logged in one)
        ticket.assigned_to = self.user
        response = self.client.post(
            reverse("helpdesk:update", kwargs={"ticket_id": ticket_id}),
            post_data,
            follow=True,
        )
        self.assertContains(
            response,
            changed_field_msg_format.format(
                "Status",
                status_value_to_title[Ticket.OPEN_STATUS],
                status_value_to_title[Ticket.CLOSED_STATUS],
            ),
        )
        post_data = {
            "new_status": Ticket.OPEN_STATUS,
            "owner": self.user2.id,
            "public": True,
            **default_post_data,
        }
        response = self.client.post(
            reverse("helpdesk:update", kwargs={"ticket_id": ticket_id}),
            post_data,
            follow=True,
        )
        self.assertContains(
            response,
            changed_field_msg_format.format(
                "Status",
                status_value_to_title[Ticket.OPEN_STATUS],
                status_value_to_title[Ticket.CLOSED_STATUS],
            ),
        )

    def test_can_access_ticket(self):
        """Tests whether non-staff but assigned user still counts as owner"""

        # make non-staff user
        self.loginUser(is_staff=False)

        # create second user
        User = get_user_model()
        self.user2 = User.objects.create(
            username="User_2",
            is_staff=False,
        )

        initial_data = {
            "title": "Private ticket test",
            "queue": self.queue_private,
            "assigned_to": self.user,
            "status": Ticket.OPEN_STATUS,
        }

        # create ticket
        helpdesk_settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION = True
        ticket = Ticket.objects.create(**initial_data)
        self.assertEqual(HelpdeskUser(self.user).can_access_ticket(ticket), True)
        self.assertEqual(HelpdeskUser(self.user2).can_access_ticket(ticket), False)

    def test_num_to_link(self):
        """Test that we are correctly expanding links to tickets from IDs"""

        # make staff user
        self.loginUser()

        initial_data = {
            "title": "Some private ticket",
            "queue": self.queue_public,
            "assigned_to": self.user,
            "status": Ticket.OPEN_STATUS,
        }

        # create ticket
        ticket = Ticket.objects.create(**initial_data)
        ticket_id = ticket.id

        # generate the URL text
        result = num_to_link(f"this is ticket#{ticket_id}")
        self.assertEqual(
            result,
            f"this is ticket <a href='/tickets/{ticket_id}/' class='ticket_link_status ticket_link_status_Open'>#{ticket_id}</a>",
        )

        result2 = num_to_link(f"whoa another ticket is here #{ticket_id} huh")
        self.assertEqual(
            result2,
            f"whoa another ticket is here  <a href='/tickets/{ticket_id}/' class='ticket_link_status ticket_link_status_Open'>#{ticket_id}</a> huh",
        )

    def test_create_ticket_getform(self):
        self.loginUser()
        response = self.client.get(reverse("helpdesk:submit"), follow=True)
        self.assertEqual(response.status_code, 200)

        # TODO this needs to be checked further

    def test_merge_tickets(self):
        self.loginUser()

        # Create two tickets
        ticket_1 = Ticket.objects.create(
            queue=self.queue_public,
            title="Ticket 1",
            description="Description from ticket 1",
            submitter_email="user1@mail.com",
            status=Ticket.RESOLVED_STATUS,
            resolution="Awesome resolution for ticket 1",
        )
        ticket_1_follow_up = ticket_1.followup_set.create(title="Ticket 1 creation")
        ticket_1_cc = ticket_1.ticketcc_set.create(user=self.user)
        ticket_1_created = ticket_1.created
        due_date = timezone.now()
        ticket_2 = Ticket.objects.create(
            queue=self.queue_public,
            title="Ticket 2",
            description="Description from ticket 2",
            submitter_email="user2@mail.com",
            due_date=due_date,
            assigned_to=self.user,
        )
        ticket_2_follow_up = ticket_1.followup_set.create(title="Ticket 2 creation")
        ticket_2_cc = ticket_2.ticketcc_set.create(email="random@mail.com")

        # Create custom fields and set values for tickets
        public_cf = CustomField.objects.create(
            name="test",
            label="Test",
            data_type="varchar",
        )
        ticket_1_field_1 = "This is for the test field"
        ticket_1.ticketcustomfieldvalue_set.create(
            field=public_cf, value=ticket_1_field_1
        )
        ticket_2_field_1 = "Another test text"
        ticket_2.ticketcustomfieldvalue_set.create(
            field=public_cf, value=ticket_2_field_1
        )
        staff_only_cf = CustomField.objects.create(
            name="number",
            label="Number",
            data_type="integer",
        )
        ticket_2_field_2 = "444"
        ticket_2.ticketcustomfieldvalue_set.create(
            field=staff_only_cf, value=ticket_2_field_2
        )

        # Check that it correctly redirects to the intermediate page
        response = self.client.post(
            reverse("helpdesk:mass_update"),
            data={"ticket_id": [str(ticket_1.id), str(ticket_2.id)], "action": "merge"},
            follow=True,
        )
        redirect_url = "{}?tickets={}&tickets={}".format(
            reverse("helpdesk:merge_tickets"),
            ticket_1.id,
            ticket_2.id,
        )
        self.assertRedirects(response, redirect_url)
        self.assertContains(response, ticket_1.description)
        self.assertContains(response, ticket_1.resolution)
        self.assertContains(response, ticket_1.submitter_email)
        self.assertContains(response, ticket_1_field_1)
        self.assertContains(response, ticket_2.description)
        self.assertContains(response, ticket_2.submitter_email)
        self.assertContains(response, ticket_2_field_1)
        self.assertContains(response, ticket_2_field_2)

        # Check that the merge is correctly done
        response = self.client.post(
            redirect_url,
            data={
                "chosen_ticket": str(ticket_1.id),
                "due_date": str(ticket_2.id),
                "status": str(ticket_1.id),
                "submitter_email": str(ticket_2.id),
                "description": str(ticket_2.id),
                "assigned_to": str(ticket_2.id),
                public_cf.name: str(ticket_1.id),
                staff_only_cf.name: str(ticket_2.id),
            },
            follow=True,
        )
        self.assertRedirects(response, ticket_1.get_absolute_url())
        ticket_2.refresh_from_db()
        self.assertEqual(ticket_2.merged_to, ticket_1)
        self.assertEqual(ticket_2.followup_set.count(), 0)
        self.assertEqual(ticket_2.ticketcc_set.count(), 0)
        ticket_1.refresh_from_db()
        self.assertEqual(ticket_1.created, ticket_1_created)
        self.assertEqual(ticket_1.due_date, due_date)
        self.assertEqual(ticket_1.status, Ticket.RESOLVED_STATUS)
        self.assertEqual(ticket_1.submitter_email, ticket_2.submitter_email)
        self.assertEqual(ticket_1.description, ticket_2.description)
        self.assertEqual(ticket_1.assigned_to, ticket_2.assigned_to)
        self.assertEqual(
            ticket_1.ticketcustomfieldvalue_set.get(field=public_cf).value,
            ticket_1_field_1,
        )
        self.assertEqual(
            ticket_1.ticketcustomfieldvalue_set.get(field=staff_only_cf).value,
            ticket_2_field_2,
        )
        self.assertEqual(
            list(ticket_1.followup_set.all()), [ticket_1_follow_up, ticket_2_follow_up]
        )
        self.assertEqual(list(ticket_1.ticketcc_set.all()), [ticket_1_cc, ticket_2_cc])

    def test_update_ticket_queue(self):
        """Tests whether user can change the queue in the Respond to this ticket section."""

        # log user in
        self.loginUser()

        # create ticket
        initial_data = {
            "title": "Queue change ticket test",
            "queue": self.queue_public,
            "assigned_to": self.user,
            "status": Ticket.OPEN_STATUS,
        }
        ticket = Ticket.objects.create(**initial_data)
        ticket_id = ticket.id

        # initial queue
        self.assertEqual(ticket.queue, self.queue_public)

        # POST first follow-up with new queue
        new_queue = Queue.objects.create(
            title="New Queue",
            slug="newqueue",
        )
        comment_string = "first follow-up in new queue"
        post_data = {
            "title": ticket.title,
            "priority": ticket.priority,
            "comment": comment_string,
            "queue": str(new_queue.id),
        }
        self.client.post(
            reverse("helpdesk:update", kwargs={"ticket_id": ticket_id}), post_data
        )

        # queue was correctly modified
        ticket.refresh_from_db()
        self.assertEqual(ticket.queue, new_queue)

        # ticket change was saved
        latest_fup = ticket.followup_set.latest("date")
        latest_ticketchange = latest_fup.ticketchange_set.latest("id")
        self.assertEqual(latest_ticketchange.field, _("Queue"))
        self.assertEqual(int(latest_ticketchange.old_value), self.queue_public.id)
        self.assertEqual(int(latest_ticketchange.new_value), new_queue.id)
        self.assertEqual(latest_fup.comment, comment_string)

    def test_update_ticket_with_custom_fields(self):
        """Tests that tickets that contain custom fields will correctly update core and custom fields."""

        # log user in
        self.loginUser()

        # create ticket
        initial_data = {
            "title": "Queue change ticket test",
            "queue": self.queue_public,
            "assigned_to": self.user,
            "status": Ticket.OPEN_STATUS,
        }
        ticket = Ticket.objects.create(**initial_data)
        ticket_id = ticket.id
        # Create custom fields and set values for tickets
        public_cf = CustomField.objects.create(
            name="my_custom_field",
            label="My Custom Field",
            data_type="varchar",
            required=True,
        )
        public_cf_value = "This is my custom field value"

        comment_string = "FollowUp.comment field string"
        post_data = {
            "title": ticket.title,
            "priority": ticket.priority,
            "comment": comment_string,
            "queue": str(self.queue_public.id),
            "custom_" + public_cf.name: public_cf_value,
        }
        self.client.post(
            reverse("helpdesk:update", kwargs={"ticket_id": ticket_id}), post_data
        )

        # queue was correctly modified
        ticket.refresh_from_db()
        self.assertEqual(ticket.queue_id, self.queue_public.id)

        # ticket change was saved
        latest_fup = ticket.followup_set.latest("date")
        self.assertEqual(latest_fup.comment, comment_string)
        self.assertEqual(
            ticket.ticketcustomfieldvalue_set.get(field=public_cf).value,
            public_cf_value,
        )

    def test_update_ticket_with_custom_fields_changes_displayed_in_ui(self):
        """
        Tests updating ticket details by staff and verifying that:
        1. staff_only custom field changes are not visible in the public UI
        2. The text displayed for the custom field name is the custom fields label
        3. The "built-in" field changes show the fields template title
        """

        submitter_email = "submitter@example.com"
        public_cf = CustomField.objects.create(
            name="public_cf",
            label="Custom Field 1",
            data_type="varchar",
        )
        staff_only_cf = CustomField.objects.create(
            name="staff_only_cf",
            label="Custom Field 2",
            data_type="varchar",
            staff_only=True,
        )
        public_cf_field_values = {
            "initial": "Initial custom field 1 value",
            "next": "Next cf1 value",
        }
        staff_only_cf_field_values = {
            "initial": "Initial custom field 2 value",
            "next": "Next cf2 value",
        }

        self.loginUser()

        initial_ticket_data = {
            "title": "Test Ticket",
            "queue": self.queue_public,
            "assigned_to": self.user,
            "status": Ticket.OPEN_STATUS,
            "submitter_email": submitter_email,
        }

        # create ticket
        ticket = Ticket.objects.create(**initial_ticket_data)
        ticket_id = ticket.id
        ticket.ticketcustomfieldvalue_set.create(
            field=public_cf, value=public_cf_field_values["initial"]
        )
        ticket.ticketcustomfieldvalue_set.create(
            field=staff_only_cf, value=staff_only_cf_field_values["initial"]
        )

        default_post_data = {
            "title": ticket.title,
            "priority": ticket.priority,
            "queue": ticket.queue_id,
        }
        # assign new owner
        post_data = {
            "new_status": Ticket.CLOSED_STATUS,
            "public": True,
            **default_post_data,
        }
        post_data[f"custom_{public_cf.name}"] = public_cf_field_values["next"]
        post_data[f"custom_{staff_only_cf.name}"] = staff_only_cf_field_values["next"]
        response = self.client.post(
            reverse("helpdesk:update", kwargs={"ticket_id": ticket_id}),
            post_data,
            follow=True,
        )
        self.assertContains(
            response,
            changed_field_msg_format.format(
                "Status",
                status_value_to_title[Ticket.OPEN_STATUS],
                status_value_to_title[Ticket.CLOSED_STATUS],
            ),
        )
        self.assertContains(
            response,
            changed_field_msg_format.format(
                public_cf.label,
                public_cf_field_values["initial"],
                public_cf_field_values["next"],
            ),
        )
        self.assertContains(
            response,
            changed_field_msg_format.format(
                staff_only_cf.label,
                staff_only_cf_field_values["initial"],
                staff_only_cf_field_values["next"],
            ),
        )

        # Check public response excludes staff_only custom fields
        response = self.get_public_view_response(ticket)
        self.assertContains(
            response,
            changed_field_msg_format.format(
                "Status",
                status_value_to_title[Ticket.OPEN_STATUS],
                status_value_to_title[Ticket.CLOSED_STATUS],
            ),
        )
        self.assertContains(
            response,
            changed_field_msg_format.format(
                public_cf.label,
                public_cf_field_values["initial"],
                public_cf_field_values["next"],
            ),
        )
        self.assertNotContains(
            response,
            changed_field_msg_format.format(
                staff_only_cf.label,
                staff_only_cf_field_values["initial"],
                staff_only_cf_field_values["next"],
            ),
        )
