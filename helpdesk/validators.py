# validators.py
#
# validators for file uploads, etc.

from django.conf import settings

def validate_file_extension(value):
    import os
    from django.core.exceptions import ValidationError
    ext = os.path.splitext(value.name)[1]  # [0] returns path+filename
    # TODO: we might improve this with more thorough checks of file types
    # rather than just the extensions.

    # check if VALID_EXTENSTIONS is defined in settings.py
    # if not use defaults

    if settings.VALID_EXTENSTIONS:
        valid_extenstions = settings.VALID_EXTENSTIONS
    else:
        valid_extenstions = ['.txt', '.pdf', '.doc', '.docx', '.odt', '.jpg', '.png']

    if not ext.lower() in valid_extenstions:
        raise ValidationError('Unsupported file extension.')
