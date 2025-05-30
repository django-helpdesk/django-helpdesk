"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008-2025 Jutda. All Rights Reserved. See LICENSE for details.

models.py - Model (and hence database) definitions. This is the core of the
            helpdesk structure.
"""

from helpdesk import settings as helpdesk_settings
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
import os

from . import FollowUp, Attachment


class FollowUpAttachment(Attachment):
    followup = models.ForeignKey(
        FollowUp,
        on_delete=models.CASCADE,
        verbose_name=_("Follow-up"),
    )

    def attachment_path(self, filename):
        path = "helpdesk/attachments/{ticket_for_url}-{secret_key}/{id_}".format(
            ticket_for_url=self.followup.ticket.ticket_for_url,
            secret_key=self.followup.ticket.secret_key,
            id_=self.followup.id,
        )
        att_path = os.path.join(settings.MEDIA_ROOT, path)
        if settings.STORAGES == "django.core.files.storage.FileSystemStorage":
            if not os.path.exists(att_path):
                os.makedirs(att_path, helpdesk_settings.HELPDESK_ATTACHMENT_DIR_PERMS)
        return os.path.join(path, filename)
