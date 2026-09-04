from django.db.models import Q

from helpdesk import settings as helpdesk_settings
from helpdesk.models import Queue, Ticket

if helpdesk_settings.HELPDESK_KB_ENABLED:
    from helpdesk.models import KBCategory, KBItem


def huser_from_request(req):
    return HelpdeskUser(req.user)


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
        public_ids = [q.pk for q in Queue.objects.filter(allow_public_submission=True)]
        limit_queues_by_user = (
            helpdesk_settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION
            and not user.is_superuser
        )
        if limit_queues_by_user:
            id_list = [q.pk for q in all_queues if user.has_perm(q.permission_name)]
            id_list += public_ids
            return all_queues.filter(pk__in=id_list)
        else:
            return all_queues

    def get_allowed_kb_categories(self):
        categories = []
        if helpdesk_settings.HELPDESK_KB_ENABLED:
            for cat in KBCategory.objects.all():
                if self.can_access_kbcategory(cat):
                    categories.append(cat)
        return categories

    def get_assigned_kb_items(self):
        kbitems = []
        if helpdesk_settings.HELPDESK_KB_ENABLED:
            for item in KBItem.objects.all():
                if item.get_team() and item.get_team().is_member(self.user):
                    kbitems.append(item)
        return kbitems

    def accessible_queues(self):
        """Queues this user may actually open a ticket in.

        Narrower than get_queues(), which also returns every queue accepting
        public submissions so that they appear in the queue pickers.
        """
        return [q for q in self.get_queues() if self.can_access_queue(q)]

    def accessible_tickets_q(self):
        """can_access_ticket() as a Q, to apply to any Ticket queryset.

        Expressed as a Q rather than a queryset so a caller that already has one
        can narrow it in the same query instead of joining against a subquery.
        Matching can_access_ticket() means a granted queue or a ticket assigned
        to this user, whatever queue that ticket lives in.

        Queue permissions are read with get_all_permissions() rather than
        get_user_permissions(): the latter omits permissions held through a
        group, which is how installations of any size grant queue access.
        """
        if self.has_full_access():
            return Q()
        if not self.user.is_authenticated:
            return Q(pk__in=[])
        reachable = Q(assigned_to=self.user)
        if helpdesk_settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION:
            # Guarded on the setting for the same reason can_access_queue() is:
            # with per-queue mode off, a queue permission grants nothing, and
            # the two must not disagree about that.
            reachable |= Q(queue__permission_name__in=self.user.get_all_permissions())
        return reachable

    def accessible_tickets(self):
        """The queryset form of can_access_ticket(), for views and viewsets that
        resolve a ticket from a caller-supplied id.

        Single place where the rule lives: every path that serves or mutates a
        ticket should start from this rather than from Ticket.objects, so that
        forgetting the check is not the default.
        """
        return Ticket.objects.filter(self.accessible_tickets_q())

    def has_full_access(self):
        if self.user.is_superuser:
            return True
        if helpdesk_settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION:
            return False
        return self.user.is_staff or bool(
            helpdesk_settings.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE
        )

    def can_access_queue(self, queue):
        """Check if a certain user can access a certain queue.

        :param user: The User (the class should have the has_perm method)
        :param queue: The django-helpdesk Queue instance
        :return: True if the user has permission (either by default or explicitly), false otherwise
        """
        if self.has_full_access():
            return True
        else:
            return (
                helpdesk_settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION
                and self.user.has_perm(queue.permission_name)
            )

    def can_access_ticket(self, ticket):
        """Check to see if the user has permission to access
        a ticket. If not then deny access."""
        user = self.user
        return bool(
            self.can_access_queue(ticket.queue)
            or self.has_full_access()
            or ticket.assigned_to
            and user.id == ticket.assigned_to.id
        )

    def can_access_kbcategory(self, category):
        if category.public:
            return True
        return self.has_full_access() or (
            category.queue and self.can_access_queue(category.queue)
        )
