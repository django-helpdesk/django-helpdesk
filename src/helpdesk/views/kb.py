"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

views/kb.py - Public-facing knowledgebase views. The knowledgebase is a
              simple categorised question/answer system to show common
              resolutions to common problems.
"""

from django.contrib.auth.decorators import login_required
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
)
from django.shortcuts import get_object_or_404, render
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.http import require_POST

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
def category_iframe(request: HttpRequest, slug: str) -> HttpResponse:
    """
    Renders the knowledge base category detail view in an iframe.
    """
    return category(request, slug, iframe=True)


@require_POST
@login_required
def vote(request: HttpRequest, item_id: int, vote: str) -> HttpResponse:
    """
    Upvote or downvote a knowledge base answer.
    """

    if request.method != "POST":
        return HttpResponseBadRequest()

    user = request.user
    item = get_object_or_404(KBItem, pk=item_id)
    has_upvoted = item.voted_by.contains(user)
    has_downvoted = item.downvoted_by.contains(user)

    if vote == "up":
        # User never upvoted & wants to upvote
        if not has_upvoted:
            item.votes += 1
            item.recommendations += 1
            item.voted_by.add(user)

        # User downvoted earlier but now wants to upvote
        if has_downvoted:
            item.votes = max(item.votes - 1, 0)
            item.downvoted_by.remove(user)

    if vote == "down":
        # User never downvoted & wants to downvote
        if not has_downvoted:
            item.votes += 1
            item.recommendations = max(item.recommendations - 1, 0)
            item.downvoted_by.add(user)

        # User upvoted earlier but now wants to downvote
        if has_upvoted:
            item.votes = max(item.votes - 1, 0)
            item.voted_by.remove(user)

    item.save()

    return HttpResponseRedirect(item.get_absolute_url())
