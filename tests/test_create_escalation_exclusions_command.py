from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from helpdesk.models import EscalationExclusion


class CreateEscalationExclusionsCommandTests(TestCase):
    def test_creates_exclusion_for_selected_weekday(self):
        today = timezone.now().date()
        target_date = today + timedelta(days=1)
        day_name = target_date.strftime("%A").lower()

        call_command("create_escalation_exclusions", days=[day_name])

        exclusion = EscalationExclusion.objects.get(date=target_date)
        self.assertEqual(exclusion.name, f"Auto Exclusion for {day_name}")
        self.assertEqual(exclusion.queues.count(), 0)

    def test_associates_exclusion_with_selected_queue(self):
        from helpdesk.models import Queue

        queue = Queue.objects.create(title="Support", slug="support")
        target_date = timezone.now().date() + timedelta(days=1)
        day_name = target_date.strftime("%A").lower()

        call_command(
            "create_escalation_exclusions",
            days=[day_name],
            queues=[queue.slug],
        )

        exclusion = EscalationExclusion.objects.get(date=target_date)
        self.assertEqual(list(exclusion.queues.all()), [queue])

    def test_does_not_create_duplicate_exclusions(self):
        target_date = timezone.now().date() + timedelta(days=1)
        day_name = target_date.strftime("%A").lower()

        call_command("create_escalation_exclusions", days=[day_name])
        call_command("create_escalation_exclusions", days=[day_name])

        self.assertEqual(
            EscalationExclusion.objects.filter(date=target_date).count(), 1
        )

    def test_rejects_zero_occurrences(self):
        from django.core.management.base import CommandError

        target_date = timezone.now().date() + timedelta(days=1)
        day_name = target_date.strftime("%A").lower()

        with self.assertRaises(CommandError):
            call_command(
                "create_escalation_exclusions",
                days=[day_name],
                occurrences=0,
            )

        self.assertFalse(EscalationExclusion.objects.exists())
