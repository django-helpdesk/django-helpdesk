"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008-2025 Jutda. All Rights Reserved. See LICENSE for details.

models.py - Model (and hence database) definitions. This is the core of the
            helpdesk structure.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
import mimetypes

from ..validators import validate_file_extension
from . import attachment_path


class Attachment(models.Model):
    """
    Represents a file attached to a follow-up. This could come from an e-mail
    attachment, or it could be uploaded via the web interface.
    """

    file = models.FileField(
        _("File"),
        upload_to=attachment_path,
        max_length=1000,
        validators=[validate_file_extension],
    )

    filename = models.CharField(
        _("Filename"),
        blank=True,
        max_length=1000,
    )

    mime_type = models.CharField(
        _("MIME Type"),
        blank=True,
        max_length=255,
    )

    size = models.IntegerField(
        _("Size"),
        blank=True,
        help_text=_("Size of this file in bytes"),
    )

    def __str__(self):
        return "%s" % self.filename

    def save(self, *args, **kwargs):
        if not self.size:
            self.size = self.get_size()

        if not self.filename:
            self.filename = self.get_filename()

        if not self.mime_type:
            self.mime_type = (
                mimetypes.guess_type(self.filename, strict=False)[0]
                or "application/octet-stream"
            )

        return super(Attachment, self).save(*args, **kwargs)

    def get_filename(self):
        return str(self.file)

    def get_size(self):
        return self.file.file.size

    def attachment_path(self, filename):
        """Provide a file path that will help prevent files being overwritten, by
        putting attachments in a folder off attachments for ticket/followup_id/.
        """
        assert NotImplementedError(
            "This method is to be implemented by Attachment classes"
        )

    class Meta:
        ordering = ("filename",)
        verbose_name = _("Attachment")
        verbose_name_plural = _("Attachments")
        abstract = True
