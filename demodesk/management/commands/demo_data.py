"""Generate a realistic data set for the demo project.

Every date is computed relative to the current time, so the dashboard and the
reports (tickets by age, average resolution time over the last 60 days, monthly
charts) keep the same shape whenever the data is generated. The random generator is
seeded, so each run produces the same tickets; only those whose closing date
falls around the current time can end up open or closed.

The command builds on top of the demo.json fixture (admin user, the first two
queues and knowledge base items), which must be loaded first, or use --reset.
"""

import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from helpdesk.models import (
    Checklist,
    ChecklistTemplate,
    CustomField,
    FollowUp,
    KBCategory,
    KBItem,
    Queue,
    Ticket,
    TicketCC,
    TicketCustomFieldValue,
    TicketDependency,
)

from . import _demo_content as content

User = get_user_model()

# How long the demo history goes back.
HISTORY_DAYS = 240
RANDOM_TICKETS = 130

# Range of days needed to close a ticket, per priority.
RESOLUTION_DAYS = {1: (0.1, 2), 2: (0.5, 6), 3: (1, 14), 4: (3, 35), 5: (7, 60)}
PRIORITY_WEIGHTS = {1: 5, 2: 15, 3: 50, 4: 20, 5: 10}

# Knowledge base article suggested for tickets whose title contains the key.
KB_LINKS = {
    "VPN": "Connecting to the VPN",
    "Phishing": "Recognizing a phishing e-mail",
    "CSV": "Importing data from a CSV file",
    "refund": "Getting a refund",
    "Payment failed": "Changing your payment method",
}


class Command(BaseCommand):
    help = (
        "Generate demo users, queues, tickets, follow-ups, checklists and "
        "knowledge base articles, dated relative to now."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help=(
                "Flush the database and reload the emailtemplate.json and "
                "demo.json fixtures before generating the data."
            ),
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=1476,
            help="Seed for the random generator (default: %(default)s).",
        )

    def handle(self, *args, reset=False, seed=1476, **options):
        if reset:
            call_command("flush", interactive=False, verbosity=0)
            call_command("loaddata", "emailtemplate.json", "demo.json", verbosity=0)

        admin = User.objects.filter(username="admin").first()
        if admin is None:
            raise CommandError(
                "The demo.json fixture is not loaded. Run "
                "'manage.py loaddata emailtemplate.json demo.json' first, "
                "or use --reset."
            )
        if User.objects.filter(username=content.STAFF[0][0]).exists():
            self.stdout.write(
                "Demo data is already present, nothing to do. "
                "Use --reset to generate it again."
            )
            return

        with transaction.atomic():
            DemoData(random.Random(seed), timezone.now(), admin).build()

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo data generated: {Ticket.objects.count()} tickets, "
                f"{FollowUp.objects.count()} follow-ups, "
                f"{User.objects.count()} users."
            )
        )


class DemoData:
    def __init__(self, rng, now, admin):
        self.rng = rng
        self.now = now
        self.admin = admin
        self.month_factor = {}

    def build(self):
        self.create_users()
        self.create_queues()
        self.create_custom_fields()
        self.create_knowledge_base()
        self.create_checklist_templates()
        self.redate_fixture_tickets()
        self.create_random_tickets()
        self.create_customer_tickets()
        self.create_onboarding_tickets()
        self.create_website_launch_tickets()

    # Helpers

    def at(self, days_ago, hour=None):
        """A datetime `days_ago` days back, during office hours, never in the future."""
        hour = self.rng.randint(8, 17) if hour is None else hour
        moment = (self.now - timedelta(days=days_ago)).replace(
            hour=hour, minute=self.rng.randint(0, 59), second=0, microsecond=0
        )
        if moment > self.now:
            moment = self.now - timedelta(minutes=self.rng.randint(5, 90))
        return moment

    def between(self, start, end):
        return start + (end - start) * self.rng.uniform(0.1, 0.9)

    def weighted(self, weights):
        return self.rng.choices(list(weights), weights=list(weights.values()))[0]

    def name(self, user):
        return user.get_full_name() or user.get_username() if user else "Unassigned"

    def resolution_days(self, priority, created):
        """Days needed to close a ticket; some months are busier than others."""
        month = (created.year, created.month)
        if month not in self.month_factor:
            self.month_factor[month] = self.rng.uniform(0.6, 1.7)
        if self.rng.random() < 0.1:
            # Tickets stuck waiting for a third party
            return self.rng.uniform(40, 120)
        low, high = RESOLUTION_DAYS[priority]
        return self.rng.uniform(low, high) * self.month_factor[month]

    def followup(self, ticket, date, title, comment="", public=True, user=None, **kw):
        changes = kw.pop("changes", ())
        followup = FollowUp.objects.create(
            ticket=ticket,
            date=date,
            title=title,
            comment=comment,
            public=public,
            user=user,
            **kw,
        )
        for field, old, new in changes:
            followup.ticketchange_set.create(
                field=field, old_value=str(old), new_value=str(new)
            )
        return followup

    def new_ticket(self, queue, title, description, created, submitter, user=None):
        ticket = Ticket.objects.create(
            queue=queue,
            title=title,
            description=description,
            submitter_email=submitter,
            status=Ticket.OPEN_STATUS,
        )
        self.followup(ticket, created, "Ticket Opened", description, user=user)
        return ticket

    def save_dates(self, ticket, created):
        """Store the final state: created/modified are auto fields, hence update()."""
        last = ticket.followup_set.order_by("-date").first()
        ticket.save()
        Ticket.objects.filter(pk=ticket.pk).update(
            created=created, modified=last.date if last else created
        )

    def status_change(self, ticket, new_status):
        old = ticket.get_status_display()
        ticket.status = new_status
        return ("Status", old, ticket.get_status_display())

    # Reference data

    def create_users(self):
        # Everyone shares the admin password, without paying for hashing again.
        password = self.admin.password
        self.staff = {}
        for username, first, last, queues in content.STAFF:
            user = User.objects.create(
                username=username,
                first_name=first,
                last_name=last,
                email=f"{username}@example.com",
                is_staff=True,
                password=password,
            )
            self.staff[username] = (user, queues)
        username, first, last, email = content.CUSTOMER
        self.customer = User.objects.create(
            username=username,
            first_name=first,
            last_name=last,
            email=email,
            password=password,
        )

    def create_queues(self):
        self.queues = {q.slug: q for q in Queue.objects.all()}
        for title, slug, email in content.NEW_QUEUES:
            self.queues[slug] = Queue.objects.create(
                title=title,
                slug=slug,
                email_address=email,
                allow_public_submission=True,
                escalate_days=3,
            )

    def create_custom_fields(self):
        self.custom_fields = {
            "BIL": CustomField.objects.create(
                name="customer_reference",
                label="Customer reference",
                data_type="varchar",
                max_length=20,
                ordering=1,
            ),
            "SP": CustomField.objects.create(
                name="product_version",
                label="Product version",
                data_type="list",
                list_values="4.2\n4.1\n4.0\n3.9",
                empty_selection_list=True,
                ordering=2,
            ),
            "IT": CustomField.objects.create(
                name="onsite_visit",
                label="On-site visit needed",
                data_type="boolean",
                staff_only=True,
                ordering=3,
            ),
        }

    def custom_field_value(self, slug):
        if slug == "BIL":
            return f"ACME-{self.rng.randint(1000, 9999)}"
        if slug == "SP":
            return self.rng.choice(["4.2", "4.2", "4.1", "4.0", "3.9"])
        return str(self.rng.random() < 0.3)

    def create_knowledge_base(self):
        voters = [user for user, _ in self.staff.values()] + [self.customer]
        for item in KBItem.objects.all():
            item.last_updated = self.at(self.rng.randint(60, 200))
            item.save()
        self.kb_items = {}
        for title, slug, description, queue, items in content.KB_CATEGORIES:
            category = KBCategory.objects.create(
                name=title,
                title=title,
                slug=slug,
                description=description,
                queue=self.queues[queue],
            )
            for order, (item_title, question, answer) in enumerate(items):
                votes = self.rng.randint(2, len(voters))
                item = KBItem.objects.create(
                    category=category,
                    title=item_title,
                    question=question,
                    answer=answer,
                    order=order,
                    votes=votes,
                    recommendations=self.rng.randint(votes // 2, votes),
                    last_updated=self.at(self.rng.randint(5, 150)),
                )
                item.voted_by.set(voters[:votes])
                self.kb_items[item_title] = item

    def create_checklist_templates(self):
        self.checklist_templates = {
            key: ChecklistTemplate.objects.create(name=name, task_list=tasks)
            for key, (name, tasks) in content.CHECKLIST_TEMPLATES.items()
        }

    def add_checklist(self, ticket, key, done, start, end):
        """Attach a checklist with its first `done` tasks completed between start and end."""
        template = self.checklist_templates[key]
        checklist = Checklist.objects.create(ticket=ticket, name=template.name)
        checklist.create_tasks_from_template(template)
        tasks = list(checklist.tasks.all())[:done]
        for position, task in enumerate(tasks, start=1):
            task.completion_date = start + (end - start) * position / (len(tasks) + 1)
            task.save()
        return checklist

    # Tickets

    def redate_fixture_tickets(self):
        """Bring the tickets of demo.json into the recent past."""
        for pk, days_ago in ((1, 2), (2, 9), (3, 35)):
            ticket = Ticket.objects.filter(pk=pk).first()
            if ticket is None:
                continue
            created = self.at(days_ago)
            delta = created - ticket.created
            for followup in ticket.followup_set.all():
                FollowUp.objects.filter(pk=followup.pk).update(
                    date=followup.date + delta
                )
            if ticket.due_date:
                ticket.due_date += delta
            if pk == 3:
                ticket.assigned_to = self.admin
            self.save_dates(ticket, created)

    def pick_assignee(self, slug):
        if self.rng.random() < 0.15:
            return self.admin
        candidates = [user for user, queues in self.staff.values() if slug in queues]
        return self.rng.choice(candidates)

    def create_random_tickets(self):
        ages = sorted(
            (HISTORY_DAYS * self.rng.random() ** 1.3 for _ in range(RANDOM_TICKETS)),
            reverse=True,
        )
        previous = []
        for age in ages:
            previous.append(self.create_random_ticket(age, previous))

    def create_random_ticket(self, age, previous):
        rng = self.rng
        slug = self.weighted(content.QUEUE_WEIGHTS)
        title, description, resolution = rng.choice(content.ISSUES[slug])
        priority = self.weighted(PRIORITY_WEIGHTS)
        submitter = rng.choice(content.SUBMITTERS)
        created = self.at(age)
        assignee = self.pick_assignee(slug)

        duplicate = previous and rng.random() < 0.03
        if duplicate:
            close_at = created + timedelta(hours=rng.uniform(1, 30))
        else:
            close_at = created + timedelta(days=self.resolution_days(priority, created))
        done = close_at < self.now
        end = close_at if done else self.now

        # Tickets nobody picked up yet
        if not done and rng.random() < 0.3:
            assignee = None

        ticket = self.new_ticket(
            self.queues[slug], title, description, created, submitter
        )
        if slug in self.custom_fields and rng.random() < 0.7:
            TicketCustomFieldValue.objects.create(
                ticket=ticket,
                field=self.custom_fields[slug],
                value=self.custom_field_value(slug),
            )
        for key, item_title in KB_LINKS.items():
            if key in title:
                ticket.kbitem = self.kb_items[item_title]

        # Assignment, either at creation or with a follow-up
        if assignee:
            if rng.random() < 0.5:
                ticket.assigned_to = assignee
            else:
                when = created + (end - created) * rng.uniform(0.02, 0.15)
                self.followup(
                    ticket,
                    when,
                    f"Assigned to {self.name(assignee)}",
                    user=self.admin if rng.random() < 0.4 else assignee,
                    changes=[("Owner", "Unassigned", self.name(assignee))],
                )
                ticket.assigned_to = assignee
        agent = assignee or self.admin

        if rng.random() < 0.12 and priority < 5:
            when = created + (end - created) * rng.uniform(0.15, 0.3)
            self.followup(
                ticket,
                when,
                "Updated",
                public=False,
                user=agent,
                changes=[
                    ("Priority", priority + 1, priority),
                ],
            )

        if duplicate:
            original = rng.choice(previous[-20:])
            ticket.status = Ticket.DUPLICATE_STATUS
            self.followup(
                ticket,
                close_at,
                "Duplicate",
                f"Duplicate of #{original.id}, closing this one.",
                user=agent,
                new_status=Ticket.DUPLICATE_STATUS,
                changes=[("Status", "Open", "Duplicate")],
            )
            ticket.priority = priority
            self.save_dates(ticket, created)
            return ticket

        self.add_conversation(ticket, submitter, agent, created, end)

        if slug == "BIL" and "refund" in title.lower() + description.lower():
            self.add_checklist(
                ticket,
                "refund",
                4 if done else rng.randint(0, 3),
                created,
                end,
            )

        if done:
            self.close(ticket, agent, resolution, created, close_at)
        else:
            if age > 7 and rng.random() < 0.2:
                self.reopen(ticket, submitter, agent, resolution, created)
            if rng.random() < 0.08:
                ticket.on_hold = True
            if priority <= 2 or rng.random() < 0.2:
                ticket.due_date = created + timedelta(days=3 if priority <= 2 else 14)

        ticket.priority = priority
        self.save_dates(ticket, created)
        return ticket

    def add_conversation(self, ticket, submitter, agent, start, end):
        """Replies, customer answers and internal notes between start and end."""
        rng = self.rng
        count = rng.choices([0, 1, 2, 3], weights=[2, 4, 3, 2])[0]
        dates = sorted(
            start + (end - start) * rng.uniform(0.2, 0.9) for _ in range(count)
        )
        for index, date in enumerate(dates):
            kind = rng.choices(["reply", "customer", "note"], weights=[5, 3, 3])[0]
            if kind == "reply" or (kind == "customer" and index == 0):
                self.followup(
                    ticket,
                    date,
                    "Comment",
                    rng.choice(content.STAFF_REPLIES),
                    user=agent,
                )
            elif kind == "customer":
                self.followup(
                    ticket,
                    date,
                    f"E-Mail Received from {submitter}",
                    rng.choice(content.CUSTOMER_REPLIES),
                    message_id=f"<demo-{ticket.pk}-{index}@example.com>",
                )
            else:
                self.followup(
                    ticket,
                    date,
                    "Comment",
                    rng.choice(content.PRIVATE_NOTES),
                    public=False,
                    user=agent,
                )

    def close(self, ticket, agent, resolution, created, close_at):
        ticket.resolution = resolution
        recently = close_at > self.now - timedelta(days=10)
        if recently and self.rng.random() < 0.5:
            # Resolved, waiting for the submitter to confirm
            self.followup(
                ticket,
                close_at,
                "Resolved",
                resolution,
                user=agent,
                new_status=Ticket.RESOLVED_STATUS,
                changes=[self.status_change(ticket, Ticket.RESOLVED_STATUS)],
            )
            return
        if self.rng.random() < 0.5:
            resolved_at = close_at - (close_at - created) * self.rng.uniform(0.05, 0.3)
            self.followup(
                ticket,
                resolved_at,
                "Resolved",
                resolution,
                user=agent,
                new_status=Ticket.RESOLVED_STATUS,
                changes=[self.status_change(ticket, Ticket.RESOLVED_STATUS)],
            )
            resolution = ""
        self.followup(
            ticket,
            close_at,
            "Closed",
            resolution,
            user=agent,
            new_status=Ticket.CLOSED_STATUS,
            changes=[self.status_change(ticket, Ticket.CLOSED_STATUS)],
        )

    def reopen(self, ticket, submitter, agent, resolution, created):
        """Resolved once, then reopened by the submitter."""
        resolved_at = self.between(created, self.now - timedelta(days=3))
        self.followup(
            ticket,
            resolved_at,
            "Resolved",
            resolution,
            user=agent,
            new_status=Ticket.RESOLVED_STATUS,
            changes=[self.status_change(ticket, Ticket.RESOLVED_STATUS)],
        )
        self.followup(
            ticket,
            self.between(resolved_at, self.now),
            "Reopened",
            self.rng.choice(content.REOPEN_REPLIES),
            message_id=f"<demo-{ticket.pk}-reopen@example.com>",
            new_status=Ticket.REOPENED_STATUS,
            changes=[self.status_change(ticket, Ticket.REOPENED_STATUS)],
        )

    def create_customer_tickets(self):
        """Tickets from the customer account, as submitted through the public form."""
        customer = self.customer
        agent = self.staff["bruno"][0]
        for (slug, title, description, resolution), (age, closed_after) in zip(
            content.CUSTOMER_TICKETS, [(50, 3.2), (21, 1.4), (4, None)]
        ):
            created = self.at(age)
            ticket = self.new_ticket(
                self.queues[slug], title, description, created, customer.email, customer
            )
            ticket.assigned_to = agent
            reply_at = created + timedelta(hours=self.rng.uniform(2, 20))
            self.followup(
                ticket, reply_at, "Comment", content.STAFF_REPLIES[1], user=agent
            )
            self.followup(
                ticket,
                reply_at + timedelta(hours=self.rng.uniform(1, 20)),
                "Comment",
                content.CUSTOMER_REPLIES[0],
                user=customer,
            )
            if closed_after:
                if title.startswith("How do I share"):
                    ticket.kbitem = self.kb_items["Sharing reports with your team"]
                self.close(
                    ticket,
                    agent,
                    resolution,
                    created,
                    created + timedelta(days=closed_after),
                )
            else:
                TicketCC.objects.create(
                    ticket=ticket,
                    email="olivia.brown@example.net",
                    can_view=True,
                )
            ticket.priority = 3
            self.save_dates(ticket, created)

    def create_onboarding_tickets(self):
        """A new hire: the onboarding ticket depends on two other tickets."""
        alice = self.staff["alice"][0]
        kenji = self.staff["kenji"][0]
        it = self.queues["IT"]
        created = self.at(6, hour=9)

        laptop = self.new_ticket(
            it,
            "Order laptop for Laura Chen",
            "Standard developer laptop, 32 GB RAM, US keyboard.",
            created,
            "hr@example.com",
        )
        laptop.assigned_to = kenji
        laptop.priority = 2
        self.close(
            laptop,
            kenji,
            "Laptop delivered and enrolled in device management.",
            created,
            self.at(3),
        )
        self.save_dates(laptop, created)

        accounts = self.new_ticket(
            it,
            "Create accounts for Laura Chen",
            "E-mail, chat, source code hosting and the VPN.",
            created,
            "hr@example.com",
        )
        accounts.assigned_to = alice
        accounts.priority = 2
        accounts.due_date = self.now + timedelta(days=2)
        self.followup(
            accounts,
            self.at(2),
            "Comment",
            "E-mail and chat accounts are ready, VPN access is pending approval.",
            public=False,
            user=alice,
        )
        self.save_dates(accounts, created)

        onboarding = self.new_ticket(
            it,
            "Onboard new hire: Laura Chen",
            "Laura joins the engineering team next Monday. Please get "
            "everything ready for her first day.",
            created,
            "hr@example.com",
        )
        onboarding.assigned_to = alice
        onboarding.priority = 2
        onboarding.due_date = self.now + timedelta(days=4)
        checklist = self.add_checklist(onboarding, "onboarding", 2, created, self.now)
        tasks = list(checklist.tasks.all())
        self.followup(
            onboarding,
            tasks[1].completion_date,
            "Updated",
            user=alice,
            public=False,
            changes=[
                (f"[{checklist.name}] {task.description}", "To do", "Completed")
                for task in tasks[:2]
            ],
        )
        TicketDependency.objects.create(ticket=onboarding, depends_on=laptop)
        TicketDependency.objects.create(ticket=onboarding, depends_on=accounts)
        self.save_dates(onboarding, created)

    def create_website_launch_tickets(self):
        chloe = self.staff["chloe"][0]
        kenji = self.staff["kenji"][0]
        web = self.queues["WEB"]

        created = self.at(2)
        bug = self.new_ticket(
            web,
            "Checkout redirects back to the cart",
            "After entering the payment details, customers land on the cart "
            "page again instead of the confirmation page.",
            created,
            "olivia.brown@example.net",
        )
        bug.assigned_to = kenji
        bug.priority = 1
        bug.due_date = self.now + timedelta(days=1)
        self.followup(
            bug,
            self.at(1),
            "Comment",
            "The payment provider changed their callback URL format. "
            "Patch is in review.",
            public=False,
            user=kenji,
        )
        self.save_dates(bug, created)

        created = self.at(12)
        launch = self.new_ticket(
            web,
            "Launch the winter campaign landing page",
            "Publish the landing page for the winter campaign. It must not go "
            "live while the checkout bug is open.",
            created,
            "marketing@example.com",
        )
        launch.assigned_to = chloe
        launch.priority = 3
        launch.due_date = self.now + timedelta(days=10)
        self.followup(
            launch,
            self.at(8),
            "Comment",
            "The page is ready on staging, waiting for the checkout fix.",
            user=chloe,
        )
        TicketDependency.objects.create(ticket=launch, depends_on=bug)
        self.save_dates(launch, created)
