"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

views/kb.py - Public-facing knowledgebase views. The knowledgebase is a
              simple categorised question/answer system to show common
              resolutions to common problems.
"""

from django.http import HttpResponseRedirect, Http404
from django.shortcuts import render, get_object_or_404
from django.views.decorators.clickjacking import xframe_options_exempt
from django.urls import reverse

from helpdesk import settings as helpdesk_settings
from helpdesk import user
from helpdesk.models import KBCategory, KBItem
from helpdesk.decorators import is_helpdesk_staff


def index(request):
    huser = user.huser_from_request(request)
    # TODO: It'd be great to have a list of most popular items here.
    return render(request, 'helpdesk/kb_index.html', {
        'kb_categories': huser.get_allowed_kb_categories(),
        'helpdesk_settings': helpdesk_settings,
    })

def category(request, slug, iframe=False):
    category = get_object_or_404(KBCategory, slug__iexact=slug)
    if not user.huser_from_request(request).can_access_kbcategory(category):
        # TODO remove category slug and article slug from url
        return render(request, 'helpdesk/kb_index.html', {
            'kb_categories': user.huser_from_request(request).get_allowed_kb_categories(),
            'helpdesk_settings': helpdesk_settings,
        })
    if is_helpdesk_staff(request.user):
        items = category.kbitem_set.all()
    else:
        items = category.kbitem_set.filter(enabled=True)
    qparams = request.GET.copy()
    try:
        del qparams['kbitem']
    except KeyError:
        pass
    template = 'helpdesk/kb_category.html'
    if iframe:
        template = 'helpdesk/kb_category_iframe.html'
    return render(request, template, {
        'category': category,
        'items': items,
        'query_param_string': qparams.urlencode(),
        'helpdesk_settings': helpdesk_settings,
        'iframe': iframe,
    })

def article(request, slug, pk, iframe=False):
    item = get_object_or_404(KBItem, pk=pk)
    if not user.huser_from_request(request).can_access_kbarticle(item):
        # TODO remove category slug and article slug from url
        return render(request, 'helpdesk/kb_index.html', {
            'kb_categories': user.huser_from_request(request).get_allowed_kb_categories(),
            'helpdesk_settings': helpdesk_settings,
        })
    items = item.category.kbitem_set.all()
    item_index = list(items.values_list('id', flat=True)).index(item.id)
    try:
        prev_item = items[item_index - 1]
    except AssertionError:
        prev_item = None
    try:
        next_item = items[item_index + 1]
    except IndexError:
        next_item = None

    qparams = request.GET.copy()
    try:
        del qparams['kbitem']
    except KeyError:
        pass
    template = 'helpdesk/kb_article.html'
    staff = request.user.is_authenticated and is_helpdesk_staff(request.user)
    return render(request, template, {
        'category': item.category,
        'prev_item': prev_item,
        'item': item,
        'next_item': next_item,
        'query_param_string': qparams.urlencode(),
        'helpdesk_settings': helpdesk_settings,
        'iframe': iframe,
        'staff': staff,
    })

@xframe_options_exempt
def category_iframe(request, slug):
    return category(request, slug, iframe=True)


def vote(request, item):
    item = get_object_or_404(KBItem, pk=item)
    vote = request.GET.get('vote', None)
    if vote == 'up':
        if not item.voted_by.filter(pk=request.user.pk):
            item.votes += 1
            item.voted_by.add(request.user.pk)
            item.recommendations += 1
        if item.downvoted_by.filter(pk=request.user.pk):
            item.votes -= 1
            item.downvoted_by.remove(request.user.pk)
    if vote == 'down':
        if not item.downvoted_by.filter(pk=request.user.pk):
            item.votes += 1
            item.downvoted_by.add(request.user.pk)
            item.recommendations -= 1
        if item.voted_by.filter(pk=request.user.pk):
            item.votes -= 1
            item.voted_by.remove(request.user.pk)
    item.save()
    return HttpResponseRedirect(item.get_absolute_url())
