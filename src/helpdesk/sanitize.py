"""
Sanitization for the one place where django-helpdesk deliberately turns
third-party markup back into rendered HTML: the preview of an inbound email's
HTML body.

The body is attacker controlled. Anyone able to email a queue, or to use the
public ticket form, chooses its content, and the person who ends up rendering it
is a staff member with access to every ticket in their queues. So the preview
never relies on sanitization alone. Three independent layers have to fail before
that becomes an XSS:

  1. nh3 removes scripts, event handler attributes and dangerous URL schemes.
  2. `Content-Security-Policy: default-src 'none'` stops the document from
     loading or executing anything at all.
  3. The CSP `sandbox` directive gives the document an opaque origin with
     scripting disabled, so even a sanitizer bypass cannot reach the helpdesk
     origin, the session cookie, or any helpdesk URL.

Sanitizing happens here, at render time, rather than when the attachment is
stored. That matters: the stored file keeps the sender's original bytes, which is
what you want when debugging what a customer actually sent, and upgrading nh3
retroactively protects every attachment ever stored instead of leaving already
cleaned files on disk to be trusted forever.
"""

from helpdesk import settings as helpdesk_settings

try:
    import nh3
except ImportError:  # pragma: no cover - nh3 is a declared dependency
    nh3 = None


def _allowed_attributes():
    """nh3's defaults, plus `style` on every tag.

    HTML email leans almost entirely on inline styles for layout, and dropping
    them turns a formatted message into an unreadable wall of text, which is the
    thing this preview exists to avoid. Inline CSS is safe enough here because
    the CSP forbids the document from loading any external resource, so a
    `url()` cannot be used to phone home, and scripting is off entirely.
    """
    attributes = {tag: set(attrs) for tag, attrs in nh3.ALLOWED_ATTRIBUTES.items()}
    attributes.setdefault("*", set()).add("style")
    return attributes


def sanitizer_available() -> bool:
    return nh3 is not None


def sanitize_email_html(html: str) -> str:
    """Strip everything executable out of an inbound email's HTML body.

    Raises RuntimeError rather than returning the input untouched if nh3 is
    missing: failing closed is the only acceptable behaviour here.
    """
    if nh3 is None:  # pragma: no cover - nh3 is a declared dependency
        raise RuntimeError(
            "nh3 is required to render HTML previews and is not installed."
        )
    return nh3.clean(html, attributes=_allowed_attributes())


def preview_csp() -> str:
    """The Content-Security-Policy sent with a rendered preview.

    `sandbox` with no allow-tokens is what actually makes this safe: the
    document gets an opaque origin and scripting is disabled by the browser,
    independently of whether the sanitizer missed something.

    Remote images are blocked by default, which also means tracking pixels in a
    customer's email do not fire when a staff member previews it. Operators who
    would rather have full fidelity can set
    HELPDESK_HTML_PREVIEW_ALLOW_REMOTE_IMAGES to True.
    """
    img_src = (
        "https: http:"
        if helpdesk_settings.HELPDESK_HTML_PREVIEW_ALLOW_REMOTE_IMAGES
        else "'none'"
    )
    return f"default-src 'none'; img-src {img_src}; style-src 'unsafe-inline'; sandbox"
