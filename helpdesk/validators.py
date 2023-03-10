# validators.py
#
# validators for file uploads, etc.


from django.conf import settings
from django.utils.translation import gettext as _


# TODO: can we use the builtin Django validator instead?
# see:
# https://docs.djangoproject.com/en/4.0/ref/validators/#fileextensionvalidator


def validate_file_extension(value):
    from django.core.exceptions import ValidationError
    import os
    ext = os.path.splitext(value.name)[1]  # [0] returns path+filename
    # TODO: we might improve this with more thorough checks of file types
    # rather than just the extensions.

    # check if VALID_EXTENSIONS is defined in settings.py
    # if not use defaults

    if hasattr(settings, 'VALID_EXTENSIONS'):
        valid_extensions = settings.VALID_EXTENSIONS
    else:
        valid_extensions = ['.txt', '.asc', '.htm', '.html',
                            '.pdf', '.doc', '.docx', '.odt', '.jpg', '.png', '.eml']

    if not ext.lower() in valid_extensions:
        # TODO: one more check in case it is a file with no extension; we
        # should always allow that?
        if not (ext.lower() == '' or ext.lower() == '.'):
            raise ValidationError(
                _('Unsupported file extension: ') + ext.lower()
            )
