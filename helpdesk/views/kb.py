"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

views/kb.py - Public-facing knowledgebase views. The knowledgebase is a
              simple categorised question/answer system to show common
              resolutions to common problems.
"""

from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404

from helpdesk import settings as helpdesk_settings
from helpdesk.models import KBCategory, KBItem


def index(request):
    category_list = KBCategory.objects.all()
    # TODO: It'd be great to have a list of most popular items here.
    return render(request, 'helpdesk/kb_index.html', {
        'kb_categories': category_list,
        'helpdesk_settings': helpdesk_settings,
    })


def category(request, slug):
    category = get_object_or_404(KBCategory, slug__iexact=slug)
    items = category.kbitem_set.all()
    return render(request, 'helpdesk/kb_category.html', {
        'category': category,
        'items': items,
        'helpdesk_settings': helpdesk_settings,
    })


def item(request, item):
    item = get_object_or_404(KBItem, pk=item)
    return render(request, 'helpdesk/kb_item.html', {
        'item': item,
        'helpdesk_settings': helpdesk_settings,
    })


def vote(request, item):
    item = get_object_or_404(KBItem, pk=item)
    vote = request.GET.get('vote', None)
    if vote in ('up', 'down'):
        item.votes += 1
        if vote == 'up':
            item.recommendations += 1
        item.save()

    return HttpResponseRedirect(item.get_absolute_url())
