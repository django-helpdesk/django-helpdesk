Settings
========

First, django-helpdesk needs  ``django.core.context_processors.request`` activated, so in your ``settings.py`` add::

    from django.conf import global_settings
    TEMPLATE_CONTEXT_PROCESSORS = (
                global_settings.TEMPLATE_CONTEXT_PROCESSORS +
                ('django.core.context_processors.request',)
         )

The following settings can be changed in your ``settings.py`` file to help change the way django-helpdesk operates.

HELPDESK_DEFAULT_SETTINGS
-------------------------

django-helpdesk has a built in ``UserSettings`` entity with per-user options that they will want to configure themselves. When you create a new user, a set of options is automatically created for them which they can then change themselves.

If you want to override the default settings for your users, create ``HELPDESK_DEFAULT_SETTINGS`` as a dictionary in ``settings.py``. The default is below::

    HELPDESK_DEFAULT_SETTINGS = {
            'use_email_as_submitter': True,
            'email_on_ticket_assign': True,
            'email_on_ticket_change': True,
            'login_view_ticketlist': True,
            'email_on_ticket_apichange': True,
            'tickets_per_page': 25
            }
