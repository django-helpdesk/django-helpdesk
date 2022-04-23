"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

views/feeds.py - A handful of staff-only RSS feeds to provide ticket details
                 to feed readers or similar software.
"""

from django.contrib.auth import get_user_model
from django.contrib.syndication.views import Feed
from django.urls import reverse
from django.db.models import Q
from django.utils.translation import gettext as _
from django.shortcuts import get_object_or_404

from helpdesk.models import Ticket, FollowUp, Queue

User = get_user_model()


class OpenTicketsByUser(Feed):
    title_template = 'helpdesk/rss/ticket_title.html'
    description_template = 'helpdesk/rss/ticket_description.html'

    def get_object(self, request, user_name, queue_slug=None):
        user = get_object_or_404(User, username=user_name)
        if queue_slug:
            queue = get_object_or_404(Queue, slug=queue_slug)
        else:
            queue = None

        return {'user': user, 'queue': queue}

    def title(self, obj):
        if obj['queue']:
            return _("Helpdesk: Open Tickets in queue %(queue)s for %(username)s") % {
                'queue': obj['queue'].title,
                'username': obj['user'].get_username(),
            }
        else:
            return _("Helpdesk: Open Tickets for %(username)s") % {
                'username': obj['user'].get_username(),
            }

    def description(self, obj):
        if obj['queue']:
            return _("Open and Reopened Tickets in queue %(queue)s for %(username)s") % {
                'queue': obj['queue'].title,
                'username': obj['user'].get_username(),
            }
        else:
            return _("Open and Reopened Tickets for %(username)s") % {
                'username': obj['user'].get_username(),
            }

    def link(self, obj):
        if obj['queue']:
            return u'%s?assigned_to=%s&queue=%s' % (
                reverse('helpdesk:list'),
                obj['user'].id,
                obj['queue'].id,
            )
        else:
            return u'%s?assigned_to=%s' % (
                reverse('helpdesk:list'),
                obj['user'].id,
            )

    def items(self, obj):
        if obj['queue']:
            return Ticket.objects.filter(
                assigned_to=obj['user']
            ).filter(
                queue=obj['queue']
            ).filter(
                Q(status=Ticket.OPEN_STATUS) | Q(status=Ticket.REOPENED_STATUS)
            )
        else:
            return Ticket.objects.filter(
                assigned_to=obj['user']
            ).filter(
                Q(status=Ticket.OPEN_STATUS) | Q(status=Ticket.REOPENED_STATUS)
            )

    def item_pubdate(self, item):
        return item.created

    def item_author_name(self, item):
        if item.assigned_to:
            return item.assigned_to.get_username()
        else:
            return _('Unassigned')


class UnassignedTickets(Feed):
    title_template = 'helpdesk/rss/ticket_title.html'
    description_template = 'helpdesk/rss/ticket_description.html'

    title = _('Helpdesk: Unassigned Tickets')
    description = _('Unassigned Open and Reopened tickets')
    link = ''  # '%s?assigned_to=' % reverse('helpdesk:list')

    def items(self, obj):
        return Ticket.objects.filter(
            assigned_to__isnull=True
        ).filter(
            Q(status=Ticket.OPEN_STATUS) | Q(status=Ticket.REOPENED_STATUS)
        )

    def item_pubdate(self, item):
        return item.created

    def item_author_name(self, item):
        if item.assigned_to:
            return item.assigned_to.get_username()
        else:
            return _('Unassigned')


class RecentFollowUps(Feed):
    title_template = 'helpdesk/rss/recent_activity_title.html'
    description_template = 'helpdesk/rss/recent_activity_description.html'

    title = _('Helpdesk: Recent Followups')
    description = _('Recent FollowUps, such as e-mail replies, comments, attachments and resolutions')
    link = '/tickets/'  # reverse('helpdesk:list')

    def items(self):
        return FollowUp.objects.order_by('-date')[:20]


class OpenTicketsByQueue(Feed):
    title_template = 'helpdesk/rss/ticket_title.html'
    description_template = 'helpdesk/rss/ticket_description.html'

    def get_object(self, request, queue_slug):
        return get_object_or_404(Queue, slug=queue_slug)

    def title(self, obj):
        return _('Helpdesk: Open Tickets in queue %(queue)s') % {
            'queue': obj.title,
        }

    def description(self, obj):
        return _('Open and Reopened Tickets in queue %(queue)s') % {
            'queue': obj.title,
        }

    def link(self, obj):
        return '%s?queue=%s' % (
            reverse('helpdesk:list'),
            obj.id,
        )

    def items(self, obj):
        return Ticket.objects.filter(
            queue=obj
        ).filter(
            Q(status=Ticket.OPEN_STATUS) | Q(status=Ticket.REOPENED_STATUS)
        )

    def item_pubdate(self, item):
        return item.created

    def item_author_name(self, item):
        if item.assigned_to:
            return item.assigned_to.get_username()
        else:
            return _('Unassigned')
