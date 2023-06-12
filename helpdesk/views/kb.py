"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

views/kb.py - Public-facing knowledgebase views. The knowledgebase is a
              simple categorised question/answer system to show common
              resolutions to common problems.
"""

from django.conf import settings
from django.http import HttpResponseRedirect, Http404, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.clickjacking import xframe_options_exempt
from django.urls import reverse

from helpdesk import settings as helpdesk_settings
from helpdesk import user
from helpdesk.models import KBCategory, KBItem, get_markdown
from helpdesk.decorators import is_helpdesk_staff, helpdesk_staff_member_required
from helpdesk.forms import EditKBCategoryForm, EditKBItemForm
from django.utils.html import escape

import datetime

def index(request):
    huser = user.huser_from_request(request)
    # TODO: It'd be great to have a list of most popular items here.
    return render(request, 'helpdesk/kb_index.html', {
        'kb_categories': huser.get_allowed_kb_categories(),
        'helpdesk_settings': helpdesk_settings,
        'debug': settings.DEBUG,
    })


def category(request, slug, iframe=False):
    category = get_object_or_404(KBCategory, slug__iexact=slug)
    if not user.huser_from_request(request).can_access_kbcategory(category):
        # TODO remove category slug and article slug from url
        return render(request, 'helpdesk/kb_index.html', {
            'kb_categories': user.huser_from_request(request).get_allowed_kb_categories(),
            'helpdesk_settings': helpdesk_settings,
            'debug': settings.DEBUG,
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
        'debug': settings.DEBUG,
    })

@helpdesk_staff_member_required
def create_category(request):
    if request.method == 'GET':
        form = EditKBCategoryForm('create', organization = request.user.default_organization)

        return render(request, 'helpdesk/kb_category_edit.html', {
            'form': form,
            'action': "Create",
            'debug': settings.DEBUG,
        })
    elif request.method == 'POST':
        form = EditKBCategoryForm('create', request.POST, organization = request.user.default_organization)

        if form.is_valid():
            category = KBCategory(
                organization = request.user.default_organization,
                name = form.cleaned_data['name'],
                title = form.cleaned_data['title'],
                slug = form.cleaned_data['slug'],
                preview_description = form.cleaned_data['preview_description'],
                description = form.cleaned_data['description'],
                queue = form.cleaned_data['queue'],
                public = form.cleaned_data['public'],
            )
            category.save() 
            category.forms.set(form.cleaned_data['forms'])        
            return HttpResponseRedirect(reverse('helpdesk:kb_index'))
        
        redo_form = EditKBCategoryForm(
            'create', 
            request.POST,
            organization =  request.user.default_organization,
            initial = {
                'name': form.cleaned_data['name'],
                'title': form.cleaned_data['title'],
                'slug': form.data['slug'],
                'preview_description': escape(form.cleaned_data['preview_description']),
                'description': escape(form.cleaned_data['description']),
                'queue': form.cleaned_data['queue'],
                'forms': form.cleaned_data['forms'].all(),
                'public': form.cleaned_data['public'],
            }   
        )

        return render(request, 'helpdesk/kb_category_edit.html', {
            'form': redo_form,
            'errors': form.errors,
            'action': "Create",
            'debug': settings.DEBUG,
        })

@helpdesk_staff_member_required
def edit_category(request, slug):
    """Edit Knowledgebase category"""
    category = get_object_or_404(KBCategory, slug__iexact=slug)

    if request.method == 'GET':
        form = EditKBCategoryForm(
            'edit',
            organization = category.organization,
            initial = {
                'name': category.name,
                'title': category.title,
                'slug': category.slug,
                'preview_description': escape(category.preview_description),
                'description': escape(category.description),
                'queue': category.queue,
                'forms': category.forms.all(),
                'public': category.public,
            }
        )

        return render(request, 'helpdesk/kb_category_edit.html', {
            'category': category,
            'form': form,
            'action': "Edit",
            'debug': settings.DEBUG,
        })
    elif request.method == 'POST':
        form = EditKBCategoryForm("edit", request.POST, organization = category.organization)

        if form.is_valid():
            category.name = form.cleaned_data['name']
            category.title = form.cleaned_data['title']
            # slug = form.cleaned_data['slug']
            category.preview_description = form.cleaned_data['preview_description']
            category.description = form.cleaned_data['description']
            category.queue = form.cleaned_data['queue']
            category.forms.set(form.cleaned_data['forms'])
            category.public = form.cleaned_data['public']

            category.save()
        return HttpResponseRedirect(reverse('helpdesk:kb_category', args=[category.slug]))

@helpdesk_staff_member_required
def delete_category(request, slug):
    category = get_object_or_404(KBCategory, slug=slug)
    category.delete()
    return HttpResponseRedirect(reverse('helpdesk:kb_index'))

def article(request, slug, pk, iframe=False):
    item = get_object_or_404(KBItem, pk=pk)
    if not user.huser_from_request(request).can_access_kbarticle(item):
        # TODO remove category slug and article slug from url
        return render(request, 'helpdesk/kb_index.html', {
            'kb_categories': user.huser_from_request(request).get_allowed_kb_categories(),
            'helpdesk_settings': helpdesk_settings,
            'debug': settings.DEBUG,
        })
    staff = request.user.is_authenticated and is_helpdesk_staff(request.user)
    if staff:
        items = item.category.kbitem_set.all()
        kb_forms = item.category.forms.all().values('id', 'name')
    else:
        items = item.category.kbitem_set.filter(enabled=True)
        kb_forms = item.category.forms.filter(public=True).values('id', 'name')
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
    return render(request, template, {
        'category': item.category,
        'prev_item': prev_item,
        'item': item,
        'next_item': next_item,
        'query_param_string': qparams.urlencode(),
        'helpdesk_settings': helpdesk_settings,
        'iframe': iframe,
        'staff': staff,
        'debug': settings.DEBUG,
        'kb_forms': kb_forms
    })

@helpdesk_staff_member_required
def create_article(request, slug):
    category = get_object_or_404(KBCategory, slug=slug)

    if request.method == 'GET':
        form = EditKBItemForm(organization=request.user.default_organization, category=category)

        return render(request, 'helpdesk/kb_article_edit.html', {
            'category': category,
            'form': form,
            'action': "Create",
            'debug': settings.DEBUG,
        })
    elif request.method == 'POST':
        form = EditKBItemForm(request.POST, organization = request.user.default_organization)

        if form.is_valid():
            item = KBItem(
                category = form.cleaned_data['category'],
                title = form.cleaned_data['title'],
                question = form.cleaned_data['question'],
                answer = escape(form.cleaned_data['answer']),
                order = form.cleaned_data['order'],
                enabled = form.cleaned_data['enabled'],
            )
            item.save()     
        return HttpResponseRedirect(reverse('helpdesk:kb_category', args=[category.slug]))

@helpdesk_staff_member_required
def edit_article(request, slug, pk, iframe=False):
    category = get_object_or_404(KBCategory, slug=slug)
    item = get_object_or_404(KBItem, pk=pk)

    if request.method == "GET":
        form = EditKBItemForm(
            organization = request.user.default_organization,
            initial = {
                'category': item.category,
                'title': item.title,
                'question': item.question,
                'answer': item.answer,
                'order': item.order,
                'enabled': item.enabled,
            }
        )

        return render(request, 'helpdesk/kb_article_edit.html', {
            'category': category,
            'item': item,
            'action': "Edit",
            'form': form,
            'debug': settings.DEBUG,
        })
    elif request.method == "POST":
        form = EditKBItemForm(request.POST, organization = request.user.default_organization)

        if form.is_valid():
            item.category = form.cleaned_data['category']
            item.title = form.cleaned_data['title']
            item.question = form.cleaned_data['question']
            item.answer = form.cleaned_data['answer']
            item.order = form.cleaned_data['order']
            item.enabled = form.cleaned_data['enabled']

            item.save()
        return HttpResponseRedirect(reverse('helpdesk:kb_article', args=[item.category.slug, item.id]))

@helpdesk_staff_member_required
def delete_article(request, slug, pk):
    item = get_object_or_404(KBItem, pk=pk)
    item.delete()
    return HttpResponseRedirect(reverse('helpdesk:kb_category', args=[slug]))

def preview_markdown(request):
    answer = request.GET.get('md')
    org = request.user.default_organization

    class MarkdownNumbers(object):
        def __init__(self, start=1, pattern=''):
            self.count = start - 1
            self.pattern = pattern

        def __call__(self, match):
                self.count += 1
                return self.pattern.format(self.count)

    import re
    title_pattern = r'!~!'
    body_pattern = r'~!~'
    title = "{{: .card .btn .btn-link style='text-align: left;' " \
            "data-toggle='collapse' data-target='#collapse{0}' role='region' " \
            "aria-expanded='false' aria-controls='collapse{0}' .card-header #header{0} .h5 .mb-0 }}"
    body = "{{ #collapse{0} .collapse role='region' aria-labelledby='header{0}' data-parent='#header{0}' " \
           "style='padding-top:0;padding-bottom:0;margin:0;' .card-body }}"
    new_answer, title_count = re.subn(title_pattern, MarkdownNumbers(start=1, pattern=title), answer)
    new_answer, body_count = re.subn(body_pattern, MarkdownNumbers(start=1, pattern=body), new_answer)
    if title_count != 0 and title_count == body_count:
        return JsonResponse({'md_html':get_markdown(new_answer, org, kb=True)})
    return JsonResponse({'md_html':get_markdown(answer, org)})


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


