"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

views/kb.py - Public-facing knowledgebase views. The knowledgebase is a
              simple categorised question/answer system to show common
              resolutions to common problems.
"""

from django.http import Http404, HttpResponseRedirect, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.clickjacking import xframe_options_exempt

from helpdesk import settings as helpdesk_settings
from helpdesk import user
from helpdesk.models import KBCategory, KBItem


def index(request: HttpRequest) -> HttpResponse:
    """
    List view for public facing knowledge base articles arrange by category.
    # TODO: It'd be great to have a list of most popular items here.
    """

    huser = user.huser_from_request(request)
    ctx = {
        "kb_categories": huser.get_allowed_kb_categories(),
        "helpdesk_settings": helpdesk_settings,
    }
    return render(request, "helpdesk/kb_index.html", ctx)


def category(request: HttpRequest, slug: str, iframe=False) -> HttpResponse:
    """
    List view to show all knowledge base articles for a particular category.
    """

    category = get_object_or_404(KBCategory, slug__iexact=slug)

    if not user.huser_from_request(request).can_access_kbcategory(category):
        raise Http404

    staff = request.user.is_authenticated and request.user.is_staff
    items = category.kbitem_set.filter(enabled=True)
    selected_item = request.GET.get("kbitem", None)

    try:
        selected_item = int(selected_item)
    except TypeError:
        pass

    qparams = request.GET.copy()
    qparams.pop("kbitem", None)

    template = "helpdesk/kb_category.html"
    if iframe:
        template = "helpdesk/kb_category_iframe.html"

    ctx = {
        "category": category,
        "items": items,
        "selected_item": selected_item,
        "query_param_string": qparams.urlencode(),
        "helpdesk_settings": helpdesk_settings,
        "iframe": iframe,
        "staff": staff,
    }

    return render(request, template, ctx)


@xframe_options_exempt
def category_iframe(request, slug):
    return category(request, slug, iframe=True)


def vote(request, item, vote):
    item = get_object_or_404(KBItem, pk=item)
    if request.method == "POST":
        if vote == "up":
            if not item.voted_by.filter(pk=request.user.pk):
                item.votes += 1
                item.voted_by.add(request.user.pk)
                item.recommendations += 1
            if item.downvoted_by.filter(pk=request.user.pk):
                item.votes -= 1
                item.downvoted_by.remove(request.user.pk)
        if vote == "down":
            if not item.downvoted_by.filter(pk=request.user.pk):
                item.votes += 1
                item.downvoted_by.add(request.user.pk)
                item.recommendations -= 1
            if item.voted_by.filter(pk=request.user.pk):
                item.votes -= 1
                item.voted_by.remove(request.user.pk)
        item.save()
    return HttpResponseRedirect(item.get_absolute_url())
