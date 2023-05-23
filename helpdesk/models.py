"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

models.py - Model (and hence database) definitions. This is the core of the
            helpdesk structure.
"""

from django.contrib.auth.models import Permission
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _, ugettext
from io import StringIO
import re
import os
import mimetypes
import datetime
import logging

from django.utils.safestring import mark_safe
from markdown import markdown
from markdown.extensions import Extension
from markdown_deux.templatetags.markdown_deux_tags import markdown_allowed

import bleach
from bleach.linkifier import LinkifyFilter
from bleach.sanitizer import Cleaner
from bleach_allowlist import markdown_tags, markdown_attrs, print_tags, print_attrs, all_styles
from urllib.parse import urlparse, quote
from functools import partial

import pinax.teams.models

import uuid

from helpdesk import settings as helpdesk_settings
from helpdesk.decorators import is_helpdesk_staff

from .templated_email import send_templated_mail

from seed.lib.superperms.orgs.models import Organization, get_helpdesk_count_by_domain
from seed.models import (
    Column,
    Property,
    TaxLot,
)


logger = logging.getLogger(__name__)


def is_extra_data(field_name):
    """
    Replaces the CustomField field is_extra_data with a method. Returns true if the field is not one of the Ticket's
    default fields, i.e., the ones in the model.
    """
    return field_name not in ['queue', 'submitter_email', 'contact_name', 'contact_email', 'title',
                              'description', 'building_name', 'building_address', 'building_id', 'pm_id',
                              'attachment', 'due_date', 'priority', 'cc_emails']


def is_unlisted(field_name):
    """
    Replaces the CustomField field unlisted with a method. Returns true if the field is one that isn't displayed
    in the Ticket's table of fields once its created.
    """
    return field_name in ['queue', 'submitter_email', 'title', 'description', 'attachment', 'due_date',
                          'priority', 'cc_emails']


def format_time_spent(time_spent):
    if time_spent:
        time_spent = "{0:02d}h:{1:02d}m".format(
            time_spent.seconds // 3600,
            time_spent.seconds // 60 % 60,
        )
    else:
        time_spent = ""
    return time_spent


class EscapeHtml(Extension):
    def extendMarkdown(self, md, md_globals):
        del md.preprocessors['html_block']
        del md.inlinePatterns['html']


def _cleaner_set_target(domain, attrs, new=False):
    """Callback for bleach. Opens external urls in a new tab.
        Added directly from https://bleach.readthedocs.io/en/latest/linkify.html """
    p = urlparse(attrs[(None, 'href')])
    if p.netloc not in [domain.netloc, domain.hostname, domain.name, '']:
        attrs[(None, 'target')] = '_blank'
        attrs[(None, 'class')] = 'external'
    else:
        attrs.pop((None, 'target'), None)
    return attrs


def _cleaner_shorten_url(attrs, new=False):
    """Callback for bleach. Shortens overly-long URLs in the text.
        Added directly from https://bleach.readthedocs.io/en/latest/linkify.html """
    # Only adjust newly-created links
    if not new:
        return attrs
    # _text will be the same as the URL for new links
    text = attrs['_text']
    if len(text) > 50:
        attrs['_text'] = text[0:47] + '...'
    return attrs


def get_markdown(text, org, kb=False):
    if not text:
        return ""

    domain = org.domain

    extensions = [EscapeHtml(),
                  'markdown.extensions.nl2br',  # required for collapsing sections to work; a single newline doesn't break up a section, two newlines do
                  'markdown.extensions.fenced_code',  # required for collapsing sections
                  'markdown.extensions.tables']  # requested
    collapsible_attrs = {}
    if kb:
        extensions.append('markdown.extensions.attr_list')
        collapsible_attrs = {"p": ["data-target", "data-toggle", "data-parent", "role",
                                   'aria-controls', 'aria-expanded', 'aria-labelledby', 'id']}
    cleaner = Cleaner(
        filters=[partial(LinkifyFilter, callbacks=[partial(_cleaner_set_target, domain), _cleaner_shorten_url])],
        tags=markdown_tags + print_tags,
        attributes={**markdown_attrs,
                    **print_attrs,
                    **collapsible_attrs},
        styles=all_styles
    )
    cleaned = cleaner.clean(markdown(text, extensions=extensions))
    return mark_safe(cleaned)


class Queue(models.Model):
    """
    A queue is a collection of tickets into what would generally be business
    areas or departments.

    For example, a company may have a queue for each Product they provide, or
    a queue for each of Accounts, Pre-Sales, and Support.

    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)

    title = models.CharField(
        _('Title'),
        max_length=100,
    )

    slug = models.SlugField(
        _('Slug'),
        max_length=50,
        help_text=_('This slug is used when building ticket ID\'s. Once set, '
                    'try not to change it or e-mailing may get messy.'),
    )
    importer = models.ForeignKey('seed.EmailImporter', on_delete=models.SET_NULL, null=True, blank=True)
    match_on = models.JSONField(blank=True, default=list,
                                help_text="A list of strings. If you'd like only emails with "
                                          "certain subject lines to be imported into this queue, "
                                          "list that text here. Otherwise, leave blank.")
    match_on_addresses = models.JSONField(blank=True, default=list,
                                          help_text="A list of strings. If you'd like only emails from "
                                                    "specific addresses to be imported into this queue, "
                                                    "list those addresses here. Otherwise, leave blank.")

    allow_public_submission = models.BooleanField(
        _('Allow Public Submission?'),
        blank=True,
        default=False,
        help_text=_('Should this queue be listed on the public submission form?'),
    )

    escalate_days = models.IntegerField(
        _('Escalation Days'),
        blank=True,
        null=True,
        help_text=_('For tickets which are not held, how often do you wish to '
                    'increase their priority? Set to 0 for no escalation.'),
    )

    new_ticket_cc = models.CharField(
        _('New Ticket CC Address'),
        blank=True,
        null=True,
        max_length=200,
        help_text=_('If an e-mail address is entered here, then it will '
                    'receive notification of all new tickets created for this queue. '
                    'Enter a comma between multiple e-mail addresses.'),
    )

    updated_ticket_cc = models.CharField(
        _('Updated Ticket CC Address'),
        blank=True,
        null=True,
        max_length=200,
        help_text=_('If an e-mail address is entered here, then it will '
                    'receive notification of all activity (new tickets, closed '
                    'tickets, updates, reassignments, etc) for this queue. Separate '
                    'multiple addresses with a comma.'),
    )
    # TODO implement -- when off, this should turn off ALL notifications in the future
    enable_notifications_on_email_events = models.BooleanField(
        _('Notify contacts when email updates arrive'),
        blank=True,
        default=True,
        help_text=_('When an email arrives to either create a ticket or to '
                    'interact with an existing discussion. Should email notifications be sent ? '
                    'Note: the new_ticket_cc and updated_ticket_cc work independently of this feature'),
    )

    default_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='default_owner',
        blank=True,
        null=True,
        verbose_name=_('Default owner'),
    )

    reassign_when_closed = models.BooleanField(
        default=False,
        help_text=_('When a ticket is closed, reassign the ticket to the default owner (if one is set).')
    )

    dedicated_time = models.DurationField(
        help_text=_("Time to be spent on this Queue in total"),
        blank=True, null=True
    )

    def __str__(self):
        return "%s" % self.title

    class Meta:
        ordering = ('title',)
        verbose_name = _('Queue')
        verbose_name_plural = _('Queues')
        unique_together = ('organization', 'slug')

    @property
    def time_spent(self):
        """Return back total time spent on the ticket. This is calculated value
        based on total sum from all FollowUps
        """
        total = datetime.timedelta(0)
        for val in self.ticket_set.all():
            if val.time_spent:
                total = total + val.time_spent
        return total

    @property
    def time_spent_formatted(self):
        return format_time_spent(self.time_spent)

    @property
    def email_address(self):
        if self.importer:
            return self.importer.email_address
        elif self.organization.sender:
            return self.organization.sender.from_address
        else:
            return None

    @property
    def from_address(self):
        if self.importer:
            return self.importer.sender.from_address
        elif self.organization.sender:
            return self.organization.sender.from_address
        else:
            return u'NO EMAIL ADDRESS DEFINED <%s>' % settings.DEFAULT_FROM_EMAIL

    def prepare_permission_name(self):
        """Prepare internally the codename for the permission and store it in permission_name.
        :return: The codename that can be used to create a new Permission object.
        """
        # Prepare the permission associated to this Queue
        basename = "queue_access_%s" % self.slug
        self.permission_name = "helpdesk.%s" % basename
        return basename

    def save(self, *args, **kwargs):
        if not self.id:
            # Prepare the permission codename and the permission
            # (even if they are not needed with the current configuration)
            basename = self.prepare_permission_name()

            Permission.objects.create(
                name=_("Permission for queue: ") + self.title,
                content_type=ContentType.objects.get_for_model(self.__class__),
                codename=basename,
            )

        super(Queue, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        permission_name = None
        if hasattr(self, 'permission_name'):
            permission_name = self.permission_name

        super(Queue, self).delete(*args, **kwargs)

        # once the Queue is safely deleted, remove the permission (if exists)
        if permission_name:
            try:
                p = Permission.objects.get(codename=permission_name[9:])
                p.delete()
            except ObjectDoesNotExist:
                pass


def mk_secret():
    return str(uuid.uuid4())


class FormType(models.Model):

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    name = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(blank=True, null=True,
                                   help_text=_('Introduction text included in the form.'))
    queue = models.ForeignKey(Queue, on_delete=models.SET_NULL, null=True, blank=True,
                              help_text=_('Tickets should automatically be added to this queue.'
                                          'This option will hide the Queue field on the form.'))
    created = models.DateTimeField(auto_now_add=True, blank=True)
    updated = models.DateTimeField(auto_now=True, blank=True)
    public = models.BooleanField(_('Public'), blank=True, default=True,
                                 help_text=_('Should this form be accessible by everyone?'))
    staff = models.BooleanField(_('Staff'), blank=True, default=True,
                                help_text=_('Should this form be only accessible by staff? It will not be shown in the public form list.'))
    unlisted = models.BooleanField(_('Unlisted'), blank=False, default=False,
                                   help_text=_('Should this form be hidden from the public form list? '
                                               '(It will still be accessible by everyone if the "public" option is checked.)'))

    # Add Preset Form Fields to the Database, avoiding having to run a PSQL command in another terminal window.
    # This will happen automatically upon FormType Creation

    class Meta:
        verbose_name = _("Form")
        verbose_name_plural = _("Forms")
        # TODO index by organization and id?
        get_latest_by = "created"
        ordering = ('id',)

    def __str__(self):
        return 'FormType - %s %s' % (self.id, self.name)

    def get_markdown(self):
        return get_markdown(self.description, self.organization)

    def get_extra_field_names(self):
        fields = CustomField.objects.filter(ticket_form=self.id).values_list('field_name', flat=True)
        return [field for field in fields if is_extra_data(field)]

    def get_extra_fields_mapping(self):
        fields = CustomField.objects.filter(ticket_form=self.id).values_list('field_name', 'label')
        return {field_name: label for field_name, label in fields if is_extra_data(field_name)}

    def get_fields_mapping(self):
        fields = CustomField.objects.filter(ticket_form=self.id).values_list('field_name', 'label')
        return {field_name: label for field_name, label in fields if not is_extra_data(field_name)}

@receiver(post_save, sender=FormType)
def insert_presets_to_db(instance, created, **kwargs):
    from helpdesk.preset_form_fields import get_preset_fields
    # Generate the 13 different preset forms fields (with 19 fields each) and set them to a specific form type
    kwargs_for_CF = get_preset_fields(instance.id)
    # Only add preset fields if the object was just created
    if created:
        for kwarg_CF in kwargs_for_CF:
            new_CustomField = CustomField(**kwarg_CF)
            new_CustomField.save()


class Ticket(models.Model):
    """
    To allow a ticket to be entered as quickly as possible, only the
    bare minimum fields are required. These basically allow us to
    sort and manage the ticket. The user can always go back and
    enter more information later.

    A good example of this is when a customer is on the phone, and
    you want to give them a ticket ID as quickly as possible. You can
    enter some basic info, save the ticket, give the customer the ID
    and get off the phone, then add in further detail at a later time
    (once the customer is not on the line).

    Note that assigned_to is optional - unassigned tickets are displayed on
    the dashboard to prompt users to take ownership of them.
    """
    OPEN_STATUS = 1
    REOPENED_STATUS = 2
    RESOLVED_STATUS = 3
    CLOSED_STATUS = 4
    DUPLICATE_STATUS = 5
    REPLIED_STATUS = 6
    NEW_STATUS = 7

    STATUS_CHOICES = (
        (OPEN_STATUS, _('Open')),
        (REOPENED_STATUS, _('Reopened')),
        (RESOLVED_STATUS, _('Resolved')),
        (CLOSED_STATUS, _('Closed')),
        (DUPLICATE_STATUS, _('Duplicate')),
        (REPLIED_STATUS, _('Replied')),
        (NEW_STATUS, _('New')),
    )

    PRIORITY_CHOICES = (
        (1, _('1. Critical')),
        (2, _('2. High')),
        (3, _('3. Normal')),
        (4, _('4. Low')),
        (5, _('5. Very Low')),
    )

    # These fields are required by all tickets.
    # Labels are built-in for these fields, and not overwritten.
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True,
                                    related_name='assigned_to', verbose_name=_('Assigned to'))
    created = models.DateTimeField(_('Created'), auto_now_add=True,
                                   help_text=_('Date this ticket was first created'), )
    modified = models.DateTimeField(_('Modified'), auto_now=True,
                                    help_text=_('Date this ticket was most recently changed.'))
    status = models.IntegerField(_('Status'), choices=STATUS_CHOICES, default=NEW_STATUS)
    on_hold = models.BooleanField(_('On Hold'), blank=True, default=False,
                                  help_text=_('If a ticket is on hold, it will not automatically be escalated.'))
    resolution = models.TextField(_('Resolution'), blank=True, null=True,
                                  help_text=_('The resolution provided to the customer by our staff.'))
    last_escalation = models.DateTimeField(blank=True, null=True, editable=False,
                                           help_text=_('The date this ticket was last escalated - updated '
                                                       'automatically by management/commands/escalate_tickets.py.'))
    secret_key = models.CharField(_("Secret key needed for viewing/editing ticket by non-logged in users"),
                                  max_length=36, default=mk_secret)
    kbitem = models.ForeignKey("KBItem", blank=True, null=True, on_delete=models.SET_NULL,
                               verbose_name=_('Knowledge base item the user was viewing '
                                              'when they created this ticket.'))
    merged_to = models.ForeignKey('self', verbose_name=_('merged to'), related_name='merged_tickets',
                                  on_delete=models.SET_NULL, null=True, blank=True)

    # These fields are required by all tickets.
    # Labels for these fields are provided by CustomField by default.
    queue = models.ForeignKey(Queue, on_delete=models.PROTECT, verbose_name=_('Queue'))
    title = models.CharField(max_length=200, default="(no title)")
    description = models.TextField(blank=True, null=True)
    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=3, blank=3)
    due_date = models.DateTimeField(blank=True, null=True)
    submitter_email = models.EmailField(blank=True, null=True)

    # BEAM fieldsclass
    ticket_form = models.ForeignKey(FormType, on_delete=models.PROTECT)
    beam_property = models.ManyToManyField(Property, blank=True, related_name='helpdesk_ticket',  # TODO make plural
                                           verbose_name='BEAM Property')
    beam_taxlot = models.ManyToManyField(TaxLot, blank=True, related_name='helpdesk_ticket',  # TODO make plural
                                         verbose_name='BEAM Taxlot')  # TODO hide prop/taxlot from form fields

    # Contains extra fields, determined by items in CustomField
    extra_data = models.JSONField(default=dict, blank=True)

    # Default contact fields
    # Labels for these fields must be added in CustomField (not part of default)
    contact_name = models.CharField(max_length=200, blank=True, null=True)
    contact_email = models.CharField(max_length=200, blank=True, null=True)  # todo why is this a charfield and not an emailfield??
    building_name = models.CharField(max_length=200, blank=True, null=True)
    building_address = models.TextField(blank=True, null=True)
    pm_id = models.CharField(_("Portfolio Manager ID"), max_length=200, blank=True, null=True)
    building_id = models.CharField(_("Building ID"), max_length=200, blank=True, null=True)

    @property
    def time_spent(self):
        """Return back total time spent on the ticket. This is calculated value
        based on total sum from all FollowUps
        """
        total = datetime.timedelta(0)
        for val in self.followup_set.all():
            if val.time_spent:
                total = total + val.time_spent
        return total

    @property
    def time_spent_formatted(self):
        return format_time_spent(self.time_spent)

    def send_ticket_mail(self, roles, organization=None, dont_send_to=None,  **kwargs):
        """
        Send notifications to everyone interested in this ticket.

        The roles argument is a dictionary mapping from roles to (template, context) pairs.
        This method attempts to send a message to every possible role (see below), but the inner send method will
            ensure only the roles passed in will be sent a message.

        The following templates are default:
          - assigned (cc_user, owner)
          - closed (cc_user, cc_public, owner, submitter)
          - escalated (cc_user, cc_public, owner, submitter)
          - merged (none)
          - newticket (cc_user, cc_public, submitter)
          - resolved (cc_user, cc_public, owner, submitter)
          - updated (cc_user, cc_public, owner, submitter)

        The following roles exist:
          - 'submitter' (the default field contact_email is treated as the submitter)
          - 'queue_new'
          - 'queue_updated'
          - 'cc_users'
          - 'cc_public'
          - 'assigned_to'
          - 'extra'

        Here is an example roles dictionary:
        {
            'submitter': (template_name, context),
            'assigned_to': (template_name2, context),
        }

        **kwargs are passed to send_templated_mail defined in templated_email.py

        returns the set of email addresses the notification was delivered to.

        """
        logger.info('Sending emails from ticket model.')
        recipients = set()  # list of people already set to receive an email

        if dont_send_to is not None:
            recipients.update(dont_send_to)

        recipients.add(self.queue.email_address)

        def send(role, recipient):
            if recipient and recipient not in recipients and role in roles:
                template, context = roles[role]
                send_templated_mail(template, context, recipient, sender=self.queue.from_address,
                                    organization=organization, ticket_id=self.pk, **kwargs)
                recipients.add(recipient)

        # Attempts to send an email to every possible field.

        if self.submitter_email:
            send('submitter', self.submitter_email)
        if self.contact_email:
            send('submitter', self.contact_email)  # TODO add a new role/template for contact_email field?
        send('queue_updated', self.queue.updated_ticket_cc)
        send('queue_new', self.queue.new_ticket_cc)
        if self.assigned_to:
            send('assigned_to', self.assigned_to.email)

        # If queue allows CC'd users to be notified, send them email updates
        for cc in self.ticketcc_set.all():
            if cc.user and organization and is_helpdesk_staff(cc.user, organization.id):
                send('cc_users', cc.email_address)
            elif self.queue.enable_notifications_on_email_events:
                send('cc_public', cc.email_address)

        if self.queue.enable_notifications_on_email_events:
            # 'extra' fields are treated as cc_public.
            #  todo Add a method to pair specific extra fields with specific templates?
            email_fields = CustomField.objects.filter(
                ticket_form=self.ticket_form_id,
                data_type='email',
                notifications=True,
            ).values_list('field_name', flat=True)

            for field in email_fields:
                if field in self.extra_data and self.extra_data[field] is not None and self.extra_data[field] != '' and is_extra_data(field):
                    send('extra', self.extra_data[field])

        return recipients

    def _get_assigned_to(self):
        """ Custom property to allow us to easily print 'Unassigned' if a
        ticket has no owner, or the users name if it's assigned. If the user
        has a full name configured, we use that, otherwise their username. """
        if not self.assigned_to:
            return _('Unassigned')
        else:
            if self.assigned_to.get_full_name():
                return self.assigned_to.get_full_name()
            else:
                return self.assigned_to.get_username()
    get_assigned_to = property(_get_assigned_to)

    def _get_ticket(self):
        """ A user-friendly ticket ID, which is a combination of ticket ID
        and queue slug. This is generally used in e-mail subjects. """

        return u"[%s]" % self.ticket_for_url
    ticket = property(_get_ticket)

    def _get_ticket_for_url(self):
        """ A URL-friendly ticket ID, used in links. """
        return u"%s-%s" % (self.queue.slug, self.id)
    ticket_for_url = property(_get_ticket_for_url)

    def _get_priority_css_class(self):
        """
        Return the boostrap class corresponding to the priority.
        """
        if self.priority == 1:
            return "danger"
        elif self.priority == 2:
            return "warning"
        else:
            return "success"
    get_priority_css_class = property(_get_priority_css_class)

    def _get_priority(self):
        """
        Displays the priority of the ticket
        """
        return dict(self.PRIORITY_CHOICES)[self.priority]
    get_priority = property(_get_priority)

    def _get_status(self):
        """
        Displays the ticket status, with an "On Hold" message if needed.
        """
        held_msg = ''
        if self.on_hold:
            held_msg = _(' - On Hold')
        dep_msg = ''
        if not self.can_be_resolved:
            dep_msg = _(' - Open dependencies')
        return u'%s%s%s' % (self.get_status_display(), held_msg, dep_msg)
    get_status = property(_get_status)

    def _get_ticket_url(self):
        """
        Returns a publicly-viewable URL for this ticket, used when giving
        a URL to the submitter of a ticket.
        """
        from django.contrib.sites.models import Site
        from django.core.exceptions import ImproperlyConfigured
        from django.urls import reverse
        domain_id = None
        try:
            domain_id = self.ticket_form.organization.domain.id
            domain_name = self.ticket_form.organization.domain.netloc
        except Exception:
            domain_name = Site.objects.get_current().domain
        except ImproperlyConfigured:
            domain_name = Site(domain='configure-django-sites.com').domain
        if helpdesk_settings.HELPDESK_USE_HTTPS_IN_EMAIL_LINK:
            protocol = 'https'
        else:
            protocol = 'http'
        if get_helpdesk_count_by_domain(domain_id) == 1:
            return u"%s://%s%s?ticket=%s&email=%s&key=%s" % (
                protocol,
                domain_name,
                reverse('helpdesk:public_view'),
                self.ticket_for_url,
                self.submitter_email,
                self.secret_key
            )
        else:
            org_name = quote(self.queue.organization.name)
            return u"%s://%s%s?org=%s&ticket=%s&email=%s&key=%s" % (
                protocol,
                domain_name,
                reverse('helpdesk:public_view'),
                org_name,
                self.ticket_for_url,
                self.submitter_email,
                self.secret_key
            )
    ticket_url = property(_get_ticket_url)

    def _get_staff_url(self):
        """
        Returns a staff-only URL for this ticket, used when giving a URL to
        a staff member (in emails etc)
        """
        from django.contrib.sites.models import Site
        from django.core.exceptions import ImproperlyConfigured
        from django.urls import reverse
        try:
            domain_name = self.ticket_form.organization.domain.netloc
        except Exception:
            domain_name = Site.objects.get_current().domain
        except ImproperlyConfigured:
            domain_name = Site(domain='configure-django-sites.com').domain
        if helpdesk_settings.HELPDESK_USE_HTTPS_IN_EMAIL_LINK:
            protocol = 'https'
        else:
            protocol = 'http'
        return u"%s://%s%s" % (
            protocol,
            domain_name,
            reverse('helpdesk:view',
                    args=[self.id])
        )
    staff_url = property(_get_staff_url)

    def _can_be_resolved(self):
        """
        Returns a boolean.
        True = any dependencies are resolved
        False = There are non-resolved dependencies
        """
        OPEN_STATUSES = (Ticket.OPEN_STATUS, Ticket.REOPENED_STATUS, Ticket.REPLIED_STATUS, Ticket.NEW_STATUS)
        return TicketDependency.objects.filter(ticket=self).filter(
            depends_on__status__in=OPEN_STATUSES).count() == 0
    can_be_resolved = property(_can_be_resolved)

    def get_last_followup(self, level='staff'):
        """
        Return the datetime of the last followup, or last staff - public followup based on level parameter
        """
        if level == 'staff':
            followups = [f for f in self.followup_set.order_by('-date') if is_helpdesk_staff(f.user)]
        elif level == 'public':
            followups = [f for f in self.followup_set.order_by('-date') if not is_helpdesk_staff(f.user)]
        else:
            followups = [f for f in self.followup_set.order_by('-date')]

        if followups:
            return followups[0].date
        else:
            return None

    def get_submitter_userprofile(self):
        User = get_user_model()
        try:
            return User.objects.get(email=self.submitter_email)
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            return None

    class Meta:
        get_latest_by = "created"
        ordering = ('id',)
        verbose_name = _('Ticket')
        verbose_name_plural = _('Tickets')

    def __str__(self):
        return '%s %s' % (self.id, self.title)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('helpdesk:view', args=(self.id,))

    def save(self, query_fields=None, *args, **kwargs):
        if not self.id:
            # This is a new ticket as no ID yet exists.
            self.created = timezone.now()

        if not self.priority:
            self.priority = 3

        self.modified = timezone.now()

        super(Ticket, self).save(*args, **kwargs)

    @staticmethod
    def queue_and_id_from_query(query):
        # Apply the opposite logic here compared to self._get_ticket_for_url
        # Ensure that queues with '-' in them will work
        parts = query.split('-')
        queue = '-'.join(parts[0:-1])
        return queue, parts[-1]

    def get_markdown(self):
        return get_markdown(self.description, self.ticket_form.organization)

    @property
    def get_resolution_markdown(self):
        return get_markdown(self.resolution, self.ticket_form.organization)

    def add_email_to_ticketcc_if_not_in(self, email=None, user=None, ticketcc=None):
        """
        Check that given email/user_email/ticketcc_email is not already present on the ticket
        (submitter email, assigned to, or in ticket CCs) and add it to a new ticket CC,
        or move the given one

        :param str email:
        :param User user:
        :param TicketCC ticketcc:
        :rtype: TicketCC|None
        """
        if ticketcc:
            email = ticketcc.display
        elif user:
            if user.email:
                email = user.email
            else:
                # Ignore if user has no email address
                return
        elif not email:
            raise ValueError('You must provide at least one parameter to get the email from')

        # Prepare all emails already into the ticket
        ticket_emails = [x.display for x in self.ticketcc_set.all()]
        if self.submitter_email:
            ticket_emails.append(self.submitter_email)
        if self.assigned_to and self.assigned_to.email:
            ticket_emails.append(self.assigned_to.email)

        # Check that email is not already part of the ticket
        if email not in ticket_emails:
            if ticketcc:
                ticketcc.ticket = self
                ticketcc.save(update_fields=['ticket'])
            elif user:
                ticketcc = self.ticketcc_set.create(user=user, email=user.email)
            else:
                ticketcc = self.ticketcc_set.create(email=email)
            return ticketcc


class FollowUpManager(models.Manager):

    def private_followups(self):
        return self.filter(public=False)

    def public_followups(self):
        return self.filter(public=True)


class FollowUp(models.Model):
    """
    A FollowUp is a comment and/or change to a ticket. We keep a simple
    title, the comment entered by the user, and the new status of a ticket
    to enable easy flagging of details on the view-ticket page.

    The title is automatically generated at save-time, based on what action
    the user took.

    Tickets that aren't public are never shown to or e-mailed to the submitter,
    although all staff can see them.
    """

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        verbose_name=_('Ticket'),
    )

    date = models.DateTimeField(
        _('Date'),
        default=timezone.now
    )

    title = models.CharField(
        _('Title'),
        max_length=200,
        blank=True,
        null=True,
    )

    comment = models.TextField(
        _('Comment'),
        blank=True,
        null=True,
    )

    public = models.BooleanField(
        _('Public'),
        blank=True,
        default=False,
        help_text=_(
            'Public tickets are viewable by the submitter and all '
            'staff, but non-public tickets can only be seen by staff.'
        ),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_('User'),
    )

    new_status = models.IntegerField(
        _('New Status'),
        choices=Ticket.STATUS_CHOICES,
        blank=True,
        null=True,
        help_text=_('If the status was changed, what was it changed to?'),
    )

    message_id = models.CharField(
        _('E-Mail ID'),
        max_length=256,
        blank=True,
        null=True,
        help_text=_("The Message ID of the submitter's email."),
        editable=False,
    )

    objects = FollowUpManager()

    time_spent = models.DurationField(
        help_text=_("Time spent on this follow up"),
        blank=True, null=True
    )

    class Meta:
        ordering = ('date',)
        verbose_name = _('Follow-up')
        verbose_name_plural = _('Follow-ups')

    def __str__(self):
        return '%s' % self.title

    def get_absolute_url(self):
        return u"%s#followup%s" % (self.ticket.get_absolute_url(), self.id)

    def save(self, *args, **kwargs):
        t = self.ticket
        t.modified = timezone.now()
        t.save()
        super(FollowUp, self).save(*args, **kwargs)

    def get_markdown(self):
        return get_markdown(self.comment, self.ticket.ticket_form.organization)

    @property
    def time_spent_formatted(self):
        return format_time_spent(self.time_spent)


class TicketChange(models.Model):
    """
    For each FollowUp, any changes to the parent ticket (eg Title, Priority,
    etc) are tracked here for display purposes.
    """

    followup = models.ForeignKey(
        FollowUp,
        on_delete=models.CASCADE,
        verbose_name=_('Follow-up'),
    )

    field = models.CharField(
        _('Field'),
        max_length=100,
    )

    old_value = models.TextField(
        _('Old Value'),
        blank=True,
        null=True,
    )

    new_value = models.TextField(
        _('New Value'),
        blank=True,
        null=True,
    )

    def __str__(self):
        out = '%s ' % self.field
        if not self.new_value:
            out += ugettext('removed')
        elif not self.old_value:
            out += ugettext('set to %s') % self.new_value
        else:
            out += ugettext('changed from "%(old_value)s" to "%(new_value)s"') % {
                'old_value': self.old_value,
                'new_value': self.new_value
            }
        return out

    class Meta:
        verbose_name = _('Ticket change')
        verbose_name_plural = _('Ticket changes')


def attachment_path(instance, filename):
    """Just bridge"""
    return instance.attachment_path(filename)


class Attachment(models.Model):
    """
    Represents a file attached to a follow-up. This could come from an e-mail
    attachment, or it could be uploaded via the web interface.
    """

    file = models.FileField(
        _('File'),
        upload_to=attachment_path,
        max_length=1000,
    )

    filename = models.CharField(
        _('Filename'),
        blank=True,
        max_length=1000,
    )

    mime_type = models.CharField(
        _('MIME Type'),
        blank=True,
        max_length=255,
    )

    size = models.IntegerField(
        _('Size'),
        blank=True,
        help_text=_('Size of this file in bytes'),
    )

    def __str__(self):
        return '%s' % self.filename

    def save(self, *args, **kwargs):

        if not self.size:
            self.size = self.get_size()

        if not self.filename:
            self.filename = self.get_filename()

        if not self.mime_type:
            self.mime_type = \
                mimetypes.guess_type(self.filename, strict=False)[0] or \
                'application/octet-stream'

        return super(Attachment, self).save(*args, **kwargs)

    def get_filename(self):
        return str(self.file)

    def get_size(self):
        return self.file.file.size

    def attachment_path(self, filename):
        """Provide a file path that will help prevent files being overwritten, by
        putting attachments in a folder off attachments for ticket/followup_id/.
        """
        assert NotImplementedError(
            "This method is to be implemented by Attachment classes"
        )

    class Meta:
        ordering = ('filename',)
        verbose_name = _('Attachment')
        verbose_name_plural = _('Attachments')
        abstract = True


class FollowUpAttachment(Attachment):

    followup = models.ForeignKey(
        FollowUp,
        on_delete=models.CASCADE,
        verbose_name=_('Follow-up'),
    )

    def attachment_path(self, filename):

        os.umask(0)
        path = 'helpdesk/attachments/{ticket_for_url}-{secret_key}/{id_}'.format(
            ticket_for_url=self.followup.ticket.ticket_for_url,
            secret_key=self.followup.ticket.secret_key,
            id_=self.followup.id)
        att_path = os.path.join(settings.MEDIA_ROOT, path)
        if settings.DEFAULT_FILE_STORAGE == "django.core.files.storage.FileSystemStorage":
            if not os.path.exists(att_path):
                os.makedirs(att_path, 0o777)
        return os.path.join(path, filename)


class KBIAttachment(Attachment):

    kbitem = models.ForeignKey(
        "KBItem",
        on_delete=models.CASCADE,
        verbose_name=_('Knowledgebase Article'),
    )

    def attachment_path(self, filename):

        os.umask(0)
        path = 'helpdesk/attachments/kb/{category}/{kbi}'.format(
            category=self.kbitem.category,
            kbi=self.kbitem.id)
        att_path = os.path.join(settings.MEDIA_ROOT, path)
        if settings.DEFAULT_FILE_STORAGE == "django.core.files.storage.FileSystemStorage":
            if not os.path.exists(att_path):
                os.makedirs(att_path, 0o777)
        return os.path.join(path, filename)


class PreSetReply(models.Model):
    """
    We can allow the admin to define a number of pre-set replies, used to
    simplify the sending of updates and resolutions. These are basically Django
    templates with a limited context - however if you wanted to get crafy it would
    be easy to write a reply that displays ALL updates in hierarchical order etc
    with use of for loops over {{ ticket.followup_set.all }} and friends.

    When replying to a ticket, the user can select any reply set for the current
    queue, and the body text is fetched via AJAX.
    """
    class Meta:
        ordering = ('name',)
        verbose_name = _('Pre-set reply')
        verbose_name_plural = _('Pre-set replies')

    queues = models.ManyToManyField(
        Queue,
        blank=True,
        help_text=_('Leave blank to allow this reply to be used for all '
                    'queues, or select those queues you wish to limit this reply to.'),
    )

    name = models.CharField(
        _('Name'),
        max_length=100,
        help_text=_('Only used to assist users with selecting a reply - not '
                    'shown to the user.'),
    )

    body = models.TextField(
        _('Body'),
        help_text=_('Context available: {{ ticket }} - ticket object (eg '
                    '{{ ticket.title }}); {{ queue }} - The queue; and {{ user }} '
                    '- the current user.'),
    )

    def __str__(self):
        return '%s' % self.name


class EscalationExclusion(models.Model):
    """
    An 'EscalationExclusion' lets us define a date on which escalation should
    not happen, for example a weekend or public holiday.

    You may also have a queue that is only used on one day per week.

    To create these on a regular basis, check out the README file for an
    example cronjob that runs 'create_escalation_exclusions.py'.
    """

    queues = models.ManyToManyField(
        Queue,
        blank=True,
        help_text=_('Leave blank for this exclusion to be applied to all queues, '
                    'or select those queues you wish to exclude with this entry.'),
    )

    name = models.CharField(
        _('Name'),
        max_length=100,
    )

    date = models.DateField(
        _('Date'),
        help_text=_('Date on which escalation should not happen'),
    )

    def __str__(self):
        return '%s' % self.name

    class Meta:
        verbose_name = _('Escalation exclusion')
        verbose_name_plural = _('Escalation exclusions')


class EmailTemplate(models.Model):
    """
    Since these are more likely to be changed than other templates, we store
    them in the database.

    This means that an admin can change email templates without having to have
    access to the filesystem.
    """

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
    )

    template_name = models.CharField(
        _('Template Name'),
        max_length=100,
    )

    subject = models.CharField(
        _('Subject'),
        max_length=100,
        help_text=_('This will be prefixed with "[ticket.ticket] ticket.title"'
                    '. We recommend something simple such as "(Updated") or "(Closed)"'
                    ' - the same context is available as in plain_text, below.'),
    )

    heading = models.CharField(
        _('Heading'),
        max_length=100,
        help_text=_('In HTML e-mails, this will be the heading at the top of '
                    'the email - the same context is available as in plain_text, '
                    'below.'),
    )

    plain_text = models.TextField(
        _('Plain Text'),
        help_text=_('The context available to you includes {{ ticket }}, '
                    '{{ queue }}, and depending on the time of the call: '
                    '{{ resolution }} or {{ comment }}.'),
    )

    html = models.TextField(
        _('HTML'),
        help_text=_('The same context is available here as in plain_text, above.'),
    )

    locale = models.CharField(
        _('Locale'),
        max_length=10,
        blank=True,
        null=True,
        help_text=_('Locale of this template.'),
    )

    def __str__(self):
        return '%s' % self.template_name

    class Meta:
        ordering = ('template_name', 'locale')
        verbose_name = _('e-mail template')
        verbose_name_plural = _('e-mail templates')


class KBCategory(models.Model):
    """
    Lets help users help themselves: the Knowledge Base is a categorised
    listing of questions & answers.
    """

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
    )

    name = models.CharField(
        _('Name of the category'),
        max_length=100,
    )

    title = models.CharField(
        _('Title on knowledgebase page'),
        max_length=100,
    )

    slug = models.SlugField(
        _('Slug'),
        unique=True,
    )

    preview_description = models.TextField(
        _('Preview description on knowledgebase page'),
        blank=True,
        null=True,
    )

    description = models.TextField(
        _('Full description on knowledgebase category page'),
    )

    queue = models.ForeignKey(
        Queue,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        verbose_name=_('Default queue when creating a ticket after viewing this category.'),
    )

    forms = models.ManyToManyField(
        FormType,
        blank=True,
        help_text='Forms listed on the page, that the user can submit after reading any article in this category. (Only public forms will be displayed to public users, regardless of whether or not they are unlisted.)',
    )

    public = models.BooleanField(
        default=True,
        verbose_name=_("Is KBCategory publicly visible?")
    )

    def __str__(self):
        return '%s: %s (%s)' % (self.organization.name, self.name, self.pk)

    class Meta:
        ordering = ('title',)
        verbose_name = _('Knowledgebase category')
        verbose_name_plural = _('Knowledgebase categories')

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('helpdesk:kb_category', kwargs={'slug': self.slug})

    def get_description_markdown(self):
        return get_markdown(self.description, self.organization)

    def get_preview_markdown(self):
        return get_markdown(self.preview_description, self.organization)


class KBItem(models.Model):
    """
    An item within the knowledgebase. Very straightforward question/answer
    style system.
    """
    voted_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='votes',
    )
    downvoted_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='downvotes',
    )
    category = models.ForeignKey(
        KBCategory,
        on_delete=models.CASCADE,
        verbose_name=_('Category'),
    )

    title = models.CharField(
        _('Title'),
        max_length=100,
    )

    question = models.TextField(
        _('Question'),
    )

    answer = models.TextField(
        _('Answer'),
        help_text=_(markdown_allowed() + '<br/><br/>'
                    "<b>Multple newlines:</b><br/>Markdown doesn't recognize multiple blank lines. "
                    "To display one, write &amp;nbsp; on a blank line.<br/><br/>"
                    "<b>Table formatting:</b><br/>"
                    "<pre>First Header  | Second Header</br>"
                    '------------- | -------------</br>'
                    'Content Cell  | Content Cell</br>'
                    'Content Cell  | Content Cell</pre></br>'
                    '<b>Collapsing section:</b><br/> '
                    'Add !~! on a line following the section title, followed by a blank line. '
                    'Add ~!~ on a line following the section body, followed by another blank line. <br/>'
                    'The body may have multiple lines of text, but no blank lines.<br/><br/>'
                    'Example:<br/><pre>This text comes before the section.<br/><br/>'
                    'Title of Subsection<br/>!~!<br/><br/>'
                    '&amp;nbsp;<br/>Body of subsection.<br/>&amp;nbsp;<br/>I can add many lines of text to this. '
                    "It will all be included in the section.<br/>~!~<br/><br/>"
                    "&amp;nbsp;<br/>This, however, won't be included in the collapsing section.</pre>"),
    )

    votes = models.IntegerField(
        _('Votes'),
        help_text=_('Total number of votes cast for this item'),
        default=0,
    )

    recommendations = models.IntegerField(
        _('Positive Votes'),
        help_text=_('Number of votes for this item which were POSITIVE.'),
        default=0,
    )

    last_updated = models.DateTimeField(
        _('Last Updated'),
        help_text=_('The date on which this question was most recently changed.'),
        blank=True,
    )

    team = models.ForeignKey(
        pinax.teams.models.Team,
        on_delete=models.CASCADE,
        verbose_name=_('Team'),
        blank=True,
        null=True,
    )

    order = models.PositiveIntegerField(
        _('Order'),
        blank=True,
        null=True,
    )

    enabled = models.BooleanField(
        _('Enabled to display to users'),
        default=True,
    )

    def save(self, *args, **kwargs):
        if not self.last_updated:
            self.last_updated = timezone.now()
        return super(KBItem, self).save(*args, **kwargs)

    def _score(self):
        """ Return a score out of 10 or Unrated if no votes """
        if self.votes > 0:
            return (self.recommendations / self.votes) * 10
        else:
            return _('Unrated')
    score = property(_score)

    def __str__(self):
        return '%s: %s' % (self.category.title, self.title)

    class Meta:
        ordering = ('order', 'title',)
        verbose_name = _('Knowledgebase article')
        verbose_name_plural = _('Knowledgebase articles')

    def get_absolute_url(self):
        from django.urls import reverse
        return str(reverse('helpdesk:kb_category', args=(self.category.slug,))) + str(self.pk)

    def query_url(self):
        from django.urls import reverse
        return str(reverse('helpdesk:list')) + "?kbitem=" + str(self.pk)

    def num_open_tickets(self):
        return Ticket.objects.filter(kbitem=self, status__in=(1, 2, 6)).count()

    def unassigned_tickets(self):
        return Ticket.objects.filter(kbitem=self, status__in=(1, 2, 6), assigned_to__isnull=True)

    def get_markdown(self):
        """
        Converts KB article text from Markdown to HTML.
        This method searches for two new patterns, !~! and ~!~, to replace with HTML tags for a collapsing
        subsection.

        - !~! and ~!~ both must be on their own line
        - They must directly follow a block of text (blank lines divide a block)
        - They must be followed by a blank line

        Example:
            Title of Subsection
            !~!

            Body of subsection.
            I can add many lines of text to this.
            It will all be included in the section.
            ~!~

            This, however, won't be included in the collapsing section.
        """

        class MarkdownNumbers(object):
            def __init__(self, start=1, pattern=''):
                self.count = start - 1
                self.pattern = pattern

            def __call__(self, match):
                self.count += 1
                return self.pattern.format(self.count)

        title_pattern = r'!~!'
        body_pattern = r'~!~'

        title = "{{: .card .btn .btn-link style='text-align: left;' " \
                "data-toggle='collapse' data-target='#collapse{0}' role='region' " \
                "aria-expanded='false' aria-controls='collapse{0}' .card-header #header{0} .h5 .mb-0 }}"
        body = "{{ #collapse{0} .collapse role='region' aria-labelledby='header{0}' data-parent='#header{0}' " \
               "style='padding-top:0;padding-bottom:0;margin:0;' .card-body }}"

        new_answer, title_count = re.subn(title_pattern, MarkdownNumbers(start=1, pattern=title), self.answer)
        new_answer, body_count = re.subn(body_pattern, MarkdownNumbers(start=1, pattern=body), new_answer)
        if title_count != 0 and title_count == body_count:
            return get_markdown(new_answer, self.category.organization, kb=True)
        return get_markdown(self.answer, self.category.organization)


class SavedSearch(models.Model):
    """
    Allow a user to save a ticket search, eg their filtering and sorting
    options, and optionally share it with other users. This lets people
    easily create a set of commonly-used filters, such as:
        * My tickets waiting on me
        * My tickets waiting on submitter
        * My tickets in 'Priority Support' queue with priority of 1
        * All tickets containing the word 'billing'.
         etc...
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name=_('User'),
    )

    title = models.CharField(
        _('Query Name'),
        max_length=100,
        help_text=_('User-provided name for this query'),
    )

    shared = models.BooleanField(
        _('Shared With Other Users?'),
        blank=True,
        default=False,
        help_text=_('Should other users see this query?'),
    )

    query = models.TextField(
        _('Search Query'),
        help_text=_('Pickled query object. Be wary changing this.'),
    )

    opted_out_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        help_text=_('Users who have opted out of seeing this query'),
        related_name='opted_out'
    )

    def __str__(self):
        if self.shared:
            return '%s (*)' % self.title
        else:
            return '%s' % self.title

    class Meta:
        verbose_name = _('Saved search')
        verbose_name_plural = _('Saved searches')

    @property
    def get_visible_cols(self):
        """
        Return the visible cols stored in the query64
        """
        from helpdesk.query import query_from_base64
        import json
        query_unencoded = query_from_base64(self.query)
        if 'visible_cols' in query_unencoded:
            visible_cols = query_unencoded.get('visible_cols', [])
        else:
            # For queries made before the change, have them include be default
            visible_cols = ['id', 'ticket', 'status', 'created', 'assigned_to', 'submitter', 'kbitem']
        return json.dumps(visible_cols)


def get_default_setting(setting):
    from helpdesk.settings import DEFAULT_USER_SETTINGS
    return DEFAULT_USER_SETTINGS[setting]


def login_view_ticketlist_default():
    return get_default_setting('login_view_ticketlist')


def email_on_ticket_change_default():
    return get_default_setting('email_on_ticket_change')


def email_on_ticket_assign_default():
    return get_default_setting('email_on_ticket_assign')


def tickets_per_page_default():
    return get_default_setting('tickets_per_page')


def use_email_as_submitter_default():
    return get_default_setting('use_email_as_submitter')


class UserSettings(models.Model):
    """
    A bunch of user-specific settings that we want to be able to define, such
    as notification preferences and other things that should probably be
    configurable.
    """
    PAGE_SIZES = ((10, '10'), (25, '25'), (50, '50'), (100, '100'))

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="usersettings_helpdesk")

    settings_pickled = models.TextField(
        _('DEPRECATED! Settings Dictionary DEPRECATED!'),
        help_text=_('DEPRECATED! This is a base64-encoded representation of a pickled Python dictionary. '
                    'Do not change this field via the admin.'),
        blank=True,
        null=True,
    )

    login_view_ticketlist = models.BooleanField(
        verbose_name=_('Show Ticket List on Login?'),
        help_text=_('Display the ticket list upon login? Otherwise, the dashboard is shown.'),
        default=login_view_ticketlist_default,
    )

    email_on_ticket_change = models.BooleanField(
        verbose_name=_('E-mail me on ticket change?'),
        help_text=_(
            'If you\'re the ticket owner and the ticket is changed via the web by somebody else, '
            'do you want to receive an e-mail?'
        ),
        default=email_on_ticket_change_default,
    )

    email_on_ticket_assign = models.BooleanField(
        verbose_name=_('E-mail me when assigned a ticket?'),
        help_text=_('If you are assigned a ticket via the web, do you want to receive an e-mail?'),
        default=email_on_ticket_assign_default,
    )

    tickets_per_page = models.IntegerField(
        verbose_name=_('Number of tickets to show per page'),
        help_text=_('How many tickets do you want to see on the Ticket List page?'),
        default=tickets_per_page_default,
        choices=PAGE_SIZES,
    )

    use_email_as_submitter = models.BooleanField(
        verbose_name=_('Use my e-mail address when submitting tickets?'),
        help_text=_('When you submit a ticket, do you want to automatically '
                    'use your e-mail address as the submitter address? You '
                    'can type a different e-mail address when entering the '
                    'ticket if needed, this option only changes the default.'),
        default=use_email_as_submitter_default,
    )

    def __str__(self):
        return 'Preferences for %s' % self.user

    class Meta:
        verbose_name = _('User Setting')
        verbose_name_plural = _('User Settings')


def create_usersettings(sender, instance, created, **kwargs):
    """
    Helper function to create UserSettings instances as
    required, eg when we first create the UserSettings database
    table via 'syncdb' or when we save a new user.

    If we end up with users with no UserSettings, then we get horrible
    'DoesNotExist: UserSettings matching query does not exist.' errors.
    """
    if created:
        UserSettings.objects.create(user=instance)


models.signals.post_save.connect(create_usersettings, sender=settings.AUTH_USER_MODEL)


class IgnoreEmail(models.Model):
    """
    This model lets us easily ignore e-mails from certain senders when
    processing IMAP and POP3 mailboxes, eg mails from postmaster or from
    known trouble-makers.
    """
    class Meta:
        verbose_name = _('Ignored e-mail address')
        verbose_name_plural = _('Ignored e-mail addresses')

    importers = models.ManyToManyField(
        'seed.EmailImporter',
        blank=True,
        help_text=_('Leave blank for this e-mail to be ignored on all importer emails, '
                    'or select those importers you wish to ignore this e-mail for.'),
    )

    name = models.CharField(
        _('Name'),
        max_length=100,
    )

    date = models.DateField(
        _('Date'),
        help_text=_('Date on which this e-mail address was added'),
        blank=True,
        editable=False
    )

    email_address = models.CharField(
        _('E-Mail Address'),
        max_length=150,
        help_text=_('Enter a full e-mail address, or portions with '
                    'wildcards, eg *@domain.com or postmaster@*.'),
    )

    keep_in_mailbox = models.BooleanField(
        _('Save Emails in Mailbox?'),
        blank=True,
        default=False,
        help_text=_('Do you want to save emails from this address in the mailbox? '
                    'If this is unticked, emails from this address will be deleted.'),
    )

    def __str__(self):
        return '%s <%s>' % (self.name, self.email_address)

    def save(self, *args, **kwargs):
        if not self.date:
            self.date = timezone.now()
        return super(IgnoreEmail, self).save(*args, **kwargs)

    def importer_list(self):
        """Return a list of the importers this IgnoreEmail applies to.
        If this IgnoreEmail applies to ALL importers, return '*'.
        """
        importers = self.importers.all().order_by('email_address')
        if len(importers) == 0:
            return '*'
        else:
            return ', '.join([str(i) for i in importers])

    def test(self, email):
        """
        Possible situations:
            1. Username & Domain both match
            2. Username is wildcard, domain matches
            3. Username matches, domain is wildcard
            4. username & domain are both wildcards
            5. Other (no match)

            1-4 return True, 5 returns False.
        """

        # matches case before comparing
        self_email = self.email_address.lower()
        compare_email = email.lower()

        self_parts = self_email.split("@")
        compare_parts = compare_email.split("@")

        if self_email == compare_email or \
                self_parts[0] == "*" and self_parts[1] == compare_parts[1] or \
                self_parts[1] == "*" and self_parts[0] == compare_parts[0] or \
                self_parts[0] == "*" and self_parts[1] == "*":
            return True
        else:
            return False


class TicketCC(models.Model):
    """
    Often, there are people who wish to follow a ticket who aren't the
    person who originally submitted it. This model provides a way for those
    people to follow a ticket.

    In this circumstance, a 'person' could be either an e-mail address or
    an existing system user.
    """
    VIEW_WARNING = 'You do not have permission to view this ticket. Please contact the submitter, %s, to change your ' \
                   'CC settings for this ticket.'

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        verbose_name=_('Ticket'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        help_text=_('This user will receive staff updates from both private and public comments.'),
        verbose_name=_('User'),
    )

    email = models.EmailField(
        _('E-Mail Address'),
        blank=True,
        null=True,
        help_text=_('This address will not receive updates from private comments.'),
    )

    can_view = models.BooleanField(
        _('View Ticket'),
        blank=True,
        default=False,
        help_text=_('Can this person login to view the ticket details?'),
    )

    can_update = models.BooleanField(
        _('Update Ticket'),
        blank=True,
        default=False,
        help_text=_('Can this person login and update the ticket?'),
    )

    def _email_address(self):
        if self.user and self.user.email is not None:
            return self.user.email
        else:
            return self.email
    email_address = property(_email_address)

    def _display(self):
        if self.user:
            return self.user
        else:
            return self.email
    display = property(_display)

    def __str__(self):
        return '%s for %s' % (self.display, self.ticket.title)

    def clean(self):
        if self.user and not self.user.email:
            raise ValidationError('User has no email address')


class CustomFieldManager(models.Manager):

    def get_queryset(self):
        return super(CustomFieldManager, self).get_queryset().order_by('form_ordering')


class CustomField(models.Model):
    """
    Definitions for custom fields that are glued onto each ticket.
    """

    # Must be unique with the ticket_form.
    # TODO also can't be a field whose labels are built in
    field_name = models.SlugField(
        _('Field Name'),
        help_text=_('As used in the database and behind the scenes. '
                    'Must consist of only lowercase letters with no punctuation.'),
        unique=False,
    )

    label = models.CharField(
        _('Label'),
        max_length=200,
        help_text=_('The display label for this field'),
        blank=True,
        null=True
    )

    help_text = models.TextField(
        _('Help Text'),
        help_text=_('Shown to the user when editing the ticket'),
        blank=True,
        null=True
    )

    DATA_TYPE_CHOICES = (
        ('varchar', _('Character (single line)')),
        ('text', _('Text (multi-line)')),
        ('integer', _('Integer')),
        ('decimal', _('Decimal')),
        ('list', _('List')),
        ('boolean', _('Boolean (checkbox yes/no)')),
        ('date', _('Date')),
        ('time', _('Time')),
        ('datetime', _('Date & Time')),
        ('email', _('E-Mail Address')),
        ('url', _('URL')),
        ('ipaddress', _('IP Address')),
        ('slug', _('Slug')),
        ('attachment', _('Attachment')),
    )

    data_type = models.CharField(
        _('Data Type'),
        max_length=100,
        help_text=_('Allows you to restrict the data entered into this field'),
        choices=DATA_TYPE_CHOICES,
        blank=True,
        null=True
    )

    max_length = models.IntegerField(
        _('Maximum Length (characters)'),
        blank=True,
        null=True,
    )

    decimal_places = models.IntegerField(
        _('Decimal Places'),
        help_text=_('Only used for decimal fields'),
        blank=True,
        null=True,
    )

    notifications = models.BooleanField(
        _('Use this email for notifications?'),
        default=False,
        help_text=_('Only for Email Address: adds this email to the list of addresses that receive notifications of '
                    'ticket updates. By default, only submitter_email and contact_email receive notifications.'),
    )

    empty_selection_list = models.BooleanField(
        _('Add empty first choice to List?'),
        default=False,
        help_text=_('Only for List: adds an empty first entry to the choices list, '
                    'which enforces that the user makes an active choice.'),
    )

    list_values = models.TextField(
        _('List Values'),
        help_text=_('For list fields only. Enter one option per line.'),
        blank=True,
        null=True,
    )

    # TODO employ ordering
    form_ordering = models.IntegerField(
        _('Form Ordering'),
        help_text=_('Order of fields when submitting a form. '
                    'Lower numbers are displayed first; higher numbers are listed later'),
        blank=True,
        null=True,
    )

    # TODO remove this ordering
    view_ordering = models.IntegerField(
        _('View Ordering'),
        help_text=_('Order of fields when viewing a ticket. '
                    'Lower numbers are displayed first; higher numbers are listed later'),
        blank=True,
        null=True,
    )

    def _choices_as_array(self):
        valuebuffer = StringIO(self.list_values)
        choices = [[item.strip(), item.strip()] for item in valuebuffer.readlines()]
        valuebuffer.close()
        return choices
    choices_as_array = property(_choices_as_array)

    required = models.BooleanField(_('Required?'), help_text=_('Does the user have to enter a value for this field?'),
                                   default=False)
    staff = models.BooleanField(_('Show on staff form?'), default=True)
    public = models.BooleanField(_('Show on public form?'), default=True)

    ticket_form = models.ForeignKey(FormType, on_delete=models.CASCADE)
    column = models.ForeignKey(Column, blank=True, null=True, on_delete=models.SET_NULL, related_name='helpdesk_fields', verbose_name=_('Associated BEAM column'))

    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    objects = CustomFieldManager()  # for ordering objects based on "ordering"

    def __str__(self):
        return 'Custom Field - %s %s' % (self.pk, self.field_name)

    class Meta:
        verbose_name = _("Form field")
        verbose_name_plural = _("Form fields")
        unique_together = ('field_name', 'ticket_form')
        ordering = ['ticket_form', 'form_ordering']
        # Django 3.2 option
        # constraints = [models.UniqueConstraint(fields=['field_name', 'ticket_form'], name='unique_form_field')]

    def get_markdown(self):
        return get_markdown(self.help_text, self.ticket_form.organization)


class TicketCustomFieldValue(models.Model):
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        verbose_name=_('Ticket'),
    )

    field = models.ForeignKey(
        CustomField,
        on_delete=models.CASCADE,
        verbose_name=_('Field'),
    )

    value = models.TextField(blank=True, null=True)

    def __str__(self):
        return '%s / %s' % (self.ticket, self.field)

    class Meta:
        unique_together = (('ticket', 'field'),)
        verbose_name = _('Ticket custom field value')
        verbose_name_plural = _('Ticket custom field values')


class TicketDependency(models.Model):
    """
    The ticket identified by `ticket` cannot be resolved until the ticket in `depends_on` has been resolved.
    To help enforce this, a helper function `can_be_resolved` on each Ticket instance checks that
    these have all been resolved.
    """
    class Meta:
        unique_together = (('ticket', 'depends_on'),)
        verbose_name = _('Ticket dependency')
        verbose_name_plural = _('Ticket dependencies')

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        verbose_name=_('Ticket'),
        related_name='ticketdependency',
    )

    depends_on = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        verbose_name=_('Depends On Ticket'),
        related_name='depends_on',
    )

    def __str__(self):
        return '%s / %s' % (self.ticket, self.depends_on)
