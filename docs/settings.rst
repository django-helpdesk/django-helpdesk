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

.. setting:: HELPDESK_PUBLIC_VIEW_PROTECTOR

   Function that takes a request and can either return ``None`` granting access to to a public view or a redirect denying access.

.. setting:: HELPDESK_STAFF_VIEW_PROTECTOR

   Function that takes a request and can either return ``None`` granting access to to a staff view or a redirect denying access.

.. setting:: HELPDESK_REDIRECT_TO_LOGIN_BY_DEFAULT

   *Default:* ``False``

   When a user visits ``/``, should we redirect to the login page instead of the default homepage?

.. setting:: HELPDESK_ANON_ACCESS_RAISES_404

   *Default:* ``False``

   If ``True``, redirects user to a 404 page when attempting to reach ticket pages while not logged in, rather than redirecting to a login screen.

Settings related to attachments

.. setting:: HELPDESK_ENABLE_ATTACHMENTS

   *Default:* ``True``

   If set to ``True``, files can be attached to tickets and followups, and emails are searched for attachments which are then attached to the ticket.  Also enables the :setting:`HELPDESK_ALWAYS_SAVE_INCOMING_EMAIL_MESSAGE` setting.

   .. caution::
      Set this to False, unless you have secured access to the uploaded files. Otherwise anyone on the Internet will be able to download your ticket attachments.

      Attachments are enabled by default for backwards compatibility.

.. setting:: HELPDESK_VALID_EXTENSIONS

   *Default:* ``['.txt', '.asc', '.htm', '.html', '.pdf', '.doc', '.docx', '.odt', '.jpg', '.png', '.eml']``

   Valid extensions for file types that can be attached to tickets. Note: This used to be called ``VALID_EXTENSIONS`` which is now deprecated.

.. setting:: HELPDESK_VALIDATE_ATTACHMENT_TYPES

   If you'd like to turn of filtering of helpdesk extension types you can set this to ``False``.

.. setting:: HELPDESK_ALWAYS_SAVE_INCOMING_EMAIL_MESSAGE

   *Default:* ``False``

   Any incoming .eml message is saved and available, helps when customer spent some time doing fancy markup which has been corrupted during the ``email-to-ticket-comment`` translate process.

   Requires :setting:`HELPDESK_ENABLE_ATTACHMENTS` to be set to ``True``.


Generic Options
---------------

These changes are visible throughout django-helpdesk

.. setting:: HELPDESK_KANBAN_ENABLED

   *Default:* ``True``

   show the Kanban board?

.. setting:: HELPDESK_KANBAN_DEFAULT_DUE_WEEKS

   *Default:* ``2``

   Default number of weeks ahead used by the Kanban board's due-date filter (more Scrum like). On first load (no filter parameters in the URL) the board shows tickets due within this many weeks plus any overdue open tickets.
   Set to ``0`` or ``None`` to show all tickets by default (Makes it more Kanban like - not recommended for large datasets).

.. setting:: HELPDESK_KANBAN_DEFAULT_RENDER_CLOSED_TICKETS_WEEKS

   *Default:* ``6``

   Hides closed and duplicate tickets that have not been modified within this many weeks. Tickets with a ``Closed`` or ``Duplicate`` status whose ``modified`` timestamp is older than the cutoff are excluded from the board.
   Set to ``0`` or ``None`` to always show all closed and duplicate tickets regardless of age.

.. setting:: HELPDESK_KB_ENABLED

   *Default:* ``True``

   Show knowledgebase links?

.. setting:: HELPDESK_NAVIGATION_ENABLED

   *Default:* ``False``

   Show extended navigation by default, to all users, irrespective of staff status?

.. setting:: HELPDESK_SHOW_MY_TICKETS_IN_NAV_FOR_STAFF

   *Default:* ``True``

   Show "My tickets" for staff. Typically used for help desk deployments that allow staff to create tickets to action other staff members.

.. setting:: HELPDESK_TRANSLATE_TICKET_COMMENTS

   *Default:* ``False``

   Show dropdown list of languages that ticket comments can be translated into via Google Translate?

.. setting:: HELPDESK_TRANSLATE_TICKET_COMMENTS_LANG

   *Default:* ``["en", "de", "fr", "it", "ru"]``

   List of languages to offer. If set to false, all default google translate languages will be shown.

.. setting:: HELPDESK_FOLLOWUP_MOD

   *Default:* ``False``

   Allow user to override default layout for 'followups' (work in progress)

.. setting:: HELPDESK_AUTO_SUBSCRIBE_ON_TICKET_RESPONSE

   *Default:* ``False``

   Auto-subscribe user to ticket as a 'CC' if (s)he responds to a ticket?

.. setting:: HELPDESK_EMAIL_SUBJECT_TEMPLATE

   *Default:* ``"{{ ticket.ticket }} {{ ticket.title|safe }} %(subject)s"``

   Subject template for templated emails. ``%(subject)s`` represents the subject wording from the email template (e.g. "(Closed)").

   .. caution::
      Your subject template should always include a ``{{ ticket.ticket }}`` somewhere as many ``django-helpdesk`` features rely on the ticket ID in the subject line in order to correctly route mail to the corresponding ticket. If you leave out the ticket ID, your helpdesk may not work correctly!

.. setting:: HELPDESK_NOTIFY_SUBMITTER_FOR_ALL_TICKET_CHANGES

   *Default:* ``False``

   Send email to submitter for all ticket updates. Default is to only sends to submitter for followups marked as public (defaults to True) on ticket creation, closing, status changes or followup comment.

.. setting:: HELPDESK_PRIVATE_FOLLOWUP_MEANS_NO_EMAILS

   *Default:* ``False``

   If ``True``, private follow-ups (marked with ``public=False``) will not trigger any email notifications to any recipients (submitters, assigned users, CC'd users, or queue notifications). This provides complete privacy for internal staff communications.
   Public follow-ups (``public=True``) continue to work normally. This setting overrides other notification settings like :setting:`HELPDESK_NOTIFY_SUBMITTER_FOR_ALL_TICKET_CHANGES` when the follow-up is private.

.. setting:: HELPDESK_EMAIL_FALLBACK_LOCALE

   *Default:* ``en``

   Fallback locale for templated emails when queue locale not found

.. setting:: HELPDESK_MAX_EMAIL_ATTACHMENT_SIZE

   *Default:* ``512000``

   Maximum size, in bytes, of file attachments that will be sent via email

.. setting:: QUEUE_EMAIL_BOX_UPDATE_ONLY

   *Default:* ``False``

   Only process mail with a valid tracking ID; all other mail will be ignored instead of creating a new ticket.

.. setting:: HELPDESK_ENABLE_DEPENDENCIES_ON_TICKET

   *Default:* ``True``

   If False, disable the dependencies fields on ticket.

.. setting:: HELPDESK_ENABLE_TIME_SPENT_ON_TICKET

   *Default:* ``True``

   If False, disable the time spent fields on ticket.

.. setting:: HELPDESK_TICKETS_TIMELINE_ENABLED

   *Default:* ``True``

   If False, remove from the dashboard the Timeline view for tickets.


Options shown on public pages
-----------------------------

These options only change display of items on public-facing pages, not staff pages.

.. setting:: HELPDESK_VIEW_A_TICKET_PUBLIC

   *Default:* ``True``

   Show 'View a Ticket' section on public page?

.. setting:: HELPDESK_SUBMIT_A_TICKET_PUBLIC

   *Default:* ``True``

   Show 'submit a ticket' section & form on public page?

.. setting:: HELPDESK_PUBLIC_TICKET_FORM_CLASS

   *Default:* ``helpdesk.forms.PublicTicketForm``

   Define custom form class to show on public pages for anon users. You can use it for adding custom fields and validation, captcha and so on.


Options for public ticket submission form
-----------------------------------------

.. setting:: HELPDESK_PUBLIC_TICKET_QUEUE

   *Default:* Not defined

   Sets the queue for tickets submitted through the public form. If defined, the matching form field will be hidden. This cannot be ``None`` but must be set to a valid queue slug.

.. setting:: HELPDESK_PUBLIC_TICKET_PRIORITY

   *Default:* Not defined

   Sets the priority for tickets submitted through the public form. If defined, the matching form field will be hidden. Must be set to a valid integer priority.

.. setting:: HELPDESK_PUBLIC_TICKET_DUE_DATE

   *Default:* Not defined

   Sets the due date for tickets submitted through the public form. If defined, the matching form field will be hidden. Set to ``None`` if you want to hide the form field but do not want to define a value.


Options that change ticket updates
----------------------------------

.. setting:: HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE

   *Default:* ``False``

   Allow non-staff users to interact with tickets?
   Set to True to allow any authenticated user to manage tickets.
   You can also apply a custom authorisation logic for identifying helpdesk staff members, by setting this to a callable.
   In that case, the value should be a function accepting the active user as a parameter and returning True if the user is considered helpdesk staff, e.g.::

     lambda u: u.is_authenticated() and u.is_active and u.groups.filter(name='helpdesk_staff').exists()

.. setting:: HELPDESK_SHOW_EDIT_BUTTON_FOLLOW_UP

   *Default:* ``True``

   Show edit buttons in ticket follow ups?

.. setting:: HELPDESK_SHOW_DELETE_BUTTON_SUPERUSER_FOLLOW_UP

   *Default:* ``False``

   Show delete buttons in ticket follow ups if user is 'superuser'?

.. setting:: HELPDESK_UPDATE_PUBLIC_DEFAULT

   *Default:* ``False``

   Make all updates public by default? This will hide the 'is this update public' checkbox.

.. setting:: HELPDESK_STAFF_ONLY_TICKET_OWNERS

   *Default:* ``False``

   Only show staff users in ticket owner drop-downs?

.. setting:: HELPDESK_STAFF_ONLY_TICKET_CC

   *Default:* ``False``

   Only show staff users in ticket cc drop-down?

.. setting:: HELPDESK_SHOW_CUSTOM_FIELDS_FOLLOW_UP_LIST

   *Default:* ``[]``

   Show configured custom fields in the follow-up form.

.. setting:: HELPDESK_FOLLOWUP_NEWEST_FIRST

   *Default:* ``False``

   Sets the default order for the follow-up list on the ticket view. If True, the most recent follow up is listed first. If False, the oldest follow up is listed first. Users can still toggle the order from the ticket view using the sort button, regardless of this setting.


Options that change ticket properties
-------------------------------------

.. setting:: HELPDESK_TICKET_OPEN_STATUS

   *Default:* ``1``

   Customize the id of OPEN_STATUS status.

.. setting:: HELPDESK_TICKET_REOPENED_STATUS

   *Default:* ``2``

   Customize the id of REOPENED_STATUS status.

.. setting:: HELPDESK_TICKET_RESOLVED_STATUS

   *Default:* ``3``

   Customize the id of RESOLVED_STATUS status.

.. setting:: HELPDESK_TICKET_CLOSED_STATUS

   *Default:* ``4``

   Customize the id of CLOSED_STATUS status.

.. setting:: HELPDESK_TICKET_DUPLICATE_STATUS

   *Default:* ``5``

   Customize the id of DUPLICATE_STATUS status.

.. setting:: HELPDESK_TICKET_STATUS_CHOICES

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

.. setting:: HELPDESK_TICKET_OPEN_STATUSES

   *Default:* ``(HELPDESK_TICKET_OPEN_STATUS, HELPDESK_TICKET_REOPENED_STATUS)``

   Define the list of statuses to be considered as a type of open status.

   If you have added the ``HELPDESK_TICKET_FORKED_STATUS`` status and wish to have django-helpdesk treat it as an open status choice, add it to the list of OPEN_STATUSES like this::

     HELPDESK_TICKET_OPEN_STATUSES = (HELPDESK_TICKET_OPEN_STATUS,
                                      HELPDESK_TICKET_REOPENED_STATUS,
                                      HELPDESK_TICKET_FORKED_STATUS)

.. setting:: HELPDESK_TICKET_STATUS_CHOICES_FLOW

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

.. setting:: HELPDESK_TICKET_STATUS_CSS_CLASSES

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

.. setting:: HELPDESK_TICKET_PRIORITY_CHOICES

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

.. setting:: HELPDESK_TICKET_PRIORITY_CSS_CLASSES

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

.. setting:: HELPDESK_FOLLOWUP_TIME_SPENT_AUTO

   *Default:* ``False``

   If ``True``, calculate follow-up 'time_spent' with previous follow-up or ticket creation time.

.. setting:: HELPDESK_FOLLOWUP_TIME_SPENT_OPENING_HOURS

   *Default:* ``{}``

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

.. setting:: HELPDESK_FOLLOWUP_TIME_SPENT_EXCLUDE_HOLIDAYS

   *Default:* ``()``

   List of days in format ``%Y-%m-%d`` to exclude from automatic follow-up 'time_spent' calculation.

   This example removes Christmas and New Year's Eve in 2024::

     HELPDESK_FOLLOWUP_TIME_SPENT_EXCLUDE_HOLIDAYS = ("2024-12-25", "2024-12-31",)

.. setting:: HELPDESK_FOLLOWUP_TIME_SPENT_EXCLUDE_STATUSES

   *Default:* ``()``

   List of ticket statuses to exclude from automatic follow-up 'time_spent' calculation.

   This example will have follow-ups to resolved ticket status not to be counted in::

     HELPDESK_FOLLOWUP_TIME_SPENT_EXCLUDE_STATUSES = (HELPDESK_TICKET_RESOLVED_STATUS,)

.. setting:: HELPDESK_FOLLOWUP_TIME_SPENT_EXCLUDE_QUEUES

   *Default:* ``()``

   List of ticket queues slugs to exclude from automatic follow-up 'time_spent' calculation.

   This example will have follow-ups excluded from time calculation if they belong to the queue with slug ``time-not-counting-queue``::

     HELPDESK_FOLLOWUP_TIME_SPENT_EXCLUDE_QUEUES = ('time-not-counting-queue',)


Staff Ticket Creation Settings
------------------------------

.. setting:: HELPDESK_CREATE_TICKET_HIDE_ASSIGNED_TO

   *Default:* ``False``

   Hide the 'assigned to' / 'Case owner' field from the 'create_ticket' view? It'll still show on the ticket detail/edit form.


Staff Ticket View Settings
------------------------------

.. setting:: HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION

   *Default:* ``False``

   If ``True``, logged in staff users only see queues and tickets to which they have specifically been granted access -  this holds for the dashboard, ticket query, and ticket report views. User assignment is done through the standard ``django.admin.admin`` permissions.

   .. note::
      Staff with access to admin interface will be able to see the full list of tickets, but won't have access to details and could not modify them. This setting does not prevent staff users from creating tickets for all queues. Also, superuser accounts have full access to all queues, regardless of whatever queue memberships they have been granted.


Default E-Mail Settings
-----------------------

The following settings default to ``None`` but can be set as defaults, rather than setting them per-queue.

.. setting:: QUEUE_EMAIL_BOX_TYPE

   Protocol used: ``pop3``, ``imap`` or ``oauth``.

.. setting:: QUEUE_EMAIL_BOX_SSL

   Set to ``True`` to use SSL, otherwise ``False``.

.. setting:: QUEUE_EMAIL_BOX_HOST

   The URL of the mail server.

.. setting:: QUEUE_EMAIL_BOX_USER

   The ``username`` of the email account.

.. setting:: QUEUE_EMAIL_BOX_PASSWORD

   The ``password`` of the email account.

   If ``oauth`` is used, configure ``HELPDESK_OAUTH``::

     HELPDESK_OAUTH = {
         "token_url": "",
         "client_id": "",
         "secret": "",
         "scope": [""],
     }

.. setting:: HELPDESK_IMAP_DEBUG_LEVEL

   *Default:* ``0``

   If using ``imap`` or ``oauth``, set the IMAP debug logging level. Default: ``0`` (no debugging).


Discontinued Settings
---------------------
The following settings were defined in previous versions and are no longer supported.

.. setting:: HELPDESK_CUSTOM_WELCOME

.. setting:: HELDPESK_KB_ENABLED_STAFF

   Now always True

.. setting:: HELPDESK_NAVIGATION_STATS_ENABLED

   Now always True

.. setting:: HELPDESK_PREPEND_ORG_NAME

   Please customise your local ``helpdesk/base.html`` template if needed

.. setting:: HELPDESK_SHOW_DELETE_BUTTON_TICKET_TOP

   Button is always shown

.. setting:: HELPDESK_SHOW_EDIT_BUTTON_TICKET_TOP

   Button is always shown

.. setting:: HELPDESK_SHOW_HOLD_BUTTON_TICKET_TOP

   Button is always shown

.. setting:: HELPDESK_SHOW_KB_ON_HOMEPAGE

   KB categories are always shown on the homepage

.. setting:: HELPDESK_SUPPORT_PERSON

   Please customise your local ``helpdesk/attribution.html`` template if needed

.. setting:: HELPDESK_DASHBOARD_SHOW_DELETE_UNASSIGNED

   Button is always shown

.. setting:: HELPDESK_DASHBOARD_HIDE_EMPTY_QUEUES

   Empty queues are always hidden

.. setting:: HELPDESK_DASHBOARD_BASIC_TICKET_STATS

   Stats are always shown

.. setting:: HELPDESK_FOOTER_SHOW_API_LINK

   Link to API documentation is always shown. Edit your local ``helpdesk/base.html`` template if needed.

.. setting:: HELPDESK_FOOTER_SHOW_CHANGE_LANGUAGE_LINK

   Is never shown. Use your own template if required.

.. setting:: HELPDESK_ENABLE_PER_QUEUE_MEMBERSHIP

   Discontinued in favor of :setting:`HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION`.

.. setting:: HELPDESK_FULL_FIRST_MESSAGE_FROM_EMAIL

   Do not ignore fowarded and replied text from the email messages which create a new ticket; useful for cases when customer forwards some email (error from service or something) and wants support to see that

