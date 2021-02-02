from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings


from helpdesk.models import Ticket
from helpdesk.lib import safe_template_context, send_templated_mail

class Command(BaseCommand):
    help = "Relaunch on hold tickets which didn't receive an answer in the last 7 days"

    def handle(self, *args, **options):
        print(timezone.localtime())
        admin_user = get_user_model().objects.get(username='admin')
        comment = "<p>Bonjour</p>" \
                  "<p>Sauf erreur de notre part, nous n'avons pas reçu de retour sur ce ticket.</p>" \
                  "<p>Ceci est une relance automatique au bout de 7 jours sans réponse.</p>"
        target_date = date.today() - timedelta(days=7)
        for ticket in Ticket.objects.on_hold()\
                .filter(status__in=(Ticket.OPEN_STATUS, Ticket.REOPENED_STATUS, Ticket.RESOLVED_STATUS)):
            last_followup = ticket.followup_set.first()
            # Check if the last followup was public and made by a staff user
            if last_followup and last_followup.public and last_followup.user and last_followup.user.is_staff \
                    and last_followup.date.date() <= target_date:
                # Create Follow Up
                ticket.followup_set.create(
                    title="Relance Automatique",
                    comment=comment,
                    public=True,
                    user=admin_user
                )
                # Send mail to submitter
                context = safe_template_context(ticket)
                context['ticket']['comment'] = comment
                if ticket.get_submitter_emails():
                    send_templated_mail(
                        'updated_submitter',
                        context,
                        recipients=ticket.get_submitter_emails(),
                        sender=ticket.queue.from_address,
                        fail_silently=True,
                    )
                self.stdout.write(self.style.SUCCESS(f'Relaunch ticket #{ticket.id}'))