from http import HTTPStatus

from django.conf import settings
from django.shortcuts import resolve_url
from django.test import TestCase
from django.urls import resolve, reverse

from helpdesk.models import KBCategory, KBItem
from tests.helpers import get_staff_user


class KBVoteViewTests(TestCase):
    """
    Test suite for the kb vote view where a user upvotes/downvotes
    a knowledge base answer.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = get_staff_user()
        cls.kb_category = KBCategory.objects.create(
            title="Customer Accounts",
            slug="customer-accounts",
            description="Account access related problems",
        )
        cls.kbitem = KBItem.objects.create(
            category=cls.kb_category,
            title="Password",
            question="How to reset a password?",
            answer="Go to settings then click reset password.",
        )

        cls.upvote_url = reverse(
            "helpdesk:kb_vote", kwargs={"item_id": cls.kbitem.id, "vote": "up"}
        )
        cls.downvote_url = reverse(
            "helpdesk:kb_vote", kwargs={"item_id": cls.kbitem.id, "vote": "down"}
        )

    def test_url_resolves_correct_view(self):
        match = resolve(self.upvote_url)
        self.assertEqual(match.url_name, "kb_vote")
        self.assertEqual(match.kwargs["vote"], "up")

        match = resolve(self.downvote_url)
        self.assertEqual(match.url_name, "kb_vote")
        self.assertEqual(match.kwargs["vote"], "down")

    def test_only_accepts_post(self):
        # Act: Try get
        r = self.client.get(self.upvote_url)
        self.assertEqual(r.status_code, HTTPStatus.METHOD_NOT_ALLOWED)

    def test_anonymous_user_cannot_cast_a_vote(self):
        # Arrange
        redirect_url = f"{resolve_url(settings.LOGIN_URL)}?next={self.upvote_url}"

        # Act: cast a vote w/o logging in
        r = self.client.post(self.upvote_url)

        # Assert
        self.assertEqual(r.status_code, HTTPStatus.FOUND)
        self.assertRedirects(r, redirect_url)

    def test_never_upvoted_now_wants_to_upvote(self):
        # Arrange: staff user logs in
        self.client.force_login(self.user)
        # Make sure no votes are registered
        self.assertEqual(self.kbitem.recommendations, 0)
        self.assertEqual(self.kbitem.votes, 0)
        self.assertFalse(self.kbitem.voted_by.contains(self.user))

        # Act: staff user casts an upvote
        r = self.client.post(self.upvote_url, follow=True)
        self.kbitem.refresh_from_db()

        # Assert
        # User is redirected
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertRedirects(r, self.kbitem.get_absolute_url())
        self.assertContains(r, "1 of 1 people found this answer useful")

        # Upvote successfully registered
        self.assertEqual(self.kbitem.recommendations, 1)
        self.assertEqual(self.kbitem.votes, 1)
        self.assertTrue(self.kbitem.voted_by.contains(self.user))
        self.assertFalse(self.kbitem.downvoted_by.contains(self.user))

    def test_never_downvoted_now_wants_to_downvote(self):
        # Arrange: staff user logs in
        self.client.force_login(self.user)
        # Make sure no votes are registered
        self.assertEqual(self.kbitem.recommendations, 0)
        self.assertEqual(self.kbitem.votes, 0)
        self.assertFalse(self.kbitem.downvoted_by.contains(self.user))

        # Act: staff user casts an downvote
        r = self.client.post(self.downvote_url, follow=True)
        self.kbitem.refresh_from_db()

        # Assert
        # User is redirected
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertRedirects(r, self.kbitem.get_absolute_url())
        self.assertContains(r, "0 of 1 people found this answer useful")

        # Downvote successfully registered
        self.assertEqual(self.kbitem.recommendations, 0)
        self.assertEqual(self.kbitem.votes, 1)  # vote still registered

        self.assertTrue(self.kbitem.downvoted_by.contains(self.user))
        self.assertFalse(self.kbitem.voted_by.contains(self.user))

    def test_upvoted_earlier_now_wants_to_downvote(self):
        # Arrange: Simulate an upvote
        obj = self.kbitem
        obj.recommendations += 1
        obj.votes += 1
        obj.voted_by.add(self.user)
        obj.save()

        self.client.force_login(self.user)

        # Act: Users casts a downvote
        r = self.client.post(self.downvote_url, follow=True)
        self.kbitem.refresh_from_db()

        # Assert
        # User is redirected
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertRedirects(r, self.kbitem.get_absolute_url())

        # Downvote successfully registered
        self.assertEqual(self.kbitem.recommendations, 0)
        self.assertEqual(self.kbitem.votes, 1)

        self.assertTrue(self.kbitem.downvoted_by.contains(self.user))
        self.assertFalse(self.kbitem.voted_by.contains(self.user))

    def test_downvoted_earlier_now_wants_to_upvote(self):
        # Arrange: Simulate an downvote
        obj = self.kbitem
        obj.recommendations -= 1
        obj.votes += 1
        obj.downvoted_by.add(self.user)
        obj.save()

        self.client.force_login(self.user)

        # Act: Users casts an upvote
        r = self.client.post(self.upvote_url, follow=True)
        self.kbitem.refresh_from_db()

        # Assert
        # User is redirected
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertRedirects(r, self.kbitem.get_absolute_url())

        # Upvote successfully registered
        self.assertEqual(self.kbitem.recommendations, 0)
        self.assertEqual(self.kbitem.votes, 1)

        self.assertFalse(self.kbitem.downvoted_by.contains(self.user))
        self.assertTrue(self.kbitem.voted_by.contains(self.user))
