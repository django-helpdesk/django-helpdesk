Settings
========

First, django-helpdesk needs  ``django.core.context_processors.request`` activated, so in your ``settings.py`` add::

    from django.conf import global_settings
    TEMPLATE_CONTEXT_PROCESSORS = (
                global_settings.TEMPLATE_CONTEXT_PROCESSORS +
                ('django.core.context_processors.request',)
         )

The following settings can be changed in your ``settings.py`` file to help change the way django-helpdesk operates. There are quite a few settings available to toggle functionality within django-helpdesk.

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


Generic Options
---------------
These changes are visible throughout django-helpdesk

- **HELPDESK_REDIRECT_TO_LOGIN_BY_DEFAULT** When a user visits "/", should we redirect to the login page instead of the default homepage?

  **Default:** ``HELPDESK_REDIRECT_TO_LOGIN_BY_DEFAULT = False``

- **HELPDESK_PREPEND_ORG_NAME** Customize helpdesk name on a few pages, i.e., your organization.

  **Default:** ``HELPDESK_PREPEND_ORG_NAME = False``

- **HELPDESK_KB_ENABLED** show knowledgebase links?

  **Default:** ``HELPDESK_KB_ENABLED = True``

- **HELDPESK_KB_ENABLED_STAFF** Show knowledgebase links for staff users?

  **Default:** ``HELPDESK_KB_ENABLED_STAFF = False``

- **HELPDESK_NAVIGATION_ENABLED** Show extended navigation by default, to all users, irrespective of staff status?

  **Default:** ``HELPDESK_NAVIGATION_ENABLED = False``

- **HELPDESK_NAVIGATION_STATS_ENABLED** Show 'stats' link in navigation bar for staff users?

  **Default:** ``HELPDESK_NAVIGATION_STATS_ENABLED = True``

- **HELPDESK_SUPPORT_PERSON** Set this to an email address inside your organization and a footer below
  the 'Powered by django-helpdesk' will be shown, telling the user whom to contact
  in case they have technical problems.

  **Default:** ``HELPDESK_SUPPORT_PERSON = ""``

- **HELPDESK_TRANSLATE_TICKET_COMMENTS** Show dropdown list of languages that ticket comments can be translated into via Google Translate?

  **Default:** ``HELPDESK_TRANSLATE_TICKET_COMMENTS = False``

- **HELPDESK_TRANSLATE_TICKET_COMMENTS_LANG** List of languages to offer. If set to false, all default google translate languages will be shown.

  **Default:** ``HELPDESK_TRANSLATE_TICKET_COMMENTS_LANG = ["en", "de", "fr", "it", "ru"]``

- **HELPDESK_SHOW_CHANGE_PASSWORD** Show link to 'change password' on 'User Settings' page?

  **Default:** ``HELPDESK_SHOW_CHANGE_PASSWORD = False``

- **HELPDESK_FOLLOWUP_MOD** Allow user to override default layout for 'followups' (work in progress)
  
  **Default:** ``HELPDESK_FOLLOWUP_MOD = False``

- **HELPDESK_CUSTOM_WELCOME** Show custom welcome message in dashboard?
  
  **Default:** ``HELPDESK_CUSTOM_WELCOME = False``

- **HELPDESK_AUTO_SUBSCRIBE_ON_TICKET_RESPONSE ** Auto-subscribe user to ticket as a 'CC' if (s)he responds to a ticket?
  
  **Default:** ``HELPDESK_AUTO_SUBSCRIBE_ON_TICKET_RESPONSE = False``


Options shown on public pages
-----------------------------

These options only change display of items on public-facing pages, not staff pages.

- **HELPDESK_VIEW_A_TICKET_PUBLIC** Show 'View a Ticket' section on public page?
  
  **Default:** ``HELPDESK_VIEW_A_TICKET_PUBLIC = True``

- **HELPDESK_SUBMIT_A_TICKET_PUBLIC** Show 'submit a ticket' section & form on public page?
  
  **Default:** ``HELPDESK_SUBMIT_A_TICKET_PUBLIC = True``

- **HELPDESK_SHOW_KB_ON_HOMEPAGE** Should we should the KB categories on the homepage?
  
  **Default:** ``HELPDESK_SHOW_KB_ON_HOMEPAGE = False``


Options that change ticket updates
----------------------------------

- **HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE** Allow non-staff users to interact with tickets? This will also change how 'staff_member_required' 
  in staff.py will be defined.
  
  **Default:** ``HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE = False``

- **HELPDESK_SHOW_EDIT_BUTTON_FOLLOW_UP** Show edit buttons in ticket follow ups?
  
  **Default:** ``HELPDESK_SHOW_EDIT_BUTTON_FOLLOW_UP = True``

- **HELPDESK_SHOW_DELETE_BUTTON_SUPERUSER_FOLLOW_UP** Show delete buttons in ticket follow ups if user is 'superuser'?

  **Default:** ``HELPDESK_SHOW_DELETE_BUTTON_SUPERUSER_FOLLOW_UP = False``

- **HELPDESK_SHOW_EDIT_BUTTON_TICKET_TOP** Show ticket edit button on top of ticket description?

  **Default:** ``HELPDESK_SHOW_EDIT_BUTTON_TICKET_TOP = True``

- **HELPDESK_SHOW_DELETE_BUTTON_TICKET_TOP** Show ticket delete button on top of ticket description?

  **Default:** ``HELPDESK_SHOW_DELETE_BUTTON_TICKET_TOP = True``

- **HELPDESK_SHOW_HOLD_BUTTON_TICKET_TOP** Show hold / unhold button on top of ticket description?

  **Default:** ``HELPDESK_SHOW_HOLD_BUTTON_TICKET_TOP = True``

- **HELPDESK_UPDATE_PUBLIC_DEFAULT** Make all updates public by default? This will hide the 'is this update public' checkbox.

  **Default:** ``HELPDESK_UPDATE_PUBLIC_DEFAULT = True``

- **HELPDESK_STAFF_ONLY_TICKET_OWNERS** Only show staff users in ticket owner drop-downs?

  **Default:** ``HELPDESK_STAFF_ONLY_TICKET_OWNERS = False``

- **HELPDESK_STAFF_ONLY_TICKET_CC** Only show staff users in ticket cc drop-down?

  **Default:** ``HELPDESK_STAFF_ONLY_TICKET_CC = False``


Staff Ticket Creation Settings
------------------------------

- **HELPDESK_CREATE_TICKET_HIDE_ASSIGNED_TO** Hide the 'assigned to' / 'Case owner' field from the 'create_ticket' view? It'll still show on the ticket detail/edit form.

  **Default:** ``HELPDESK_CREATE_TICKET_HIDE_ASSIGNED_TO = False``


Dashboard Settings
------------------

These will change the way the *dashboard* is displayed to staff users when they login.

- **HELPDESK_DASHBOARD_SHOW_DELETE_UNASSIGNED** Show delete button next to unassigned tickets?

  **Default:** ``HELPDESK_DASHBOARD_SHOW_DELETE_UNASSIGNED = True``

- **HELPDESK_DASHBOARD_HIDE_EMPTY_QUEUES** Hide empty queues in dashboard overview?

  **Default:** ``HELPDESK_DASHBOARD_HIDE_EMPTY_QUEUES = True``

- **HELPDESK_DASHBOARD_BASIC_TICKET_STATS** Show basic ticket stats on dashboard? This may have performance implications for busy helpdesks.

  **Default:** ``HELPDESK_DASHBOARD_BASIC_TICKET_STATS = False``


Footer Display Settings
-----------------------

- **HELPDESK_FOOTER_SHOW_API_LINK** Show link to API documentation at bottom of page?

  **Default:** ``HELPDESK_FOOTER_SHOW_API_LINK = True``

- **HELPDESK_FOOTER_SHOW_CHANGE_LANGUAGE_LINK** Show the 'change language' link at bottom of page? Useful if you have a multilingual helpdesk.

  **Default:** ``HELPDESK_FOOTER_SHOW_CHANGE_LANGUAGE_LINK = False``

Default E-Mail Settings
-----------------------

The following settings default to ``None`` but can be set as defaults, rather than setting them per-queue.

- ``QUEUE_EMAIL_BOX_TYPE``
- ``QUEUE_EMAIL_BOX_SSL``
- ``QUEUE_EMAIL_BOX_HOST````
- ``QUEUE_EMAIL_BOX_USER``
- ``QUEUE_EMAIL_BOX_PASSWORD``
