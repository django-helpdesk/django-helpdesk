from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase

from helpdesk import settings as helpdesk_settings
from helpdesk.models import FollowUp, Queue, Ticket
from helpdesk.update_ticket import create_ticket_backlinks, update_ticket

User = get_user_model()


class BacklinkCreationTests(TestCase):
    """
    These tests cover the base requirements for the backlink feature

    We are not worrying about cross Queue permissions here

    Github issue with request:
    https://github.com/django-helpdesk/django-helpdesk/issues/1424
    """

    def setUp(self):
        self.queue = Queue.objects.create(title="Test Queue", slug="test")
        self.ticket_a = Ticket.objects.create(
            title="Ticket A", queue=self.queue, status=Ticket.OPEN_STATUS
        )
        self.ticket_b = Ticket.objects.create(
            title="Ticket B", queue=self.queue, status=Ticket.OPEN_STATUS
        )
        self.staff_user = User.objects.create_user(
            username="staff", password="pass", is_staff=True
        )

    def _followup(self, ticket, comment):
        return FollowUp.objects.create(
            ticket=ticket,
            title="Comment",
            comment=comment,
            public=True,
            user=self.staff_user,
        )

    def _backlinks(self, ticket):
        return FollowUp.objects.filter(ticket=ticket, title__contains="Referenced in")

    def test_backlink_created_on_referenced_ticket(self):
        f = self._followup(self.ticket_a, f"See other ticket #{self.ticket_b.id}")
        create_ticket_backlinks(self.ticket_a, f, user=self.staff_user)

        backlinks = self._backlinks(self.ticket_b)
        self.assertEqual(backlinks.count(), 1)
        backlink = backlinks.first()
        self.assertIn(f"#{self.ticket_a.id}", backlink.title)
        self.assertFalse(backlink.public)
        self.assertFalse(backlink.comment)

    def test_no_self_reference_backlink(self):
        """
        If user references ticket A in ticket A do not make a backlink
        """
        f = self._followup(self.ticket_a, f"Updating #{self.ticket_a.id}")
        create_ticket_backlinks(self.ticket_a, f, user=self.staff_user)

        self.assertEqual(self._backlinks(self.ticket_a).count(), 0)

    def test_no_backlink_for_nonexistent_ticket(self):
        f = self._followup(self.ticket_a, "#99999")
        create_ticket_backlinks(self.ticket_a, f, user=self.staff_user)

        self.assertFalse(self._backlinks(self.ticket_a).exists())
        self.assertFalse(self._backlinks(self.ticket_b).exists())

    def test_duplicate_reference_creates_one_backlink(self):
        """
        Ticket A mentions Ticket B twice
        """
        f = self._followup(
            self.ticket_a,
            f"#{self.ticket_b.id} and again #{self.ticket_b.id}",
        )
        create_ticket_backlinks(self.ticket_a, f, user=self.staff_user)

        self.assertEqual(self._backlinks(self.ticket_b).count(), 1)

    def test_update_ticket_creates_backlinks(self):
        update_ticket(
            user=self.staff_user,
            ticket=self.ticket_a,
            comment=f"Related to #{self.ticket_b.id}",
            public=True,
        )

        self.assertEqual(self._backlinks(self.ticket_b).count(), 1)


class BacklinkPermissionTests(TestCase):
    """
    These tests cover the cross queue backlink feature/capability

    Github issue with request (really read @Benbb96's comment):
    https://github.com/django-helpdesk/django-helpdesk/issues/1424
    """

    def test_no_backlink_without_queue_access(self):
        """
        Don't let a user that can see ticket B but not ticket A write to
        followups in ticket A by referencing ticket B

        (tickets are in different queues)
        """
        original = helpdesk_settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION
        helpdesk_settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION = True
        self.addCleanup(
            setattr,
            helpdesk_settings,
            "HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION",
            original,
        )

        queue_a = Queue.objects.create(title="Queue A", slug="qa")
        queue_b = Queue.objects.create(title="Queue B", slug="qb")

        ticket_a = Ticket.objects.create(
            title="In Queue A", queue=queue_a, status=Ticket.OPEN_STATUS
        )
        ticket_b = Ticket.objects.create(
            title="In Queue B", queue=queue_b, status=Ticket.OPEN_STATUS
        )

        limited_user = User.objects.create_user(
            username="limited", password="pass", is_staff=True
        )
        perm_b = Permission.objects.get(codename=f"queue_access_{queue_b.slug}")
        limited_user.user_permissions.add(perm_b)
        limited_user = User.objects.get(pk=limited_user.pk)

        f = FollowUp.objects.create(
            ticket=ticket_b,
            title="Comment",
            comment=f"See #{ticket_a.id}",
            public=True,
            user=limited_user,
        )
        create_ticket_backlinks(ticket_b, f, user=limited_user)

        self.assertFalse(
            FollowUp.objects.filter(
                ticket=ticket_a, title__contains="Referenced in"
            ).exists()
        )

    def test_no_user_creates_no_backlink(self):
        """
        Emails can not auth so do not let them make back links
        """
        queue = Queue.objects.create(title="Public Queue", slug="pub")
        ticket_a = Ticket.objects.create(
            title="Ticket A", queue=queue, status=Ticket.OPEN_STATUS
        )
        ticket_b = Ticket.objects.create(
            title="Ticket B", queue=queue, status=Ticket.OPEN_STATUS
        )

        f = FollowUp.objects.create(
            ticket=ticket_a,
            title="Comment",
            comment=f"See #{ticket_b.id}",
            public=True,
        )
        create_ticket_backlinks(ticket_a, f)

        self.assertFalse(
            FollowUp.objects.filter(
                ticket=ticket_b, title__contains="Referenced in"
            ).exists()
        )
