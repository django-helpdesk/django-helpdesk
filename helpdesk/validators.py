# validators.py
#
# validators for file uploads, etc.



def validate_file_extension(value):
    import os
    from django.core.exceptions import ValidationError
    ext = os.path.splitext(value.name)[1]  # [0] returns path+filename
    valid_extensions = ['.txt', '.pdf', '.doc', '.docx', '.odt', '.jpg', '.png']
    # TODO: we might improve this with more thorough checks of file types
    # rather than just the extensions.
    if not ext.lower() in valid_extensions:
        raise ValidationError('Unsupported file extension.')
