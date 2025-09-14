"""
Default settings for django-helpdesk.

"""

from django import forms
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _
import os
import re
import warnings
import sys


DEFAULT_USER_SETTINGS = {
    "login_view_ticketlist": True,
    "email_on_ticket_change": True,
    "email_on_ticket_assign": True,
    "tickets_per_page": 25,
    "use_email_as_submitter": True,
}

try:
    DEFAULT_USER_SETTINGS.update(settings.HELPDESK_DEFAULT_SETTINGS)
except AttributeError:
    pass


HAS_TAG_SUPPORT = False

# Use international timezones
USE_TZ: bool = True

# check for secure cookie support
if os.environ.get("SECURE_PROXY_SSL_HEADER"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

##########################################
# generic options - visible on all pages #
##########################################

# redirect to login page instead of the default homepage when users visits "/"?
HELPDESK_REDIRECT_TO_LOGIN_BY_DEFAULT = getattr(
    settings, "HELPDESK_REDIRECT_TO_LOGIN_BY_DEFAULT", False
)

HELPDESK_PUBLIC_VIEW_PROTECTOR = getattr(
    settings,
    "HELPDESK_PUBLIC_VIEW_PROTECTOR",
    lambda _: None,  # noqa
)

HELPDESK_STAFF_VIEW_PROTECTOR = getattr(
    settings,
    "HELPDESK_STAFF_VIEW_PROTECTOR",
    lambda _: None,  # noqa
)

# Enable ticket and Email attachments
#
# Caution! Set this to False, unless you have secured access to
#   the uploaded files. Otherwise anyone on the Internet will be
#   able to download your ticket attachments.
HELPDESK_ENABLE_ATTACHMENTS = getattr(settings, "HELPDESK_ENABLE_ATTACHMENTS", True)

# Enable the Dependencies field on ticket view
HELPDESK_ENABLE_DEPENDENCIES_ON_TICKET = getattr(
    settings, "HELPDESK_ENABLE_DEPENDENCIES_ON_TICKET", True
)

# Enable the Time spent on field on ticket view
HELPDESK_ENABLE_TIME_SPENT_ON_TICKET = getattr(
    settings, "HELPDESK_ENABLE_TIME_SPENT_ON_TICKET", True
)

# raises a 404 to anon users. It's like it was invisible
HELPDESK_ANON_ACCESS_RAISES_404 = getattr(
    settings, "HELPDESK_ANON_ACCESS_RAISES_404", False
)

# Disable Timeline on ticket list
HELPDESK_TICKETS_TIMELINE_ENABLED = getattr(
    settings, "HELPDESK_TICKETS_TIMELINE_ENABLED", True
)

# show extended navigation by default, to all users, irrespective of staff
# status?
HELPDESK_NAVIGATION_ENABLED = getattr(settings, "HELPDESK_NAVIGATION_ENABLED", False)

# Show the "My Tickets" navigation option for staff members - typically this is for when
# staff can create tickets to action other staff.
HELPDESK_SHOW_MY_TICKETS_IN_NAV_FOR_STAFF = getattr(
    settings, "HELPDESK_SHOW_MY_TICKETS_IN_NAV_FOR_STAFF", True
)

# use public CDNs to serve jquery and other javascript by default?
# otherwise, use built-in static copy
HELPDESK_USE_CDN = getattr(settings, "HELPDESK_USE_CDN", False)

# show dropdown list of languages that ticket comments can be translated into?
HELPDESK_TRANSLATE_TICKET_COMMENTS = getattr(
    settings, "HELPDESK_TRANSLATE_TICKET_COMMENTS", False
)

# list of languages to offer. if set to false,
# all default google translate languages will be shown.
HELPDESK_TRANSLATE_TICKET_COMMENTS_LANG = getattr(
    settings,
    "HELPDESK_TRANSLATE_TICKET_COMMENTS_LANG",
    ["en", "de", "es", "fr", "it", "ru"],
)

# show link to 'change password' on 'User Settings' page?
HELPDESK_SHOW_CHANGE_PASSWORD = getattr(
    settings, "HELPDESK_SHOW_CHANGE_PASSWORD", False
)

# allow user to override default layout for 'followups' - work in progress.
HELPDESK_FOLLOWUP_MOD = getattr(settings, "HELPDESK_FOLLOWUP_MOD", False)

# auto-subscribe user to ticket if (s)he responds to a ticket?
HELPDESK_AUTO_SUBSCRIBE_ON_TICKET_RESPONSE = getattr(
    settings, "HELPDESK_AUTO_SUBSCRIBE_ON_TICKET_RESPONSE", False
)

# URL schemes that are allowed within links
ALLOWED_URL_SCHEMES = getattr(
    settings,
    "ALLOWED_URL_SCHEMES",
    (
        "file",
        "ftp",
        "ftps",
        "http",
        "https",
        "irc",
        "mailto",
        "sftp",
        "ssh",
        "tel",
        "telnet",
        "tftp",
        "vnc",
        "xmpp",
    ),
)

# Ticket status choices
OPEN_STATUS = getattr(settings, "HELPDESK_TICKET_OPEN_STATUS", 1)
REOPENED_STATUS = getattr(settings, "HELPDESK_TICKET_REOPENED_STATUS", 2)
RESOLVED_STATUS = getattr(settings, "HELPDESK_TICKET_RESOLVED_STATUS", 3)
CLOSED_STATUS = getattr(settings, "HELPDESK_TICKET_CLOSED_STATUS", 4)
DUPLICATE_STATUS = getattr(settings, "HELPDESK_TICKET_DUPLICATE_STATUS", 5)

DEFAULT_TICKET_STATUS_CHOICES = (
    (OPEN_STATUS, _("Open")),
    (REOPENED_STATUS, _("Reopened")),
    (RESOLVED_STATUS, _("Resolved")),
    (CLOSED_STATUS, _("Closed")),
    (DUPLICATE_STATUS, _("Duplicate")),
)
TICKET_STATUS_CHOICES = getattr(
    settings, "HELPDESK_TICKET_STATUS_CHOICES", DEFAULT_TICKET_STATUS_CHOICES
)

# List of status choices considered as "open"
DEFAULT_TICKET_OPEN_STATUSES = (OPEN_STATUS, REOPENED_STATUS)
TICKET_OPEN_STATUSES = getattr(
    settings, "HELPDESK_TICKET_OPEN_STATUSES", DEFAULT_TICKET_OPEN_STATUSES
)

# New status list choices depending on current ticket status
DEFAULT_TICKET_STATUS_CHOICES_FLOW = {
    OPEN_STATUS: (
        OPEN_STATUS,
        RESOLVED_STATUS,
        CLOSED_STATUS,
        DUPLICATE_STATUS,
    ),
    REOPENED_STATUS: (
        REOPENED_STATUS,
        RESOLVED_STATUS,
        CLOSED_STATUS,
        DUPLICATE_STATUS,
    ),
    RESOLVED_STATUS: (
        REOPENED_STATUS,
        RESOLVED_STATUS,
        CLOSED_STATUS,
    ),
    CLOSED_STATUS: (
        REOPENED_STATUS,
        CLOSED_STATUS,
    ),
    DUPLICATE_STATUS: (
        REOPENED_STATUS,
        DUPLICATE_STATUS,
    ),
}
TICKET_STATUS_CHOICES_FLOW = getattr(
    settings, "HELPDESK_TICKET_STATUS_CHOICES_FLOW", DEFAULT_TICKET_STATUS_CHOICES_FLOW
)

# Ticket priority choices
DEFAULT_TICKET_PRIORITY_CHOICES = (
    (1, _("1. Critical")),
    (2, _("2. High")),
    (3, _("3. Normal")),
    (4, _("4. Low")),
    (5, _("5. Very Low")),
)
TICKET_PRIORITY_CHOICES = getattr(
    settings, "HELPDESK_TICKET_PRIORITY_CHOICES", DEFAULT_TICKET_PRIORITY_CHOICES
)


#########################
# time tracking options #
#########################

# Follow-ups automatic time_spent calculation
FOLLOWUP_TIME_SPENT_AUTO = getattr(settings, "HELPDESK_FOLLOWUP_TIME_SPENT_AUTO", False)

# Calculate time_spent according to open hours
FOLLOWUP_TIME_SPENT_OPENING_HOURS = getattr(
    settings, "HELPDESK_FOLLOWUP_TIME_SPENT_OPENING_HOURS", {}
)

# Holidays don't count for time_spent calculation
FOLLOWUP_TIME_SPENT_EXCLUDE_HOLIDAYS = getattr(
    settings, "HELPDESK_FOLLOWUP_TIME_SPENT_EXCLUDE_HOLIDAYS", ()
)

# Time doesn't count for listed ticket statuses
FOLLOWUP_TIME_SPENT_EXCLUDE_STATUSES = getattr(
    settings, "HELPDESK_FOLLOWUP_TIME_SPENT_EXCLUDE_STATUSES", ()
)

# Time doesn't count for listed queues slugs
FOLLOWUP_TIME_SPENT_EXCLUDE_QUEUES = getattr(
    settings, "HELPDESK_FOLLOWUP_TIME_SPENT_EXCLUDE_QUEUES", ()
)

############################
# options for public pages #
############################

# show 'view a ticket' section on public page?
HELPDESK_VIEW_A_TICKET_PUBLIC = getattr(settings, "HELPDESK_VIEW_A_TICKET_PUBLIC", True)

# show 'submit a ticket' section on public page?
HELPDESK_SUBMIT_A_TICKET_PUBLIC = getattr(
    settings, "HELPDESK_SUBMIT_A_TICKET_PUBLIC", True
)

# change that to custom class to have extra fields or validation (like captcha)
HELPDESK_PUBLIC_TICKET_FORM_CLASS = getattr(
    settings, "HELPDESK_PUBLIC_TICKET_FORM_CLASS", "helpdesk.forms.PublicTicketForm"
)

# Custom fields constants
CUSTOMFIELD_TO_FIELD_DICT = {
    "boolean": forms.BooleanField,
    "date": forms.DateField,
    "time": forms.TimeField,
    "datetime": forms.DateTimeField,
    "email": forms.EmailField,
    "url": forms.URLField,
    "ipaddress": forms.GenericIPAddressField,
    "slug": forms.SlugField,
}
CUSTOMFIELD_DATE_FORMAT = "%Y-%m-%d"
CUSTOMFIELD_TIME_FORMAT = "%H:%M:%S"
CUSTOMFIELD_DATETIME_FORMAT = f"{CUSTOMFIELD_DATE_FORMAT}T%H:%M"


###################################
# options for update_ticket views #
###################################

""" options for update_ticket views """
# allow non-staff users to interact with tickets?
# can be True/False or a callable accepting the active user and returning
# True if they must be considered helpdesk staff
HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE = getattr(
    settings, "HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE", False
)
if not (
    HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE in (True, False)
    or callable(HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE)
):
    warnings.warn(
        "HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE should be set to either True/False or a callable.",
        RuntimeWarning,
    )

# show edit buttons in ticket follow ups.
HELPDESK_SHOW_EDIT_BUTTON_FOLLOW_UP = getattr(
    settings, "HELPDESK_SHOW_EDIT_BUTTON_FOLLOW_UP", True
)

HELPDESK_SHOW_CUSTOM_FIELDS_FOLLOW_UP_LIST = getattr(
    settings, "HELPDESK_SHOW_CUSTOM_FIELDS_FOLLOW_UP_LIST", []
)

# show delete buttons in ticket follow ups if user is 'superuser'
HELPDESK_SHOW_DELETE_BUTTON_SUPERUSER_FOLLOW_UP = getattr(
    settings, "HELPDESK_SHOW_DELETE_BUTTON_SUPERUSER_FOLLOW_UP", False
)

# make all updates public by default? this will hide the 'is this update
# public' checkbox
HELPDESK_UPDATE_PUBLIC_DEFAULT = getattr(
    settings, "HELPDESK_UPDATE_PUBLIC_DEFAULT", False
)

# only show staff users in ticket owner drop-downs
HELPDESK_STAFF_ONLY_TICKET_OWNERS = getattr(
    settings, "HELPDESK_STAFF_ONLY_TICKET_OWNERS", False
)

# only show staff users in ticket cc drop-down
HELPDESK_STAFF_ONLY_TICKET_CC = getattr(
    settings, "HELPDESK_STAFF_ONLY_TICKET_CC", False
)

# allow the subject to have a configurable template.
HELPDESK_EMAIL_SUBJECT_TEMPLATE = getattr(
    settings,
    "HELPDESK_EMAIL_SUBJECT_TEMPLATE",
    "{{ ticket.ticket }} {{ ticket.title|safe }} %(subject)s",
)
# since django-helpdesk may not work correctly without the ticket ID
# in the subject, let's do a check for it quick:
if HELPDESK_EMAIL_SUBJECT_TEMPLATE.find("ticket.ticket") < 0:
    raise ImproperlyConfigured

# default fallback locale when queue locale not found
HELPDESK_EMAIL_FALLBACK_LOCALE = getattr(
    settings, "HELPDESK_EMAIL_FALLBACK_LOCALE", "en"
)

# default maximum email attachment size, in bytes
# only attachments smaller than this size will be sent via email
HELPDESK_MAX_EMAIL_ATTACHMENT_SIZE = getattr(
    settings, "HELPDESK_MAX_EMAIL_ATTACHMENT_SIZE", 512000
)

# Send email notifications for internal ticket submitter.
HELPDESK_NOTIFY_SUBMITTER_FOR_ALL_TICKET_CHANGES = getattr(
    settings,
    "HELPDESK_NOTIFY_SUBMITTER_FOR_ALL_TICKET_CHANGES",
    False,
)

# If True, private follow-ups (public=False) will not trigger any email notifications
HELPDESK_PRIVATE_FOLLOWUP_MEANS_NO_EMAILS = getattr(
    settings, "HELPDESK_PRIVATE_FOLLOWUP_MEANS_NO_EMAILS", False
)

########################################
# options for staff.create_ticket view #
########################################

# hide the 'assigned to' / 'Case owner' field from the 'create_ticket' view?
HELPDESK_CREATE_TICKET_HIDE_ASSIGNED_TO = getattr(
    settings, "HELPDESK_CREATE_TICKET_HIDE_ASSIGNED_TO", False
)

#################
# email options #
#################

# default Queue email submission settings
QUEUE_EMAIL_BOX_TYPE = getattr(settings, "QUEUE_EMAIL_BOX_TYPE", None)
QUEUE_EMAIL_BOX_SSL = getattr(settings, "QUEUE_EMAIL_BOX_SSL", None)
QUEUE_EMAIL_BOX_HOST = getattr(settings, "QUEUE_EMAIL_BOX_HOST", None)
QUEUE_EMAIL_BOX_USER = getattr(settings, "QUEUE_EMAIL_BOX_USER", None)
QUEUE_EMAIL_BOX_PASSWORD = getattr(settings, "QUEUE_EMAIL_BOX_PASSWORD", None)

# only process emails with a valid tracking ID? (throws away all other mail)
QUEUE_EMAIL_BOX_UPDATE_ONLY = getattr(settings, "QUEUE_EMAIL_BOX_UPDATE_ONLY", False)

# only allow users to access queues that they are members of?
HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION = getattr(
    settings, "HELPDESK_ENABLE_PER_QUEUE_STAFF_PERMISSION", False
)

# use https in the email links
HELPDESK_USE_HTTPS_IN_EMAIL_LINK = getattr(
    settings, "HELPDESK_USE_HTTPS_IN_EMAIL_LINK", settings.SECURE_SSL_REDIRECT
)

# Default to True for backwards compatibility
HELPDESK_TEAMS_MODE_ENABLED = getattr(settings, "HELPDESK_TEAMS_MODE_ENABLED", True)
if HELPDESK_TEAMS_MODE_ENABLED:
    HELPDESK_TEAMS_MODEL = getattr(settings, "HELPDESK_TEAMS_MODEL", "pinax_teams.Team")
    HELPDESK_TEAMS_MIGRATION_DEPENDENCIES = getattr(
        settings,
        "HELPDESK_TEAMS_MIGRATION_DEPENDENCIES",
        [("pinax_teams", "0004_auto_20170511_0856")],
    )
    HELPDESK_KBITEM_TEAM_GETTER = getattr(
        settings, "HELPDESK_KBITEM_TEAM_GETTER", lambda kbitem: kbitem.team
    )
else:
    HELPDESK_TEAMS_MODEL = settings.AUTH_USER_MODEL
    HELPDESK_TEAMS_MIGRATION_DEPENDENCIES = []
    HELPDESK_KBITEM_TEAM_GETTER = lambda _: None  # noqa

# show knowledgebase links?
# If Teams mode is enabled then it has to be on
HELPDESK_KB_ENABLED = (
    True
    if HELPDESK_TEAMS_MODE_ENABLED
    else getattr(settings, "HELPDESK_KB_ENABLED", True)
)

# If set then we always save incoming emails as .eml attachments
# which is quite noisy but very helpful for complicated markup, forwards and so on
# (which gets stripped/corrupted otherwise)
HELPDESK_ALWAYS_SAVE_INCOMING_EMAIL_MESSAGE = getattr(
    settings, "HELPDESK_ALWAYS_SAVE_INCOMING_EMAIL_MESSAGE", False
)

#######################
# email OAUTH         #
#######################

HELPDESK_OAUTH = getattr(
    settings,
    "HELPDESK_OAUTH",
    {"token_url": "", "client_id": "", "secret": "", "scope": [""]},
)

# Set Debug Logging Level for IMAP Services. Default to '0' for No Debugging
HELPDESK_IMAP_DEBUG_LEVEL = getattr(settings, "HELPDESK_IMAP_DEBUG_LEVEL", 0)

#############################################
# file permissions - Attachment directories #
#############################################

# Attachment directories should be created with permission 755 (rwxr-xr-x)
# Override it in your own Django settings.py
HELPDESK_ATTACHMENT_DIR_PERMS = int(
    getattr(settings, "HELPDESK_ATTACHMENT_DIR_PERMS", "755"), 8
)

HELPDESK_VALID_EXTENSIONS = getattr(settings, "VALID_EXTENSIONS", None)
if HELPDESK_VALID_EXTENSIONS:
    # Print to stderr
    print(
        "VALID_EXTENSIONS is deprecated, use HELPDESK_VALID_EXTENSIONS instead",
        file=sys.stderr,
    )
else:
    HELPDESK_VALID_EXTENSIONS = getattr(
        settings,
        "HELPDESK_VALID_EXTENSIONS",
        [
            ".txt",
            ".asc",
            ".htm",
            ".html",
            ".pdf",
            ".doc",
            ".docx",
            ".odt",
            ".jpg",
            ".png",
            ".eml",
        ],
    )

HELPDESK_VALIDATE_ATTACHMENT_TYPES = getattr(
    settings, "HELPDESK_VALIDATE_ATTACHMENT_TYPES", True
)


def get_followup_webhook_urls():
    urls = os.environ.get("HELPDESK_FOLLOWUP_WEBHOOK_URLS", None)
    if urls:
        return re.split(r"[\s],[\s]", urls)


HELPDESK_GET_FOLLOWUP_WEBHOOK_URLS = getattr(
    settings, "HELPDESK_GET_FOLLOWUP_WEBHOOK_URLS", get_followup_webhook_urls
)


def get_new_ticket_webhook_urls():
    urls = os.environ.get("HELPDESK_NEW_TICKET_WEBHOOK_URLS", None)
    if urls:
        return urls.split(",")


HELPDESK_GET_NEW_TICKET_WEBHOOK_URLS = getattr(
    settings, "HELPDESK_GET_NEW_TICKET_WEBHOOK_URLS", get_new_ticket_webhook_urls
)

HELPDESK_WEBHOOK_TIMEOUT = getattr(settings, "HELPDESK_WEBHOOK_TIMEOUT", 3)


LOG_WARN_WHEN_CC_EMAIL_NOT_LINKED_TO_A_USER = getattr(
    settings, "HELPDESK_LOG_WARN_WHEN_CC_EMAIL_NOT_LINKED_TO_A_USER", False
)
LOG_WARN_WHEN_CC_EMAIL_LINKED_TO_MORE_THAN_1_USER = getattr(
    settings, "HELPDESK_LOG_WARN_WHEN_CC_EMAIL_LINKED_TO_MORE_THAN_1_USER", True
)
HELPDESK_API_ENABLED = getattr(settings, "HELPDESK_API_ENABLED", True)
