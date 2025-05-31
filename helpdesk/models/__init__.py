"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008-2025 Jutda. All Rights Reserved. See LICENSE for details.

models.py - Model (and hence database) definitions. This is the core of the
            helpdesk structure.
"""

from .Attachment import Attachment
from .Checklist import Checklist
from .ChecklistTask import ChecklistTask
from .ChecklistTemplate import ChecklistTemplate, is_a_list_without_empty_element
from .CustomField import CustomField
from .EmailTemplate import EmailTemplate
from .EscalationExclusion import EscalationExclusion
from .EscapeHtml import EscapeHtml
from .FollowUp import FollowUp
from .IgnoreEmail import IgnoreEmail
from .KBCategory import KBCategory
from .KBIAttachment import KBIAttachment
from .KBItem import KBItem
from .PreSetReply import PreSetReply
from .Queue import Queue
from .SavedSearch import SavedSearch
from .Ticket import Ticket
from .TicketCC import TicketCC
from .TicketChange import TicketChange
from .TicketCustomFieldValue import TicketCustomFieldValue
from .TicketDependency import TicketDependency
from .UserSettings import UserSettings

from .ChecklistTaskQuerySet import ChecklistTaskQuerySet
from .CustomFieldManager import CustomFieldManager
from .FollowUpManager import FollowUpManager
from .FollowUpAttachment import FollowUpAttachment

# utility functions or settings if they are part of your
from .attachment_path import attachment_path
from .create_usersettings import create_usersettings
from .email_on_ticket_assign_default import email_on_ticket_assign_default
from .email_on_ticket_change_default import email_on_ticket_change_default
from .get_default_setting import get_default_setting
from .get_markdown import get_markdown
from .login_view_ticketlist_default import login_view_ticketlist_default
from .mk_secret import mk_secret
from .tickets_per_page_default import tickets_per_page_default
from .use_email_as_submitter_default import use_email_as_submitter_default


__all__ = [
    "Attachment",
    "Checklist",
    "ChecklistTask",
    "ChecklistTemplate",
    "CustomField",
    "EmailTemplate",
    "EscalationExclusion",
    "FollowUp",
    "IgnoreEmail",
    "KBCategory",
    "KBIAttachment",
    "KBItem",
    "PreSetReply",
    "Queue",
    "SavedSearch",
    "Ticket",
    "TicketCC",
    "TicketChange",
    "TicketCustomFieldValue",
    "TicketDependency",
    "UserSettings",
    "ChecklistTaskQuerySet",
    "CustomFieldManager",
    "FollowUpManager",
    "attachment_path",
    "create_usersettings",
    "email_on_ticket_assign_default",
    "email_on_ticket_change_default",
    "EscapeHtml",
    "get_default_setting",
    "get_markdown",
    "login_view_ticketlist_default",
    "mk_secret",
    "tickets_per_page_default",
    "use_email_as_submitter_default",
    "is_a_list_without_empty_element",
    "FollowUpAttachment",
]
