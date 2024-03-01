# validators.py
#
# validators for file uploads, etc.

from django.utils.translation import gettext as _
from helpdesk import settings as helpdesk_settings


# TODO: can we use the builtin Django validator instead?
# see:
# https://docs.djangoproject.com/en/4.0/ref/validators/#fileextensionvalidator


def validate_file_extension(value):
    from django.core.exceptions import ValidationError
    import os
    ext = os.path.splitext(value.name)[1]  # [0] returns path+filename
    # TODO: we might improve this with more thorough checks of file types
    # rather than just the extensions.

    if not helpdesk_settings.HELPDESK_VALIDATE_ATTACHMENT_TYPES:
        return

    if ext.lower() not in helpdesk_settings.HELPDESK_VALID_EXTENSIONS:
        # TODO: one more check in case it is a file with no extension; we
        # should always allow that?
        if not (ext.lower() == '' or ext.lower() == '.'):
            raise ValidationError(
                _('Unsupported file extension: ') + ext.lower()
            )
