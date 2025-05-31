"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008-2025 Jutda. All Rights Reserved. See LICENSE for details.

models.py - Model (and hence database) definitions. This is the core of the
            helpdesk structure.
"""

from markdown import markdown
from django.utils.safestring import mark_safe
import re
from helpdesk import settings as helpdesk_settings

from .EscapeHtml import EscapeHtml


def get_markdown(text):
    """
    This algorithm will check for illegal schemes used in markdown clickable links
    and remove the scheme. It does an iterative retry until no replacements done to
    account for embedded schemes in the replacement text.
    It will then do markdown processing to ensure safe markdown and return the safe string.
    """
    if not text:
        return ""

    # Search for markdown that creates a clickable link and remove the undesirable ones
    pattern = re.compile(r"(\[[\s\S]*?\])\(([\w]*?):([\s\S]*?)\)", flags=re.MULTILINE)
    rerun_scheme_check = (
        True  # Used to decide if a re-check should be done after last pass
    )
    while rerun_scheme_check:
        has_illegal_scheme = False
        for m in re.finditer(pattern, text):
            # check if scheme is allowed
            if m.group(2).lower() in helpdesk_settings.ALLOWED_URL_SCHEMES:
                # Considered safe so don't change it.
                continue
            # Remove the scheme and leave the rest
            text = text.replace(m.group(0), f"{m.group(1)}({m.group(3)})")
            has_illegal_scheme = True
        rerun_scheme_check = has_illegal_scheme
    return mark_safe(
        markdown(
            text,
            extensions=[
                EscapeHtml(),
                "markdown.extensions.nl2br",
                "markdown.extensions.fenced_code",
            ],
        )
    )
