"""
Every staff route that resolves an object from a caller-supplied id must deny a
foreign queue.

Four advisories in five weeks came from the same shape: authorization is opt-in
per view, `ticket_perm_check()` is called by most of them and forgotten by one,
and nothing makes forgetting it fail. Each report found the next view that had
been missed.

So rather than another list of hand-written cases, this walks the URL conf and
requires every route to be classified: either it is exercised here against a
foreign queue, or it is named in NO_TICKET_DATA with a reason. A route in
neither fails, so a new route cannot be added without deciding its boundary.

An earlier version keyed on routes taking a `ticket_id`, which is why the RSS
feeds escaped it: they address tickets by assignee, by queue slug, or by nothing
at all. Classifying every route is what makes the guarantee match its claim.

The assertion is deliberately about content rather than status code. Denial is
expressed as 403 by some views, 404 by others and a redirect with a message by
`view_ticket`, and pinning a number per route would make this brittle without
making it stricter. What must never happen is foreign-queue content reaching the
response body.
"""

import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from helpdesk import settings
from helpdesk.models import (
    Checklist,
    FollowUp,
    FollowUpAttachment,
    Queue,
    Ticket,
    TicketCC,
    TicketDependency,
)
from helpdesk.query import query_to_base64
from helpdesk.user import HelpdeskUser

# Appears in the foreign ticket and in every object hanging off it. If any
# response body contains it, something served across the boundary.
MARKER = "SWEEPMARKER_FOREIGN_QUEUE_CONTENT"

# Routes that cannot serve ticket data, with the reason each one is exempt.
# Every route in the URL conf must be either exercised by this sweep or listed
# here; one in neither fails test_every_route_is_classified, so a new route
# cannot be added without someone deciding which it is.
NO_TICKET_DATA = {
    "savequery": "stores a search definition, returns no ticket",
    "delete_query": "acts on a SavedSearch owned by the caller",
    "user_settings": "the caller's own UserSettings",
    "email_ignore": "IgnoreEmail rows, not tickets",
    "email_ignore_add": "IgnoreEmail rows, not tickets",
    "email_ignore_del": "IgnoreEmail rows, not tickets",
    "checklist_templates": "ChecklistTemplate rows, not attached to a ticket",
    "edit_checklist_template": "ChecklistTemplate rows, not attached to a ticket",
    "delete_checklist_template": "ChecklistTemplate rows, not attached to a ticket",
    "raw": "serves PreSetReply bodies only; preset scoping is its own question",
    "home": "public portal landing page",
    "submit": "public submission form",
    "submit_iframe": "public submission form",
    "success_iframe": "public submission confirmation",
    "public_view": "public portal, gated by submitter email or secret key "
    "rather than by queue permissions",
    "public_change_language": "sets a language cookie",
    "kb_index": "knowledge base",
    "kb_category": "knowledge base",
    "kb_category_iframe": "knowledge base",
    "kb_vote": "knowledge base",
    "login": "authentication",
    "logout": "authentication",
    "password_change": "authentication",
    "password_change_done": "authentication",
    "password_reset": "authentication",
    "password_reset_done": "authentication",
    "password_reset_confirm": "authentication",
    "password_reset_complete": "authentication",
    "help_context": "static help page",
    "system_settings": "renders configured settings, no ticket data",
}


class ForeignQueueSweepTestCase(TestCase):
    def setUp(self):
        original = settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION
        settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION = True
        self.addCleanup(
            setattr,
            settings,
            "HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION",
            original,
        )
        User = get_user_model()

        # Neither queue accepts public submissions, so this measures the queue
        # permission boundary and not the separate widening that
        # allow_public_submission causes in get_queues().
        self.mine = Queue.objects.create(title="Mine", slug="mine")
        self.theirs = Queue.objects.create(title="Theirs", slug="theirs")

        self.staff = User.objects.create(
            username="restricted", is_staff=True, email="r@example.com"
        )
        self.staff.set_password("pass")
        self.staff.save()
        self.staff.user_permissions.add(
            Permission.objects.get(codename=self.mine.permission_name[9:])
        )

        # Owns the foreign ticket, so the feeds keyed on an assignee rather than
        # on a ticket id have something to serve across the boundary.
        self.victim = User.objects.create(
            username="victim", is_staff=True, email="v@example.com"
        )

        self.my_ticket = Ticket.objects.create(title="Mine", queue=self.mine)
        self.foreign = Ticket.objects.create(
            title=MARKER,
            queue=self.theirs,
            description=MARKER,
            assigned_to=self.victim,
        )
        # Unassigned, so the unassigned-tickets feed has something to serve too.
        # The ticket above is assigned to the victim and would never appear in it.
        self.foreign_unassigned = Ticket.objects.create(
            title=MARKER, queue=self.theirs, description=MARKER
        )

        self.foreign_followup = FollowUp.objects.create(
            ticket=self.foreign, title=MARKER, comment=MARKER, public=False
        )
        self.foreign_attachment = FollowUpAttachment.objects.create(
            followup=self.foreign_followup,
            file=SimpleUploadedFile(
                f"{MARKER}.txt", MARKER.encode(), content_type="text/plain"
            ),
            filename=f"{MARKER}.txt",
        )
        self.foreign_cc = TicketCC.objects.create(
            ticket=self.foreign, email="cc@example.com"
        )
        self.foreign_checklist = Checklist.objects.create(
            ticket=self.foreign, name=MARKER
        )
        self.foreign_dependency = TicketDependency.objects.create(
            ticket=self.foreign, depends_on=self.my_ticket
        )
        self.client.login(username="restricted", password="pass")

    def foreign_kwargs(self, names):
        """Values naming objects that all belong to the foreign queue.

        A route whose parameters are not listed here fails rather than being
        skipped: an unrecognised parameter means a new route shape that nobody
        has decided the boundary for, which is exactly what this is here to
        catch.
        """
        known = {
            "ticket_id": self.foreign.id,
            "followup_id": self.foreign_followup.id,
            "attachment_id": self.foreign_attachment.id,
            "cc_id": self.foreign_cc.id,
            "dependency_id": self.foreign_dependency.id,
            "checklist_id": self.foreign_checklist.id,
        }
        unknown = set(names) - set(known)
        if unknown:
            self.fail(
                f"Route parameters {sorted(unknown)} are not covered by this "
                "sweep. Add a foreign-queue value for them so the new route is "
                "actually exercised."
            )
        return {name: known[name] for name in names}

    def all_routes(self):
        """Every helpdesk route, read from the URL conf as (name, params).

        Reads helpdesk.urls directly rather than the resolver's reverse_dict,
        which does not expose namespaced routes from the root resolver.
        """
        from helpdesk import urls as helpdesk_urls

        found = []
        for entry in helpdesk_urls.urlpatterns:
            name = getattr(entry, "name", None)
            pattern = getattr(entry, "pattern", None)
            if not name or pattern is None:
                continue  # an include(), not a route
            found.append((name, tuple(pattern.regex.groupindex)))
        return sorted(set(found))

    def ticket_routes(self):
        """The subset taking a ticket_id, for the two id-pairing sweeps."""
        return [
            (f"helpdesk:{name}", params)
            for name, params in self.all_routes()
            if "ticket_id" in params
        ]

    def other_routes(self):
        """Routes that serve ticket data without taking a ticket_id.

        This is the family the earlier version of this sweep missed: they
        address tickets by assignee, by queue slug, by an encoded query, or by
        nothing at all, so keying on `ticket_id` never reached them.
        """
        return [
            (name, params)
            for name, params in self.all_routes()
            if "ticket_id" not in params and name not in NO_TICKET_DATA
        ]

    def other_kwargs(self, name, params):
        """Parameters for a non-ticket_id route, chosen so that an unscoped view
        would serve the foreign ticket."""
        known = {
            "user_name": self.victim.username,
            "queue_slug": self.theirs.slug,
            "report": "queuestatus",
            "query": query_to_base64(
                {"filtering": {}, "sorting": "created", "search_string": ""}
            ),
        }
        unknown = set(params) - set(known)
        if unknown:
            self.fail(
                f"Route {name} takes {sorted(unknown)}, which this sweep cannot "
                "build. Add a value that would expose the foreign queue, or "
                "list the route in NO_TICKET_DATA with a reason."
            )
        return {p: known[p] for p in params}

    def test_every_route_is_classified(self):
        """The guarantee this file actually makes.

        A route is either exercised against a foreign queue below or named in
        NO_TICKET_DATA. One in neither means nobody decided whether it can serve
        a ticket, which is how the RSS feeds went unnoticed through three
        advisories: the sweep keyed on `ticket_id` and they take none.
        """
        exercised = {
            name for name, _ in self.all_routes() if name not in NO_TICKET_DATA
        }
        self.assertGreater(len(exercised), 20)
        for name, params in self.all_routes():
            with self.subTest(route=name):
                self.assertTrue(
                    name in NO_TICKET_DATA or name in exercised,
                    f"Route {name} is classified neither way.",
                )

    def test_no_route_without_a_ticket_id_serves_foreign_content(self):
        """Dashboards, listings, reports and feeds reach tickets without an id
        in the URL, so no id has to be manipulated to test them."""
        routes = self.other_routes()
        self.assertGreater(len(routes), 10, routes)
        for name, params in routes:
            with self.subTest(route=name):
                url = reverse(
                    f"helpdesk:{name}", kwargs=self.other_kwargs(name, params)
                )
                response = self.client.get(url, follow=True)
                self.assertNotIn(
                    MARKER,
                    response.content.decode(errors="replace"),
                    f"{name} served content from a queue the user cannot access",
                )

    def test_the_sweep_actually_found_the_routes(self):
        """Guards against the walk silently matching nothing, which would make
        every assertion below vacuous."""
        names = [name for name, _ in self.ticket_routes()]
        self.assertGreater(len(names), 8, names)
        for expected in ("helpdesk:view", "helpdesk:edit", "helpdesk:update"):
            self.assertIn(expected, names)

    def test_no_route_serves_foreign_queue_content(self):
        for name, params in self.ticket_routes():
            with self.subTest(route=name):
                url = reverse(name, kwargs=self.foreign_kwargs(params))
                response = self.client.get(url, follow=True)
                body = response.content.decode(errors="replace")
                self.assertNotIn(
                    MARKER,
                    body,
                    f"{name} served content from a queue the user cannot access",
                )

    def test_no_route_mutates_a_foreign_ticket(self):
        """A POST with no useful payload should be rejected on authorization,
        before validation has anything to say about the body."""
        before = {
            "title": self.foreign.title,
            "queue": self.foreign.queue_id,
            "status": self.foreign.status,
            "on_hold": self.foreign.on_hold,
        }
        for name, params in self.ticket_routes():
            with self.subTest(route=name):
                url = reverse(name, kwargs=self.foreign_kwargs(params))
                self.client.post(url, {}, follow=True)
                self.foreign.refresh_from_db()
                self.assertEqual(
                    {
                        "title": self.foreign.title,
                        "queue": self.foreign.queue_id,
                        "status": self.foreign.status,
                        "on_hold": self.foreign.on_hold,
                    },
                    before,
                    f"{name} modified a ticket in a queue the user cannot access",
                )

    def test_no_route_accepts_a_foreign_child_under_a_permitted_ticket(self):
        """The mismatched-key shape, which the sweep above cannot see.

        Pairing a foreign parent with foreign children only proves that a
        missing check is caught. A route that authorizes the ticket in the URL
        and then resolves a follow-up, attachment or checklist id independently
        needs the opposite pairing: a ticket the caller may reach, and a child
        belonging to someone else's queue. That is CWE-639, and it is how the
        second half of GHSA-jh3j-fh4x-98pj worked.
        """
        mine = {"ticket_id": self.my_ticket.id}
        for name, params in self.ticket_routes():
            children = [p for p in params if p != "ticket_id"]
            if not children:
                continue
            with self.subTest(route=name):
                kwargs = dict(mine, **self.foreign_kwargs(children))
                url = reverse(name, kwargs=kwargs)
                body = self.client.get(url, follow=True).content.decode(
                    errors="replace"
                )
                self.assertNotIn(
                    MARKER,
                    body,
                    f"{name} served a child object from a foreign queue when "
                    "paired with a ticket the user may access",
                )
                self.client.post(url, {}, follow=True)
                self.foreign_followup.refresh_from_db()
                self.assertEqual(
                    self.foreign_followup.ticket_id,
                    self.foreign.id,
                    f"{name} moved a foreign follow-up",
                )

    def test_permitted_queue_still_works(self):
        """The sweep must not be passing because everything is broken."""
        response = self.client.get(
            reverse("helpdesk:view", kwargs={"ticket_id": self.my_ticket.id})
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.get(
            reverse("helpdesk:update", kwargs={"ticket_id": self.my_ticket.id})
        )
        self.assertEqual(response.status_code, 200)

    def test_kanban_update_checks_the_authorization_helper(self):
        """kanban_update_ticket filtered on get_queues(), which also returns
        queues accepting public submissions, so a status could be written on a
        ticket the user cannot open."""
        public_queue = Queue.objects.create(
            title="Public", slug="pub", allow_public_submission=True
        )
        ticket = Ticket.objects.create(title="Public one", queue=public_queue)
        response = self.client.post(
            reverse("helpdesk:kanban_update", kwargs={"ticket_id": ticket.id}),
            json.dumps({"status": Ticket.CLOSED_STATUS}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        ticket.refresh_from_db()
        self.assertNotEqual(ticket.status, Ticket.CLOSED_STATUS)

    def test_forged_relation_is_rejected_with_a_response(self):
        """Scoping the follow-up form's ticket queryset turns a foreign id into
        a validation error, and the view has to answer that with the form and
        its errors rather than falling off the end and returning None."""
        my_followup = FollowUp.objects.create(
            ticket=self.my_ticket, title="Mine", comment="Mine"
        )
        response = self.client.post(
            reverse(
                "helpdesk:followup_edit",
                kwargs={
                    "ticket_id": self.my_ticket.id,
                    "followup_id": my_followup.id,
                },
            ),
            {
                "title": "Moved",
                "ticket": self.foreign.id,
                "comment": "Moved",
                "new_status": self.my_ticket.status,
                "time_spent": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, MARKER)
        my_followup.refresh_from_db()
        self.assertEqual(my_followup.ticket_id, self.my_ticket.id)

    def test_the_query_class_applies_the_boundary_itself(self):
        """A HELPDESK_QUERY_CLASS that overrides get() must not be able to drop
        the queue boundary, so __run__() applies it rather than trusting the
        queryset it is handed."""
        from helpdesk.query import __Query__
        from helpdesk.user import HelpdeskUser

        query = __Query__(
            HelpdeskUser(self.staff),
            query_params={"filtering": {}, "sorting": "created", "search_string": ""},
        )
        results = query.__run__(Ticket.objects.all())
        self.assertNotIn(self.foreign, results)
        self.assertIn(self.my_ticket, results)


class AccessibleTicketsParityTestCase(TestCase):
    """The queryset and the predicate must agree, ticket by ticket.

    accessible_tickets() exists so that one rule decides what a user may reach.
    That only holds while it returns exactly what can_access_ticket() answers
    for the same ticket, and the two are written differently enough that they
    can drift: one reads has_perm() per queue, the other compares a stored
    permission name against the user's permission set.
    """

    def build(self):
        User = get_user_model()
        granted = Queue.objects.create(title="Granted", slug="granted")
        other = Queue.objects.create(title="Other", slug="other")
        public = Queue.objects.create(
            title="Public", slug="public", allow_public_submission=True
        )
        users = {
            "staff": User.objects.create(username="s", is_staff=True),
            "non-staff": User.objects.create(username="n", is_staff=False),
            "superuser": User.objects.create(
                username="r", is_staff=True, is_superuser=True
            ),
            "grouped": User.objects.create(username="g", is_staff=True),
        }
        permission = Permission.objects.get(codename=granted.permission_name[9:])
        for label, user in users.items():
            if label == "grouped":
                # Holds the queue permission through a group rather than
                # directly, which get_user_permissions() would not report.
                group = Group.objects.create(name="agents")
                group.permissions.add(permission)
                user.groups.add(group)
            else:
                user.user_permissions.add(permission)
        tickets = [
            Ticket.objects.create(title="in a granted queue", queue=granted),
            Ticket.objects.create(title="in another queue", queue=other),
            Ticket.objects.create(title="in a public queue", queue=public),
            Ticket.objects.create(
                title="assigned, in another queue",
                queue=other,
                assigned_to=users["staff"],
            ),
        ]
        return users, tickets

    def test_the_queryset_matches_the_predicate(self):
        users, tickets = self.build()
        original = settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION
        self.addCleanup(
            setattr,
            settings,
            "HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION",
            original,
        )
        User = get_user_model()
        for per_queue in (True, False):
            settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION = per_queue
            for label, known in users.items():
                # Re-read so the permission cache from a previous pass is gone.
                huser = HelpdeskUser(User.objects.get(username=known.username))
                reachable = set(huser.accessible_tickets().values_list("id", flat=True))
                for ticket in tickets:
                    with self.subTest(
                        per_queue=per_queue, user=label, ticket=ticket.title
                    ):
                        self.assertEqual(
                            huser.can_access_ticket(ticket),
                            ticket.id in reachable,
                            f"accessible_tickets() and can_access_ticket() "
                            f"disagree about '{ticket.title}' for the {label} "
                            f"account with per-queue mode {per_queue}",
                        )
