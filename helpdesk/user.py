from helpdesk.models import (
    Ticket,
    Queue
)

from helpdesk import settings as helpdesk_settings


class HelpdeskUser:
    def __init__(self, user):
        self.user = user

    def get_queues(self):
        """Return the list of Queues the user can access.

        :param user: The User (the class should have the has_perm method)
        :return: A Python list of Queues
        """
        user = self.user
        all_queues = Queue.objects.all()
        public_ids = [q.pk for q in
                      Queue.objects.filter(allow_public_submission=True)]
        limit_queues_by_user = \
            helpdesk_settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION \
            and not user.is_superuser
        if limit_queues_by_user:
            id_list = [q.pk for q in all_queues if user.has_perm(q.permission_name)]
            id_list += public_ids
            return all_queues.filter(pk__in=id_list)
        else:
            return all_queues

    def get_tickets_in_queues(self):
        return Ticket.objects.filter(queue__in=self.get_queues())

    def can_access_queue(self, queue):
        """Check if a certain user can access a certain queue.

        :param user: The User (the class should have the has_perm method)
        :param queue: The django-helpdesk Queue instance
        :return: True if the user has permission (either by default or explicitly), false otherwise
        """
        user = self.user
        if user.is_superuser or not helpdesk_settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION:
            return True
        else:
            return user.has_perm(queue.permission_name)

    def can_access_ticket(self, ticket):
        """Check to see if the user has permission to access
            a ticket. If not then deny access."""
        user = self.user
        if self.can_access_queue(ticket.queue):
            return True
        elif user.is_superuser or user.is_staff or \
                (ticket.assigned_to and user.id == ticket.assigned_to.id):
            return True
        else:
            return False
