from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ObjectDoesNotExist

from django.contrib.auth.models import User

from helpdesk.models import Ticket


class Command(BaseCommand):
    help = 'Switches all tickets with an old email address to a new one.'

    def add_arguments(self, parser):
        parser.add_argument('old_email', type=str)
        parser.add_argument('new_email', type=str)

    def handle(self, *args, **options):
        """
        Get all tickets with old email and update them with new email.
        """

        old_email = options['old_email']
        new_email = options['new_email']

        try:
            User.objects.get(email=new_email)
        except ObjectDoesNotExist:
            raise CommandError('%s is not valid for any user' % new_email)

        old_tickets = Ticket.objects.filter(submitter_email=old_email)
        self.stdout.write('%s has %i tickets' % (old_email,
                                                 len(old_tickets)))

        new_tickets = Ticket.objects.filter(submitter_email=new_email)
        self.stdout.write('%s has %i tickets' % (new_email,
                                                 len(new_tickets)))

        self.stdout.write('-----BEGINNING MIGRATION-----')

        for ticket in old_tickets:
            ticket_old_email = ticket.submitter_email
            ticket.submitter_email = new_email
            ticket.save()
            self.stdout.write("Ticket %s - submitter_email changed: %s to %s"
                              % (ticket.ticket,
                                 ticket_old_email, new_email))

        self.stdout.write('-----UPDATE COMPLETE-----')

        old_tickets = Ticket.objects.filter(submitter_email=old_email)
        self.stdout.write('%s has %i tickets' % (old_email,
                                                 len(old_tickets)))

        new_tickets = Ticket.objects.filter(submitter_email=new_email)
        self.stdout.write('%s has %i tickets' % (new_email,
                                                 len(new_tickets)))
