"""
Jutda Helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

urls.py - Mapping of URL's to our various views. Note we always used NAMED 
          views for simplicity in linking later on.
"""

from django.conf.urls.defaults import *

from django.contrib.auth.decorators import login_required

from feeds import feed_setup

from django.contrib.syndication.views import feed as django_feed

urlpatterns = patterns('helpdesk.views',
    url(r'^$', 
        'dashboard',
        name='helpdesk_home'),
    
    url(r'^tickets/$', 
        'ticket_list',
        name='helpdesk_list'),
    
    url(r'^tickets/submit/$', 
        'create_ticket',
        name='helpdesk_submit'),

    url(r'^tickets/(?P<ticket_id>[0-9]+)/$',
        'view_ticket',
        name='helpdesk_view'),
    
    url(r'^tickets/(?P<ticket_id>[0-9]+)/update/$',
        'update_ticket',
        name='helpdesk_update'),
    
    url(r'^tickets/(?P<ticket_id>[0-9]+)/delete/$',
        'delete_ticket',
        name='helpdesk_delete'),
    
    url(r'^tickets/(?P<ticket_id>[0-9]+)/hold/$',
        'hold_ticket',
        name='helpdesk_hold'),

    url(r'^tickets/(?P<ticket_id>[0-9]+)/unhold/$',
        'unhold_ticket',
        name='helpdesk_unhold'),

    url(r'^raw/(?P<type>\w+)/$',
        'raw_details',
        name='helpdesk_raw'),

    url(r'^view/$',
        'public_view',
        name='helpdesk_public_view'),
    
    url(r'^rss/$',
        'rss_list',
        name='helpdesk_rss_index'),
)

urlpatterns += patterns('',
    url(r'^rss/(?P<url>.*)/$',
        login_required(django_feed),
        {'feed_dict': feed_setup},
        name='helpdesk_rss'),
)
urlpatterns += patterns('',
    url(r'^api/(?P<method>[a-z_-]+)/$',
        'helpdesk.api.api',
        name='helpdesk_api'),
    
    url(r'^login/$',
        'django.contrib.auth.views.login',
        name='login'),

    url(r'^logout/$',
        'django.contrib.auth.views.logout',
        name='logout'),
)
