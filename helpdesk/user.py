from helpdesk.models import (
    Ticket,
    Queue,
    KBCategory,
    KBItem,
)
from seed.lib.superperms.orgs.models import Organization, get_helpdesk_organizations

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
        # All queues for the users default org, and public queues available therein, unless user is superuser
        all_queues = Queue.objects.filter(organization=user.default_organization.helpdesk_organization)
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
            if category.queue:
                return self.can_access_queue(category.queue)
            else:
                return True
        elif is_helpdesk_staff(self.user) and self.can_access_organization(category.organization):
            return True
        elif self.has_full_access() and self.can_access_organization(category.organization):
            return True
        else:
            return False

    def can_access_kbarticle(self, article):
        """Check to see if the user has permission to access
            a KBarticle. If not deny access. Should be Org
            dependent. Uses can_access_kbcategory.
        :param article, Helpdesk model KBArticle
        :return boolean, whether user has access to it or not
        """
        if not HelpdeskUser.can_access_kbcategory(self, article.category):
            return False
        elif self.has_full_access() and self.can_access_organization(article.category.organization):
            return True
        elif article.enabled:
            return True
        else:
            return False

    def can_access_organization(self, organization):
        helpdesk_organizations = get_helpdesk_organizations()

        if is_helpdesk_staff(self.user):
            return self.user.default_organization.helpdesk_organization == organization
        else:
            if self.request and 'org' in self.request.GET:
                url_org = self.request.GET.get('org')
                org = helpdesk_organizations.filter(name=url_org).first()
                return org == organization
            elif not self.user.is_anonymous:
                return self.user.default_organization.helpdesk_organization == organization
            elif len(helpdesk_organizations) == 1:
                return helpdesk_organizations.first() == organization
            else:
                return False
