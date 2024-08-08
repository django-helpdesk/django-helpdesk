from helpdesk.models import (
    Ticket,
    Queue,
    KBCategory,
    KBItem,
)
from seed.lib.superperms.orgs.models import Organization, get_helpdesk_count, get_helpdesk_orgs_for_domain

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
            id_list = [q.pk for q in all_queues if user.has_perm_class(q.permission_name)]
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
        """
        Checks if a user can view the queue based on the user's current default_organization.
            User must be staff or have staff permissions.
        Works independent of the user's role permissions in the queue's organization.
        Does not check whether a user (staff or otherwise) is allowed to submit tickets to a queue,
            and doesn't check if the queue is public or not.
        """
        if self.check_default_org(queue.organization):
            if is_helpdesk_staff(self.user) or self.has_full_access():
                return True
            else:
                return (
                    helpdesk_settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION
                    and
                    self.user.has_perm_class(queue.permission_name)
                )
        return False

    def can_access_ticket(self, ticket):
        """
        Checks if a user can view a ticket based on the user's current default_organization.
            User must be staff, have staff permissions, or be assigned to the ticket.
        Works independent of the user's role permissions in the ticket's organization alone.
        Method is intended for staff users - not for the public ticket view.
        Permits staff users to edit and update tickets in addition to viewing them.
        """
        if self.check_default_org(ticket.ticket_form.organization) and (
                is_helpdesk_staff(self.user) or
                self.has_full_access() or
                (ticket.assigned_to and self.user.id == ticket.assigned_to.id)):  # todo add user is CC'd in ticket
            return True
        else:
            return False

    def can_access_kbcategory(self, category):
        """
        Checks if a user can view the KB category page based on the user's current default_organization.
            User does NOT have to be staff; if not, category must be public.
        Works independent of the user's role permissions in the category's organization.
        """
        if is_helpdesk_staff(self.user) or self.has_full_access():
            return self.check_default_org(category.organization)

        helpdesk_orgs = []
        if self.request:
            domain_id = getattr(self.request, 'domain_id', None)
            helpdesk_orgs = get_helpdesk_orgs_for_domain(domain_id)

        if category.public:
            if len(helpdesk_orgs) == 1 and helpdesk_orgs.first() == category.organization:
                return True
            return self.check_default_org(category.organization)
        return False

    def can_access_kbarticle(self, article):
        """
        Checks if a user can view the KB article page based on the user's current default_organization.
            User does NOT have to be staff; if not, article must be public.
        Works independent of the user's role permissions in the article's organization.
        """
        if is_helpdesk_staff(self.user) or self.has_full_access():
            return self.check_default_org(article.category.organization)

        helpdesk_orgs = []
        if self.request:
            domain_id = getattr(self.request, 'domain_id', None)
            helpdesk_orgs = get_helpdesk_orgs_for_domain(domain_id)

        if article.category.public and article.enabled:
            if len(helpdesk_orgs) == 1 and helpdesk_orgs.first() == article.category.organization:
                return True
            return self.check_default_org(article.category.organization)
        return False

    def can_access_form(self, form):
        """
        Checks if a user can view the form based on the user's current default_organization.
            User must be staff or have staff permissions.
        Works independent of the user's role permissions in the form's organization.
        """
        if is_helpdesk_staff(self.user) or self.has_full_access():
            return self.check_default_org(form.organization)

        helpdesk_orgs = []
        if self.request:
            domain_id = getattr(self.request, 'domain_id', None)
            helpdesk_orgs = get_helpdesk_orgs_for_domain(domain_id)

        if form.public:
            if len(helpdesk_orgs) == 1 and helpdesk_orgs.first() == form.organization:
                return True
            return self.check_default_org(form.organization)
        return False

    def check_default_org(self, organization):
        """
        Checks that the user's current default_organization helpdesk matches the given organization.
        If the user switches to a new organization in the dropdown, this method can be used to check if
        the user should be kicked off their current page, to be redirected to a different landing page.

        :param organization: Organization object
        """
        if self.request and 'org' in self.request.GET:
            url_org = self.request.GET.get('org')
            try:
                org = Organization.objects.get(name=url_org)
            except Organization.DoesNotExist:
                return False
            return org.helpdesk_organization.id == organization.id
        elif self.user.is_authenticated and self.user.is_active and self.user.default_organization is not None:
            return self.user.default_organization.helpdesk_organization.id == organization.id
        else:
            return False
