# validators.py
#
# validators for file uploads, etc.

import os

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from helpdesk import settings as helpdesk_settings


def validate_file_extension(value):
    """Refuse attachments whose extension is not in HELPDESK_VALID_EXTENSIONS.

    Trailing dots and spaces are ignored when reading the extension, since
    some web servers derive the content type from every dot-separated part of
    the name: `payload.html.` is checked as `.html`. A name without an
    extension is refused, because it may be served with no content type and
    left to the browser to guess.
    """
    if not helpdesk_settings.HELPDESK_VALIDATE_ATTACHMENT_TYPES:
        return

    name = os.path.basename(value.name).rstrip(". ")
    ext = os.path.splitext(name)[1].lower()
    if not ext:
        raise ValidationError(_("Attachments must have a file extension."))
    if ext not in helpdesk_settings.HELPDESK_VALID_EXTENSIONS:
        raise ValidationError(_("Unsupported file extension: ") + ext)
