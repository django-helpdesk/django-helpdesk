"""
Jutda Helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

urls.py - Mapping of URL's to our various views. Note we always used NAMED 
          views for simplicity in linking later on.
"""

from django.conf.urls.defaults import *

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
