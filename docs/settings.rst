Settings
========

First, django-helpdesk needs  ``django.core.context_processors.request`` activated, so you must add it to the ``settings.py``. Add the following::

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
        'tickets_per_page': 25
    }


Access control & Security
-------------------------
These settings can be used to change who can access the helpdesk.

- **HELPDESK_PUBLIC_VIEW_PROTECTOR** This is a function that takes a request and can either return `None` granting access to to a public view or a redirect denying access.

- **HELPDESK_STAFF_VIEW_PROTECTOR** This is a function that takes a request and can either return `None` granting access to to a staff view or a redirect denying access.

- **HELPDESK_REDIRECT_TO_LOGIN_BY_DEFAULT** When a user visits "/", should we redirect to the login page instead of the default homepage?

  **Default:** ``HELPDESK_REDIRECT_TO_LOGIN_BY_DEFAULT = False``

- **HELPDESK_ANON_ACCESS_RAISES_404** If True, redirects user to a 404 page when attempting to reach ticket pages while not logged in, rather than redirecting to a login screen.

  **Default:** ``HELPDESK_ANON_ACCESS_RAISES_404 = False``

Settings related to attachments:

- **HELPDESK_ENABLE_ATTACHMENTS** If set to ``True``, files can be
  attached to tickets and followups, and emails are searched for
  attachments which are then attached to the ticket.  Also enables the
  ``HELPDESK_ALWAYS_SAVE_INCOMING_EMAIL_MESSAGE`` setting.

  **Caution**: Set this to False, unless you have secured access to
   the uploaded files. Otherwise anyone on the Internet will be able
   to download your ticket attachments.

   Attachments are enabled by default for backwards compatibility.
  
- **HELPDESK_VALID_EXTENSIONS** Valid extensions for file types that can be attached to tickets. Note: This used to be called **VALID_EXTENSIONS** which is now deprecated.

  **Default:** ``HELPDESK_VALID_EXTENSIONS = ['.txt', '.asc', '.htm', '.html', '.pdf', '.doc', '.docx', '.odt', '.jpg', '.png', '.eml']``

- **HELPDESK_VALIDATE_ATTACHMENT_TYPES** If you'd like to turn of filtering of helpdesk extension types you can set this to False.

  
Generic Options
---------------
These changes are visible throughout django-helpdesk

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

- **HELPDESK_EMAIL_SUBJECT_TEMPLATE** Subject template for templated emails. ``%(subject)s`` represents the subject wording from the email template (e.g. "(Closed)"). *Warning*: your subject template should always include a ``{{ ticket.ticket }}`` somewhere as many ``django-helpdesk`` features rely on the ticket ID in the subject line in order to correctly route mail to the corresponding ticket. If you leave out the ticket ID, your helpdesk may not work correctly!

  **Default:** ``HELPDESK_EMAIL_SUBJECT_TEMPLATE = "{{ ticket.ticket }} {{ ticket.title|safe }} %(subject)s"``

- **HELPDESK_EMAIL_FALLBACK_LOCALE** Fallback locale for templated emails when queue locale not found

  **Default:** ``HELPDESK_EMAIL_FALLBACK_LOCALE = "en"``

- **HELPDESK_MAX_EMAIL_ATTACHMENT_SIZE** Maximum size, in bytes, of file attachments that will be sent via email

  **Default:** ``HELPDESK_MAX_EMAIL_ATTACHMENT_SIZE = 512000``

- **QUEUE_EMAIL_BOX_UPDATE_ONLY** Only process mail with a valid tracking ID; all other mail will be ignored instead of creating a new ticket.

  **Default:** ``QUEUE_EMAIL_BOX_UPDATE_ONLY = False``

- **HELPDESK_ENABLE_DEPENDENCIES_ON_TICKET** If False, disable the dependencies fields on ticket.

  **Default:** ``HELPDESK_ENABLE_DEPENDENCIES_ON_TICKET = True``

- **HELPDESK_ENABLE_TIME_SPENT_ON_TICKET** If False, disable the time spent fields on ticket.

  **Default:** ``HELPDESK_ENABLE_TIME_SPENT_ON_TICKET = True``

- **HELPDESK_TICKETS_TIMELINE_ENABLED** If False, remove from the dashboard the Timeline view for tickets.

  **Default:** ``HELPDESK_TICKETS_TIMELINE_ENABLED = True``


Options shown on public pages
-----------------------------

These options only change display of items on public-facing pages, not staff pages.

- **HELPDESK_VIEW_A_TICKET_PUBLIC** Show 'View a Ticket' section on public page?

  **Default:** ``HELPDESK_VIEW_A_TICKET_PUBLIC = True``

- **HELPDESK_SUBMIT_A_TICKET_PUBLIC** Show 'submit a ticket' section & form on public page?

  **Default:** ``HELPDESK_SUBMIT_A_TICKET_PUBLIC = True``

- **HELPDESK_PUBLIC_TICKET_FORM_CLASS** Define custom form class to show on public pages for anon users. You can use it for adding custom fields and validation, captcha and so on.

  **Default:** ``HELPDESK_PUBLIC_TICKET_FORM_CLASS = "helpdesk.forms.PublicTicketForm"``


Options for public ticket submission form
-----------------------------------------

- **HELPDESK_PUBLIC_TICKET_QUEUE** Sets the queue for tickets submitted through the public form. If defined, the matching form field will be hidden. This cannot be `None` but must be set to a valid queue slug.

  **Default:** Not defined

- **HELPDESK_PUBLIC_TICKET_PRIORITY** Sets the priority for tickets submitted through the public form. If defined, the matching form field will be hidden. Must be set to a valid integer priority.

  **Default:** Not defined

- **HELPDESK_PUBLIC_TICKET_DUE_DATE** Sets the due date for tickets submitted through the public form. If defined, the matching form field will be hidden. Set to `None` if you want to hide the form field but do not want to define a value.

  **Default:** Not defined


Options that change ticket updates
----------------------------------

- **HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE** Allow non-staff users to interact with tickets?
  Set to True to allow any authenticated user to manage tickets.
  You can also apply a custom authorisation logic for identifying helpdesk staff members, by setting this to a callable.
  In that case, the value should be a function accepting the active user as a parameter and returning True if the user is considered helpdesk staff, e.g.::

    lambda u: u.is_authenticated() and u.is_active and u.groups.filter(name='helpdesk_staff').exists()

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

- **HELPDESK_SHOW_CUSTOM_FIELDS_FOLLOW_UP_LIST** Show configured custom fields in the follow-up form.

  **Default:** ``HELPDESK_SHOW_CUSTOM_FIELDS_FOLLOW_UP_LIST = []``

Options that change ticket properties
-------------------------------------

- **HELPDESK_TICKET_OPEN_STATUS** Customize the id of OPEN_STATUS status.

  **Default:** ``HELPDESK_TICKET_OPEN_STATUS = 1``

- **HELPDESK_TICKET_REOPENED_STATUS** Customize the id of REOPENED_STATUS status.

  **Default:** ``HELPDESK_TICKET_REOPENED_STATUS = 2``

- **HELPDESK_TICKET_RESOLVED_STATUS** Customize the id of RESOLVED_STATUS status.

  **Default:** ``HELPDESK_TICKET_RESOLVED_STATUS = 3``

- **HELPDESK_TICKET_CLOSED_STATUS** Customize the id of CLOSED_STATUS status.

  **Default:** ``HELPDESK_TICKET_CLOSED_STATUS = 4``

- **HELPDESK_TICKET_DUPLICATE_STATUS** Customize the id of DUPLICATE_STATUS status.

  **Default:** ``HELPDESK_TICKET_DUPLICATE_STATUS = 5``

- **HELPDESK_TICKET_STATUS_CHOICES** Customize the list of status choices for all tickets.

  The **default** is below::

    HELPDESK_TICKET_STATUS_CHOICES = (
        (HELPDESK_TICKET_OPEN_STATUS, _('Open')),
        (HELPDESK_TICKET_REOPENED_STATUS, _('Reopened')),
        (HELPDESK_TICKET_RESOLVED_STATUS, _('Resolved')),
        (HELPDESK_TICKET_CLOSED_STATUS, _('Closed')),
        (HELPDESK_TICKET_DUPLICATE_STATUS, _('Duplicate')),
    )

  If you wish to modify or introduce new status choices, you may add them like this::
        
    # Don't forget to import the gettext_lazy function at the begining of your settings file
    from django.utils.translation import gettext_lazy as _

    # Explicitly define status list integer values
    HELPDESK_TICKET_OPEN_STATUS = 1
    HELPDESK_TICKET_REOPENED_STATUS = 2
    HELPDESK_TICKET_RESOLVED_STATUS = 3
    HELPDESK_TICKET_CLOSED_STATUS = 4
    HELPDESK_TICKET_DUPLICATE_STATUS = 5
    HELPDESK_TICKET_FORKED_STATUS = 6

    # Create the list with associated labels
    HELPDESK_TICKET_STATUS_CHOICES = (
        (HELPDESK_TICKET_OPEN_STATUS, _('Open')),
        (HELPDESK_TICKET_REOPENED_STATUS, _('Reopened')),
        (HELPDESK_TICKET_RESOLVED_STATUS, _('Resolved')),
        (HELPDESK_TICKET_CLOSED_STATUS, _('Closed')),
        (HELPDESK_TICKET_DUPLICATE_STATUS, _('Duplicate')),
        (HELPDESK_TICKET_FORKED_STATUS, _('Forked')),
    )

- **HELPDESK_TICKET_OPEN_STATUSES** Define the list of statuses to be considered as a type of open status.

  **Default:** ``HELPDESK_TICKET_OPEN_STATUSES = (HELPDESK_TICKET_OPEN_STATUS, HELPDESK_TICKET_REOPENED_STATUS)``

  If you have added the ``HELPDESK_TICKET_FORKED_STATUS`` status and wish to have django-helpdesk treat it as an open status choice, add it to the list of OPEN_STATUSES like this::

    HELPDESK_TICKET_OPEN_STATUSES = (HELPDESK_TICKET_OPEN_STATUS,
                                        HELPDESK_TICKET_REOPENED_STATUS,
                                        HELPDESK_TICKET_FORKED_STATUS)

- **HELPDESK_TICKET_STATUS_CHOICES_FLOW** Customize the allowed state changes depending on the current state.

  The **default** is below::

    HELPDESK_TICKET_STATUS_CHOICES_FLOW = {
        HELPDESK_TICKET_OPEN_STATUS: (HELPDESK_TICKET_OPEN_STATUS, HELPDESK_TICKET_RESOLVED_STATUS, HELPDESK_TICKET_CLOSED_STATUS, HELPDESK_TICKET_DUPLICATE_STATUS,),
        HELPDESK_TICKET_REOPENED_STATUS: (HELPDESK_TICKET_REOPENED_STATUS, HELPDESK_TICKET_RESOLVED_STATUS, HELPDESK_TICKET_CLOSED_STATUS, HELPDESK_TICKET_DUPLICATE_STATUS,),
        HELPDESK_TICKET_RESOLVED_STATUS: (HELPDESK_TICKET_REOPENED_STATUS, HELPDESK_TICKET_RESOLVED_STATUS, HELPDESK_TICKET_CLOSED_STATUS,),
        HELPDESK_TICKET_CLOSED_STATUS: (HELPDESK_TICKET_REOPENED_STATUS, HELPDESK_TICKET_CLOSED_STATUS,),
        HELPDESK_TICKET_DUPLICATE_STATUS: (HELPDESK_TICKET_REOPENED_STATUS, HELPDESK_TICKET_DUPLICATE_STATUS,),
    }

  If you wish to modify or have introduce new status choices, you may configure their status change flow like this::

    # Adding HELPDESK_TICKET_FORKED_STATUS to the other allowed states flow and defining its own flow
    HELPDESK_TICKET_STATUS_CHOICES_FLOW = {
        HELPDESK_TICKET_OPEN_STATUS: (HELPDESK_TICKET_OPEN_STATUS, HELPDESK_TICKET_FORKED_STATUS, HELPDESK_TICKET_RESOLVED_STATUS, HELPDESK_TICKET_CLOSED_STATUS, HELPDESK_TICKET_DUPLICATE_STATUS,),
        HELPDESK_TICKET_REOPENED_STATUS: (HELPDESK_TICKET_REOPENED_STATUS, HELPDESK_TICKET_FORKED_STATUS, HELPDESK_TICKET_RESOLVED_STATUS, HELPDESK_TICKET_CLOSED_STATUS, HELPDESK_TICKET_DUPLICATE_STATUS,),
        HELPDESK_TICKET_RESOLVED_STATUS: (HELPDESK_TICKET_REOPENED_STATUS, HELPDESK_TICKET_RESOLVED_STATUS, HELPDESK_TICKET_CLOSED_STATUS,),
        HELPDESK_TICKET_CLOSED_STATUS: (HELPDESK_TICKET_REOPENED_STATUS, HELPDESK_TICKET_CLOSED_STATUS,),
        HELPDESK_TICKET_DUPLICATE_STATUS: (HELPDESK_TICKET_REOPENED_STATUS, HELPDESK_TICKET_DUPLICATE_STATUS,),
        HELPDESK_TICKET_FORKED_STATUS: (HELPDESK_TICKET_OPEN_STATUS, HELPDESK_TICKET_FORKED_STATUS, HELPDESK_TICKET_RESOLVED_STATUS, HELPDESK_TICKET_CLOSED_STATUS, HELPDESK_TICKET_DUPLICATE_STATUS,),
    }

- **HELPDESK_TICKET_PRIORITY_CHOICES** Customize the priority choices for all tickets.

  The **default** is below::

    HELPDESK_TICKET_PRIORITY_CHOICES = (
        (1, _('1. Critical')),
        (2, _('2. High')),
        (3, _('3. Normal')),
        (4, _('4. Low')),
        (5, _('5. Very Low')),
    )
        
  If you have a new instance, you may override those settings but if you want to keep previous tickets priorities and add new choices, you may increment integer values like this::

    HELPDESK_TICKET_PRIORITY_CHOICES = (
        (1, _('1. Critical')),
        (2, _('2. High')),
        (3, _('3. Normal')),
        (4, _('4. Low')),
        (5, _('5. Very Low')),
        (6, _('6. Cold')),
        (7, _('7. Hot')),
    )


Time Tracking Options
---------------------

- **HELPDESK_FOLLOWUP_TIME_SPENT_AUTO** If ``True``, calculate follow-up 'time_spent' with previous follow-up or ticket creation time.

  **Default:** ``HELPDESK_FOLLOWUP_TIME_SPENT_AUTO = False``

- **HELPDESK_FOLLOWUP_TIME_SPENT_OPENING_HOURS** If defined, calculates follow-up 'time_spent' according to open hours.
  
  **Default:** ``HELPDESK_FOLLOWUP_TIME_SPENT_OPENING_HOURS = {}``
  
  If HELPDESK_FOLLOWUP_TIME_SPENT_AUTO is ``True``, you may set open hours to remove off hours from 'time_spent'::
  
    HELPDESK_FOLLOWUP_TIME_SPENT_OPENING_HOURS = {
        "monday": (8.5, 19),
        "tuesday": (8.5, 19),
        "wednesday": (8.5, 19),
        "thursday": (8.5, 19),
        "friday": (8.5, 19),
        "saturday": (0, 0),
        "sunday": (0, 0),
    }
  
  Valid hour values must be set between 0 and 23.9999.
  In this example 8.5 is interpreted as 8:30AM, saturdays and sundays don't count.
  
- **HELPDESK_FOLLOWUP_TIME_SPENT_EXCLUDE_HOLIDAYS** List of days in format "%Y-%m-%d" to exclude from automatic follow-up 'time_spent' calculation.

  **Default:** ``HELPDESK_FOLLOWUP_TIME_SPENT_EXCLUDE_HOLIDAYS = ()``
  
  This example removes Christmas and New Year's Eve in 2024::

    HELPDESK_FOLLOWUP_TIME_SPENT_EXCLUDE_HOLIDAYS = ("2024-12-25", "2024-12-31",)

- **HELPDESK_FOLLOWUP_TIME_SPENT_EXCLUDE_STATUSES** List of ticket statuses to exclude from automatic follow-up 'time_spent' calculation.

  **Default:** ``HELPDESK_FOLLOWUP_TIME_SPENT_EXCLUDE_STATUSES = ()``
  
  This example will have follow-ups to resolved ticket status not to be counted in::

    HELPDESK_FOLLOWUP_TIME_SPENT_EXCLUDE_STATUSES = (HELPDESK_TICKET_RESOLVED_STATUS,)

- **HELPDESK_FOLLOWUP_TIME_SPENT_EXCLUDE_QUEUES** List of ticket queues slugs to exclude from automatic follow-up 'time_spent' calculation.

  **Default:** ``HELPDESK_FOLLOWUP_TIME_SPENT_EXCLUDE_QUEUES = ()``
  
  This example will have follow-ups excluded from time calculation if they belong to the queue with slug ``time-not-counting-queue``::

    HELPDESK_FOLLOWUP_TIME_SPENT_EXCLUDE_QUEUES = ('time-not-counting-queue',)


Staff Ticket Creation Settings
------------------------------

- **HELPDESK_CREATE_TICKET_HIDE_ASSIGNED_TO** Hide the 'assigned to' / 'Case owner' field from the 'create_ticket' view? It'll still show on the ticket detail/edit form.

  **Default:** ``HELPDESK_CREATE_TICKET_HIDE_ASSIGNED_TO = False``


Staff Ticket View Settings
------------------------------

- **HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION** If ``True``, logged in staff users only see queues and tickets to which they have specifically been granted access -  this holds for the dashboard, ticket query, and ticket report views. User assignment is done through the standard ``django.admin.admin`` permissions. *Note*: Staff with access to admin interface will be able to see the full list of tickets, but won't have access to details and could not modify them. This setting does not prevent staff users from creating tickets for all queues. Also, superuser accounts have full access to all queues, regardless of whatever queue memberships they have been granted.

  **Default:** ``HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION = False``


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

- **HELPDESK_ENABLE_PER_QUEUE_MEMBERSHIP** Discontinued in favor of HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION.

- **HELPDESK_FULL_FIRST_MESSAGE_FROM_EMAIL** Do not ignore fowarded and replied text from the email messages which create a new ticket; useful for cases when customer forwards some email (error from service or something) and wants support to see that

- **HELPDESK_ALWAYS_SAVE_INCOMING_EMAIL_MESSAGE** Any incoming .eml
  message is saved and available, helps when customer spent some time
  doing fancy markup which has been corrupted during the
  email-to-ticket-comment translate process.

  Requires ``HELPDESK_ENABLE_ATTACHMENTS`` to be set to `True`
