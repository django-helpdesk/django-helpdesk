Settings
========

First, django-helpdesk needs  ``django.core.context_processors.request`` activated, so you must add it to the ``settings.py``. For Django 1.7, add::

    from django.conf import global_settings
    TEMPLATE_CONTEXT_PROCESSORS = (
                global_settings.TEMPLATE_CONTEXT_PROCESSORS +
                ('django.core.context_processors.request',)
         )

For Django 1.8 and onwards, the settings are located in the ``TEMPLATES``, and the ``request`` module has moved. Add the following instead::

    TEMPLATES = [
        {
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            ...
            'OPTIONS': {
                ...
                'context_processors': (
                    # Default ones first
                    ...
                    # The one django-helpdesk requires:
                    "django.template.context_processors.request",
                ),
            },
        },
    ]


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

- **HELPDESK_KB_ENABLED** show knowledgebase links?

  **Default:** ``HELPDESK_KB_ENABLED = True``

- **HELPDESK_NAVIGATION_ENABLED** Show extended navigation by default, to all users, irrespective of staff status?

  **Default:** ``HELPDESK_NAVIGATION_ENABLED = False``

- **HELPDESK_TRANSLATE_TICKET_COMMENTS** Show dropdown list of languages that ticket comments can be translated into via Google Translate?

  **Default:** ``HELPDESK_TRANSLATE_TICKET_COMMENTS = False``

- **HELPDESK_TRANSLATE_TICKET_COMMENTS_LANG** List of languages to offer. If set to false, all default google translate languages will be shown.

  **Default:** ``HELPDESK_TRANSLATE_TICKET_COMMENTS_LANG = ["en", "de", "fr", "it", "ru"]``

- **HELPDESK_SHOW_CHANGE_PASSWORD** Show link to 'change password' on 'User Settings' page?

  **Default:** ``HELPDESK_SHOW_CHANGE_PASSWORD = False``

- **HELPDESK_FOLLOWUP_MOD** Allow user to override default layout for 'followups' (work in progress)
  
  **Default:** ``HELPDESK_FOLLOWUP_MOD = False``

- **HELPDESK_AUTO_SUBSCRIBE_ON_TICKET_RESPONSE** Auto-subscribe user to ticket as a 'CC' if (s)he responds to a ticket?
  
  **Default:** ``HELPDESK_AUTO_SUBSCRIBE_ON_TICKET_RESPONSE = False``

- **HELPDESK_EMAIL_SUBJECT_TEMPLATE** Subject template for templated emails. ``%(subject)s`` represents the subject wording from the email template (e.g. "(Closed)").

  **Default:** ``HELPDESK_EMAIL_SUBJECT_TEMPLATE = "{{ ticket.ticket }} {{ ticket.title|safe }} %(subject)s"``

- **HELPDESK_EMAIL_FALLBACK_LOCALE** Fallback locale for templated emails when queue locale not found

  **Default:** ``HELPDESK_EMAIL_FALLBACK_LOCALE= "en"``


Options shown on public pages
-----------------------------

These options only change display of items on public-facing pages, not staff pages.

- **HELPDESK_VIEW_A_TICKET_PUBLIC** Show 'View a Ticket' section on public page?
  
  **Default:** ``HELPDESK_VIEW_A_TICKET_PUBLIC = True``

- **HELPDESK_SUBMIT_A_TICKET_PUBLIC** Show 'submit a ticket' section & form on public page?
  
  **Default:** ``HELPDESK_SUBMIT_A_TICKET_PUBLIC = True``


Options that change ticket updates
----------------------------------

- **HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE** Allow non-staff users to interact with tickets? This will also change how 'staff_member_required' 
  in staff.py will be defined.
  
  **Default:** ``HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE = False``

- **HELPDESK_SHOW_EDIT_BUTTON_FOLLOW_UP** Show edit buttons in ticket follow ups?
  
  **Default:** ``HELPDESK_SHOW_EDIT_BUTTON_FOLLOW_UP = True``

- **HELPDESK_SHOW_DELETE_BUTTON_SUPERUSER_FOLLOW_UP** Show delete buttons in ticket follow ups if user is 'superuser'?

  **Default:** ``HELPDESK_SHOW_DELETE_BUTTON_SUPERUSER_FOLLOW_UP = False``

- **HELPDESK_UPDATE_PUBLIC_DEFAULT** Make all updates public by default? This will hide the 'is this update public' checkbox.

  **Default:** ``HELPDESK_UPDATE_PUBLIC_DEFAULT = False``

- **HELPDESK_STAFF_ONLY_TICKET_OWNERS** Only show staff users in ticket owner drop-downs?

  **Default:** ``HELPDESK_STAFF_ONLY_TICKET_OWNERS = False``

- **HELPDESK_STAFF_ONLY_TICKET_CC** Only show staff users in ticket cc drop-down?

  **Default:** ``HELPDESK_STAFF_ONLY_TICKET_CC = False``


Staff Ticket Creation Settings
------------------------------

- **HELPDESK_CREATE_TICKET_HIDE_ASSIGNED_TO** Hide the 'assigned to' / 'Case owner' field from the 'create_ticket' view? It'll still show on the ticket detail/edit form.

  **Default:** ``HELPDESK_CREATE_TICKET_HIDE_ASSIGNED_TO = False``


Staff Ticket View Settings
------------------------------

- **HELPDESK_ENABLE_PER_QUEUE_PERMISSION** If ``True``, logged in staff users only see queues and tickets to which they have specifically been granted access -  this holds for the dashboard, ticket query, and ticket report views. User assignment is done through the standard ``django.admin.admin`` permissions. *Note*: Staff with access to admin interface will be able to see the full list of tickets, but won't have access to details and could not modify them. This setting does not prevent staff users from creating tickets for all queues. Also, superuser accounts have full access to all queues, regardless of whatever queue memberships they have been granted.

  **Default:** ``HELPDESK_ENABLE_PER_QUEUE_PERMISSION = False``



Default E-Mail Settings
-----------------------

The following settings default to ``None`` but can be set as defaults, rather than setting them per-queue.

- ``QUEUE_EMAIL_BOX_TYPE``
- ``QUEUE_EMAIL_BOX_SSL``
- ``QUEUE_EMAIL_BOX_HOST````
- ``QUEUE_EMAIL_BOX_USER``
- ``QUEUE_EMAIL_BOX_PASSWORD``

Discontinued Settings
---------------------

The following settings were defined in previous versions and are no longer supported.

- **HELPDESK_CUSTOM_WELCOME** 

- **HELDPESK_KB_ENABLED_STAFF** Now always True

- **HELPDESK_NAVIGATION_STATS_ENABLED** Now always True

- **HELPDESK_PREPEND_ORG_NAME** Please customise your local `helpdesk/base.html` template if needed

- **HELPDESK_SHOW_DELETE_BUTTON_TICKET_TOP** Button is always shown

- **HELPDESK_SHOW_EDIT_BUTTON_TICKET_TOP** Button is always shown

- **HELPDESK_SHOW_HOLD_BUTTON_TICKET_TOP** Button is always shown

- **HELPDESK_SHOW_KB_ON_HOMEPAGE** KB categories are always shown on the homepage

- **HELPDESK_SUPPORT_PERSON** Please customise your local `helpdesk/attribution.html` template if needed

- **HELPDESK_DASHBOARD_SHOW_DELETE_UNASSIGNED** Button is always shown

- **HELPDESK_DASHBOARD_HIDE_EMPTY_QUEUES** Empty queues are always hidden

- **HELPDESK_DASHBOARD_BASIC_TICKET_STATS** Stats are always shown

- **HELPDESK_FOOTER_SHOW_API_LINK** Link to API documentation is always shown. Edit your local `helpdesk/base.html` template if needed.

- **HELPDESK_FOOTER_SHOW_CHANGE_LANGUAGE_LINK** Is never shown. Use your own template if required.

- **HELPDESK_ENABLE_PER_QUEUE_MEMBERSHIP** Discontinued in favor of HELPDESK_ENABLE_PER_QUEUE_PERMISSION.
