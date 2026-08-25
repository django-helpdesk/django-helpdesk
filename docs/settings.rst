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

``HELPDESK_PUBLIC_VIEW_PROTECTOR``
  Function that takes a request and can either return ``None`` granting access to to a public view or a redirect denying access.

``HELPDESK_STAFF_VIEW_PROTECTOR``
  Function that takes a request and can either return ``None`` granting access to to a staff view or a redirect denying access.

``HELPDESK_REDIRECT_TO_LOGIN_BY_DEFAULT`` (default:``False``)
  When a user visits ``/``, should we redirect to the login page instead of the default homepage?

``HELPDESK_ANON_ACCESS_RAISES_404`` (default:``False``)
  If ``True``, redirects user to a 404 page when attempting to reach ticket pages while not logged in, rather than redirecting to a login screen.

Settings related to attachments

``HELPDESK_ENABLE_ATTACHMENTS`` (default:``True``)
  If set to ``True``, files can be attached to tickets and followups, and emails are searched for attachments which are then attached to the ticket.  Also enables the ``HELPDESK_ALWAYS_SAVE_INCOMING_EMAIL_MESSAGE`` setting.

  .. caution::
     Set this to False, unless you have secured access to the uploaded files. Otherwise anyone on the Internet will be able to download your ticket attachments.

     Attachments are enabled by default for backwards compatibility.

``HELPDESK_VALID_EXTENSIONS`` (default:``['.txt', '.asc', '.htm', '.html', '.pdf', '.doc', '.docx', '.odt', '.jpg', '.png', '.eml']``)
  Valid extensions for file types that can be attached to tickets. Note: This used to be called ``VALID_EXTENSIONS`` which is now deprecated.

``HELPDESK_VALIDATE_ATTACHMENT_TYPES``
  If you'd like to turn of filtering of helpdesk extension types you can set this to ``False``.


Generic Options
---------------

These changes are visible throughout django-helpdesk

``HELPDESK_KANBAN_ENABLED`` (default:``True``)
  show the Kanban board?

``HELPDESK_KANBAN_DEFAULT_DUE_WEEKS`` (default:``2``)
  Default number of weeks ahead used by the Kanban board's due-date filter (more Scrum like). On first load (no filter parameters in the URL) the board shows tickets due within this many weeks plus any overdue open tickets.
  Set to ``0`` or ``None`` to show all tickets by default (Makes it more Kanban like - not recommended for large datasets).

``HELPDESK_KANBAN_DEFAULT_RENDER_CLOSED_TICKETS_WEEKS`` (default:``6``)
  Hides closed and duplicate tickets that have not been modified within this many weeks. Tickets with a ``Closed`` or ``Duplicate`` status whose ``modified`` timestamp is older than the cutoff are excluded from the board.
  Set to ``0`` or ``None`` to always show all closed and duplicate tickets regardless of age.

``HELPDESK_KB_ENABLED`` (default:``True``)
  Show knowledgebase links?

``HELPDESK_NAVIGATION_ENABLED`` (default:``False``)
  Show extended navigation by default, to all users, irrespective of staff status?

``HELPDESK_SHOW_MY_TICKETS_IN_NAV_FOR_STAFF`` (default:``True``)
  Show "My tickets" for staff. Typically used for help desk deployments that allow staff to create tickets to action other staff members.

``HELPDESK_TRANSLATE_TICKET_COMMENTS`` (default:``False``)
  Show dropdown list of languages that ticket comments can be translated into via Google Translate?

``HELPDESK_TRANSLATE_TICKET_COMMENTS_LANG`` (default:``["en", "de", "fr", "it", "ru"]``)
  List of languages to offer. If set to false, all default google translate languages will be shown.

``HELPDESK_FOLLOWUP_MOD`` (default:``False``)
  Allow user to override default layout for 'followups' (work in progress)

``HELPDESK_AUTO_SUBSCRIBE_ON_TICKET_RESPONSE`` (default:``False``)
  Auto-subscribe user to ticket as a 'CC' if (s)he responds to a ticket?

``HELPDESK_EMAIL_SUBJECT_TEMPLATE`` (default: ``"{{ ticket.ticket }} {{ ticket.title|safe }} %(subject)s"``)
  Subject template for templated emails. ``%(subject)s`` represents the subject wording from the email template (e.g. "(Closed)").

  .. caution::
     Your subject template should always include a ``{{ ticket.ticket }}`` somewhere as many ``django-helpdesk`` features rely on the ticket ID in the subject line in order to correctly route mail to the corresponding ticket. If you leave out the ticket ID, your helpdesk may not work correctly!


``HELPDESK_NOTIFY_SUBMITTER_FOR_ALL_TICKET_CHANGES`` (default:``False``)
  Send email to submitter for all ticket updates. Default is to only sends to submitter for followups marked as public (defaults to True) on ticket creation, closing, status changes or followup comment.


``HELPDESK_PRIVATE_FOLLOWUP_MEANS_NO_EMAILS`` (default: ``False``)
  If ``True``, private follow-ups (marked with ``public=False``) will not trigger any email notifications to any recipients (submitters, assigned users, CC'd users, or queue notifications). This provides complete privacy for internal staff communications.
  Public follow-ups (``public=True``) continue to work normally. This setting overrides other notification settings like ``HELPDESK_NOTIFY_SUBMITTER_FOR_ALL_TICKET_CHANGES`` when the follow-up is private.

``HELPDESK_EMAIL_FALLBACK_LOCALE`` (default: ``en``)
  Fallback locale for templated emails when queue locale not found

``HELPDESK_MAX_EMAIL_ATTACHMENT_SIZE`` (default: ``512000``)
  Maximum size, in bytes, of file attachments that will be sent via email

``QUEUE_EMAIL_BOX_UPDATE_ONLY`` (default: ``False``)
  Only process mail with a valid tracking ID; all other mail will be ignored instead of creating a new ticket.

``HELPDESK_ENABLE_DEPENDENCIES_ON_TICKET`` (default:``True``)
  If False, disable the dependencies fields on ticket.

``HELPDESK_ENABLE_TIME_SPENT_ON_TICKET`` (default: ``True``)
  If False, disable the time spent fields on ticket.

``HELPDESK_TICKETS_TIMELINE_ENABLED`` (default: ``True``)
  If False, remove from the dashboard the Timeline view for tickets.


Options shown on public pages
-----------------------------

These options only change display of items on public-facing pages, not staff pages.

``HELPDESK_VIEW_A_TICKET_PUBLIC`` (default:``True``)
  Show 'View a Ticket' section on public page?

``HELPDESK_SUBMIT_A_TICKET_PUBLIC`` (default:``True``)
  Show 'submit a ticket' section & form on public page?

``HELPDESK_PUBLIC_TICKET_FORM_CLASS`` (default:``helpdesk.forms.PublicTicketForm``)
  Define custom form class to show on public pages for anon users. You can use it for adding custom fields and validation, captcha and so on.


Options for public ticket submission form
-----------------------------------------

``HELPDESK_PUBLIC_TICKET_QUEUE`` (default: Not defined)
  Sets the queue for tickets submitted through the public form. If defined, the matching form field will be hidden. This cannot be `None` but must be set to a valid queue slug.

``HELPDESK_PUBLIC_TICKET_PRIORITY`` (default: Not defined)
  Sets the priority for tickets submitted through the public form. If defined, the matching form field will be hidden. Must be set to a valid integer priority.

``HELPDESK_PUBLIC_TICKET_DUE_DATE`` (default: Not defined)
  Sets the due date for tickets submitted through the public form. If defined, the matching form field will be hidden. Set to `None` if you want to hide the form field but do not want to define a value.



Options that change ticket updates
----------------------------------

``HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE`` (default:``False``)
  Allow non-staff users to interact with tickets?
  Set to True to allow any authenticated user to manage tickets.
  You can also apply a custom authorisation logic for identifying helpdesk staff members, by setting this to a callable.
  In that case, the value should be a function accepting the active user as a parameter and returning True if the user is considered helpdesk staff, e.g.::

    lambda u: u.is_authenticated() and u.is_active and u.groups.filter(name='helpdesk_staff').exists()

``HELPDESK_SHOW_EDIT_BUTTON_FOLLOW_UP`` (default:``True``)
  Show edit buttons in ticket follow ups?

``HELPDESK_SHOW_DELETE_BUTTON_SUPERUSER_FOLLOW_UP`` (default:``False``)
  Show delete buttons in ticket follow ups if user is 'superuser'?

``HELPDESK_UPDATE_PUBLIC_DEFAULT`` (default:``False``)
  Make all updates public by default? This will hide the 'is this update public' checkbox.

``HELPDESK_STAFF_ONLY_TICKET_OWNERS`` (default:``False``)
  Only show staff users in ticket owner drop-downs?

``HELPDESK_STAFF_ONLY_TICKET_CC`` (default:``False``)
  Only show staff users in ticket cc drop-down?

``HELPDESK_SHOW_CUSTOM_FIELDS_FOLLOW_UP_LIST`` (default:``[]``)
  Show configured custom fields in the follow-up form.

``HELPDESK_FOLLOWUP_NEWEST_FIRST`` (default:``False``)
  Sets the default order for the follow-up list on the ticket view. If True, the most recent follow up is listed first. If False, the oldest follow up is listed first. Users can still toggle the order from the ticket view using the sort button, regardless of this setting.

Options that change ticket properties
-------------------------------------

``HELPDESK_TICKET_OPEN_STATUS`` (default:``1``)
  Customize the id of OPEN_STATUS status.

``HELPDESK_TICKET_REOPENED_STATUS`` (default:``2``)
  Customize the id of REOPENED_STATUS status.

``HELPDESK_TICKET_RESOLVED_STATUS`` (default:``3``)
  Customize the id of RESOLVED_STATUS status.

``HELPDESK_TICKET_CLOSED_STATUS`` (default: ``4``)
  Customize the id of CLOSED_STATUS status.

``HELPDESK_TICKET_DUPLICATE_STATUS`` (default: ``5``)
  Customize the id of DUPLICATE_STATUS status.

``HELPDESK_TICKET_STATUS_CHOICES``
  Customize the list of status choices for all tickets.

  The ``default`` is::

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

``HELPDESK_TICKET_OPEN_STATUSES``
  (default: ``(HELPDESK_TICKET_OPEN_STATUS, HELPDESK_TICKET_REOPENED_STATUS)``)

  Define the list of statuses to be considered as a type of open status.

  If you have added the ``HELPDESK_TICKET_FORKED_STATUS`` status and wish to have django-helpdesk treat it as an open status choice, add it to the list of OPEN_STATUSES like this::

    HELPDESK_TICKET_OPEN_STATUSES = (HELPDESK_TICKET_OPEN_STATUS,
                                     HELPDESK_TICKET_REOPENED_STATUS,
                                     HELPDESK_TICKET_FORKED_STATUS)

``HELPDESK_TICKET_STATUS_CHOICES_FLOW``
  Customize the allowed state changes depending on the current state.

  The default is::

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

``HELPDESK_TICKET_STATUS_CSS_CLASSES``
  Customize the Bootstrap CSS class used for the status badge of each ticket in the ticket list.

  The default is::

    HELPDESK_TICKET_STATUS_CSS_CLASSES = {
        HELPDESK_TICKET_OPEN_STATUS: 'danger',
        HELPDESK_TICKET_REOPENED_STATUS: 'warning',
        HELPDESK_TICKET_RESOLVED_STATUS: 'success',
        HELPDESK_TICKET_CLOSED_STATUS: 'success',
        HELPDESK_TICKET_DUPLICATE_STATUS: 'secondary',
    }

  Statuses not present in the map return an empty string from the model; the
  ticket-list template applies ``secondary`` (gray) as the default when the
  class is empty. To give a custom status its own badge color, add an entry like this::

    HELPDESK_TICKET_STATUS_CSS_CLASSES = {
        HELPDESK_TICKET_OPEN_STATUS: 'danger',
        HELPDESK_TICKET_REOPENED_STATUS: 'warning',
        HELPDESK_TICKET_RESOLVED_STATUS: 'success',
        HELPDESK_TICKET_CLOSED_STATUS: 'success',
        HELPDESK_TICKET_DUPLICATE_STATUS: 'secondary',
        HELPDESK_TICKET_FORKED_STATUS: 'dark',
    }

``HELPDESK_TICKET_PRIORITY_CHOICES``
  Customize the priority choices for all tickets.

  The default is::

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

``HELPDESK_TICKET_PRIORITY_CSS_CLASSES``
  Customize the Bootstrap CSS class used for the priority badge of each ticket in the ticket list.

  The default is::

    HELPDESK_TICKET_PRIORITY_CSS_CLASSES = {
        1: 'danger',
        2: 'warning',
        3: 'success',
        4: 'info',
        5: 'secondary',
    }

  Priorities not present in the map return an empty string from the model; the
  ticket-list template applies ``secondary`` (gray) as the default when the
  class is empty.


Time Tracking Options
---------------------

``HELPDESK_FOLLOWUP_TIME_SPENT_AUTO`` (default:``False``)
  If ``True``, calculate follow-up 'time_spent' with previous follow-up or ticket creation time.

``HELPDESK_FOLLOWUP_TIME_SPENT_OPENING_HOURS`` (default:``{}``)
  If defined, calculates follow-up 'time_spent' according to open hours.

  If ``HELPDESK_FOLLOWUP_TIME_SPENT_AUTO=True``, you may set open hours to remove off hours from 'time_spent'::

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

``HELPDESK_FOLLOWUP_TIME_SPENT_EXCLUDE_HOLIDAYS`` (default: ``()``)
  List of days in format ``%Y-%m-%d`` to exclude from automatic follow-up 'time_spent' calculation.

  This example removes Christmas and New Year's Eve in 2024::

    HELPDESK_FOLLOWUP_TIME_SPENT_EXCLUDE_HOLIDAYS = ("2024-12-25", "2024-12-31",)

``HELPDESK_FOLLOWUP_TIME_SPENT_EXCLUDE_STATUSES`` (default: ``()``)
  List of ticket statuses to exclude from automatic follow-up 'time_spent' calculation.

  This example will have follow-ups to resolved ticket status not to be counted in::

    HELPDESK_FOLLOWUP_TIME_SPENT_EXCLUDE_STATUSES = (HELPDESK_TICKET_RESOLVED_STATUS,)

``HELPDESK_FOLLOWUP_TIME_SPENT_EXCLUDE_QUEUES`` (default: ``()``)
  List of ticket queues slugs to exclude from automatic follow-up 'time_spent' calculation.

  This example will have follow-ups excluded from time calculation if they belong to the queue with slug ``time-not-counting-queue``::

    HELPDESK_FOLLOWUP_TIME_SPENT_EXCLUDE_QUEUES = ('time-not-counting-queue',)


Staff Ticket Creation Settings
------------------------------

``HELPDESK_CREATE_TICKET_HIDE_ASSIGNED_TO`` (default:``False``)
  Hide the 'assigned to' / 'Case owner' field from the 'create_ticket' view? It'll still show on the ticket detail/edit form.

Staff Ticket View Settings
------------------------------

``HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION`` (default:``False``)
  If ``True``, logged in staff users only see queues and tickets to which they have specifically been granted access -  this holds for the dashboard, ticket query, and ticket report views. User assignment is done through the standard ``django.admin.admin`` permissions.

  .. note::
     Staff with access to admin interface will be able to see the full list of tickets, but won't have access to details and could not modify them. This setting does not prevent staff users from creating tickets for all queues. Also, superuser accounts have full access to all queues, regardless of whatever queue memberships they have been granted.


Default E-Mail Settings
-----------------------

The following settings default to ``None`` but can be set as defaults, rather than setting them per-queue.

``QUEUE_EMAIL_BOX_TYPE``
  Protocol used: ``pop3``, ``imap`` or ``oauth``.

``QUEUE_EMAIL_BOX_SSL``
  Set to ``True`` to use SSL, otherwise ``False``.

``QUEUE_EMAIL_BOX_HOST``
  The URL of the mail server.

``QUEUE_EMAIL_BOX_USER``
  The ``username`` of the email account.

``QUEUE_EMAIL_BOX_PASSWORD``
  The ``password`` of the email account.

  If ``oauth`` is used, configure ``HELPDESK_OAUTH``::

    HELPDESK_OAUTH = {
        "token_url": "",
        "client_id": "",
        "secret": "",
        "scope": [""],
    }

``HELPDESK_IMAP_DEBUG_LEVEL`` (default: ``0``)
  If using ``imap`` or ``oauth``, set the IMAP debug logging level. Default: ``0`` (no debugging).


Discontinued Settings
---------------------
The following settings were defined in previous versions and are no longer supported.

``HELPDESK_CUSTOM_WELCOME``

``HELDPESK_KB_ENABLED_STAFF``
  Now always True

``HELPDESK_NAVIGATION_STATS_ENABLED``
  Now always True

``HELPDESK_PREPEND_ORG_NAME``
  Please customise your local ``helpdesk/base.html`` template if needed

``HELPDESK_SHOW_DELETE_BUTTON_TICKET_TOP``
  Button is always shown

``HELPDESK_SHOW_EDIT_BUTTON_TICKET_TOP``
  Button is always shown

``HELPDESK_SHOW_HOLD_BUTTON_TICKET_TOP``
  Button is always shown

``HELPDESK_SHOW_KB_ON_HOMEPAGE``
  KB categories are always shown on the homepage

``HELPDESK_SUPPORT_PERSON``
  Please customise your local ``helpdesk/attribution.html`` template if needed

``HELPDESK_DASHBOARD_SHOW_DELETE_UNASSIGNED``
  Button is always shown

``HELPDESK_DASHBOARD_HIDE_EMPTY_QUEUES``
  Empty queues are always hidden

``HELPDESK_DASHBOARD_BASIC_TICKET_STATS``
  Stats are always shown

``HELPDESK_FOOTER_SHOW_API_LINK``
  Link to API documentation is always shown. Edit your local ``helpdesk/base.html`` template if needed.

``HELPDESK_FOOTER_SHOW_CHANGE_LANGUAGE_LINK``
  Is never shown. Use your own template if required.

``HELPDESK_ENABLE_PER_QUEUE_MEMBERSHIP``
  Discontinued in favor of ``HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION``.

``HELPDESK_FULL_FIRST_MESSAGE_FROM_EMAIL``
  Do not ignore fowarded and replied text from the email messages which create a new ticket; useful for cases when customer forwards some email (error from service or something) and wants support to see that

``HELPDESK_ALWAYS_SAVE_INCOMING_EMAIL_MESSAGE``
  Any incoming .eml message is saved and available, helps when customer spent some time doing fancy markup which has been corrupted during the ``email-to-ticket-comment`` translate process.

  Requires ``HELPDESK_ENABLE_ATTACHMENTS`` to be set to ``True``
