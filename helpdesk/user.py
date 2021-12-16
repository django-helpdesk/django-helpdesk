from helpdesk.models import (
    Ticket,
    Queue,
    KBCategory,
    KBItem,
)
from seed.lib.superperms.orgs.models import Organization

from helpdesk import settings as helpdesk_settings
from helpdesk.decorators import is_helpdesk_staff


def huser_from_request(req):
    return HelpdeskUser(req.user, req)


class HelpdeskUser:
    def __init__(self, user, request=None):
        self.user = user
        self.request = request

    def get_queues(self):
        """Return the list of Queues the user can access.

        :param user: The User (the class should have the has_perm method)
        :return: A Python list of Queues
        """
        user = self.user
        # All queues for the users default org, and public queues available therein
        all_queues = Queue.objects.filter(organization=user.default_organization_id)
        public_ids = [q.pk for q in
                      all_queues.filter(allow_public_submission=True)]
        limit_queues_by_user = \
            helpdesk_settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION \
            and not user.is_superuser
        if limit_queues_by_user:
            id_list = [q.pk for q in all_queues if user.has_perm(q.permission_name)]
            id_list += public_ids
            return all_queues.filter(pk__in=id_list)
        else:
            return all_queues

    def get_allowed_kb_categories(self):
        categories = []
        for cat in KBCategory.objects.all():
            if self.can_access_kbcategory(cat):
                categories.append(cat)
        return categories

    def get_assigned_kb_items(self):
        kbitems = []
        for item in KBItem.objects.all():
            if item.team and item.team.is_member(self.user):
                kbitems.append(item)
        return kbitems

    def get_tickets_in_queues(self):
        return Ticket.objects.filter(queue__in=self.get_queues())

    def has_full_access(self):
        return self.user.is_superuser

    def can_access_queue(self, queue):
        """Check if a certain user can access a certain queue.
            Users should only be able to access that queue if it is within their org

        :param user: The User (the class should have the has_perm method)
        :param queue: The django-helpdesk Queue instance
        :return: True if the user has permission (either by default or explicitly), false otherwise
        """
        if self.can_access_organization(queue.organization):
            return True
        elif self.has_full_access():
            return True
        else:
            return (
                helpdesk_settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION
                and
                self.user.has_perm(queue.permission_name)
            )

    def can_access_ticket(self, ticket):
        """Check to see if the user has permission to access
            a ticket. If not then deny access."""
        user = self.user
        if self.can_access_queue(ticket.queue):
            return True
        elif self.has_full_access() or (ticket.assigned_to and user.id == ticket.assigned_to.id):
            return True
        else:
            return False

    def can_access_kbcategory(self, category):
        """Check to see if the user has permission to access
            a KBcategory. If not deny access. Should be Org
            dependent
        :param category, Helpdesk model KBCategory
        :return boolean, whether user has access to it or not
        """
        # Order of precedence for access:
        # A public category should be visible to anyone in the organization
        # For non-public categories:
        # If the category has a queue, should be viewable if user has access to the org
        # If there's no queue, the category should only be visible for staff in the organization (since not public)
        # Otherwise, the category will be visible to superusers
        # Not viewable to anyone else
        if category.public and self.can_access_organization(category.organization):
            return True
        elif category.queue:
            return self.can_access_queue(category.queue)
        elif is_helpdesk_staff(self.user) and self.can_access_organization(category.organization):
            return True
        elif self.has_full_access():
            return True
        else:
            return False

    def can_access_organization(self, organization):
        if self.user.is_anonymous or not is_helpdesk_staff(self.user):
            # Check if the org in the url matches this organization
            url_org = self.request.GET.get('org')
            org = Organization.objects.filter(name=url_org).first()
            if org:
                return org == organization
            elif not org and self.user.is_authenticated:
                # If no org in url, default to users default_organization
                return self.user.default_organization == organization
            else:
                return False
        else:
            return self.user.default_organization == organization
