from http import HTTPStatus

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import resolve, reverse

from helpdesk.forms import EmailIgnoreForm
from helpdesk.models import IgnoreEmail
from helpdesk.views.staff import email_ignore, email_ignore_add, email_ignore_del

CustomUser = get_user_model()


class EmailIgnoreListTests(TestCase):
    """
    Test suite for the page that shows a table of emails that
    are added to ignore.
    """

    @classmethod
    def setUpTestData(cls):
        cls.template = "helpdesk/email_ignore_list.html"
        cls.url = reverse("helpdesk:email_ignore")
        cls.alice = CustomUser.objects.create(
            username="alice", password="testpass123", is_superuser=True
        )
        # We create two email addresses to ignore
        IgnoreEmail.objects.create(name="Charlie", email_address="charlie@example.com")

        IgnoreEmail.objects.create(name="Dimple", email_address="dimple@example.com")

    def test_url_resolves_correct_view(self):
        match = resolve(self.url)
        self.assertEqual(match.url_name, "email_ignore")
        self.assertEqual(match.route, "ignore/")
        self.assertEqual(match.func, email_ignore)

    def test_normal_users_cannot_access(self):
        # Arrange: Bob is just a normal user of the system
        bob = CustomUser.objects.create(username="bob", password="testpass123")
        self.client.force_login(bob)

        # Act: Bob tries to access the ignore list page
        r = self.client.get(self.url)

        # Assert: bob should get permission denied error
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
        self.assertTemplateNotUsed(r, self.template)

    def test_super_user_can_access(self):
        # Arrange: Alice our super user logs in
        self.client.force_login(self.alice)

        # Act: Alice tries to access email ignore list page
        r = self.client.get(self.url)

        # Assert: She should have access
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(r, self.template)
        self.assertContains(r, "Ignored E-Mail Addresses")
        self.assertNotContains(r, "Hi I should not be here")

        # check two ignore emails are present
        self.assertEqual(len(r.context["ignore_list"]), 2)
        self.assertContains(r, "charlie@example.com")
        self.assertContains(r, "dimple@example.com")


class EmailIgnoreAddTests(TestCase):
    """
    Test suite to check adding of email addresses to ignore list.
    """

    @classmethod
    def setUpTestData(cls):
        cls.template = "helpdesk/email_ignore_add.html"
        cls.url = reverse("helpdesk:email_ignore_add")
        cls.alice = CustomUser.objects.create(
            username="alice", password="testpass123", is_superuser=True
        )

    def test_url_resolves_correct_view(self):
        match = resolve(self.url)
        self.assertEqual(match.func, email_ignore_add)
        self.assertEqual(match.route, "ignore/add/")
        self.assertEqual(match.url_name, "email_ignore_add")

    def test_normal_users_cannot_access(self):
        # Arrange: Bob is just a normal user of the system
        bob = CustomUser.objects.create(username="bob", password="testpass123")
        self.client.force_login(bob)

        # Act: Bob tries to access the ignore list page
        r = self.client.get(self.url)

        # Assert: bob should get permission denied error
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
        self.assertTemplateNotUsed(r, self.template)

    def test_privileged_user_can_access(self):
        # Arrange: Alice our super user logs in
        self.client.force_login(self.alice)

        # Act: Alice tries to access email ignore list page
        r = self.client.get(self.url)

        # Assert: She should have access
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(r, self.template)
        self.assertContains(r, "Ignore E-Mail Address")
        self.assertNotContains(r, "Hi I should not be here")

        self.assertIsInstance(r.context["form"], EmailIgnoreForm)

    def test_email_ignore_creation_via_post_works(self):
        # Arrange: Alice our super user logs in
        self.client.force_login(self.alice)
        data = {"name": "Ethan", "email_address": "ethan@example.com"}

        # Act: She submits the form via post
        r = self.client.post(self.url, data=data, follow=True)

        # Assert: she should be redirected to ignore list page
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertRedirects(r, reverse("helpdesk:email_ignore"))

        # alice should see a success message as well
        messages = list(r.context["messages"])

        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "Email added to ignore list successfully.")


class EmailIgnoreDeleteTests(TestCase):
    """
    Test suite to verify removal of an email from the ignore list works.
    """

    @classmethod
    def setUpTestData(cls):
        cls.email_to_ignore = IgnoreEmail.objects.create(
            name="Federico", email_address="fede@example.com"
        )
        cls.template = "helpdesk/email_ignore_del.html"
        cls.url = reverse("helpdesk:email_ignore_del", args=[cls.email_to_ignore.id])
        cls.alice = CustomUser.objects.create(
            username="alice", password="testpass123", is_superuser=True
        )

    def test_url_resolves_correct_view(self):
        match = resolve(self.url)
        self.assertEqual(match.func, email_ignore_del)
        self.assertEqual(match.url_name, "email_ignore_del")

    def test_normal_users_cannot_access(self):
        # Arrange: Bob is just a normal user of the system
        bob = CustomUser.objects.create(username="bob", password="testpass123")
        self.client.force_login(bob)

        # Act: Bob tries to access the ignore list page
        r = self.client.get(self.url)

        # Assert: bob should get permission denied error
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
        self.assertTemplateNotUsed(r, self.template)

    def test_privileged_user_can_access(self):
        # Arrange: Alice our super user logs in
        self.client.force_login(self.alice)

        # Act: Alice tries to access email ignore delete page
        r = self.client.get(self.url)

        # Assert: She should be able to see the confirmation page
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(r, self.template)
        self.assertContains(r, "Delete Ignored E-Mail Address")
        self.assertNotContains(r, "Hi I should not be here")

    def test_deletion_of_ignored_email_works_via_post(self):
        # Arrange: Alice our super user logs in
        self.client.force_login(self.alice)

        # Act: She confirms the deletion by clicks on the delete button
        r = self.client.post(self.url, follow=True)
        # Assert: She should be redirected to ignore list page
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertRedirects(r, reverse("helpdesk:email_ignore"))

        # Alice should see a success message of deletion as well
        messages = list(r.context["messages"])

        self.assertEqual(len(messages), 1)
        self.assertEqual(
            str(messages[0]), "Email removed from ignore list successfully."
        )
