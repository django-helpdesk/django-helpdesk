"""
Renders a form with Bootstrap 5 markup, replacing the django-bootstrap4-form
dependency.

That package emitted classes from Bootstrap 3 (`form-group`, `control-label`,
`has-error`, `<div class="checkbox">`), none of which exist in the Bootstrap 5
stylesheet the project ships, so the affected fields lost their spacing and
their checkboxes and radios went unstyled.

Usage in a template::

    {% load bootstrap5_form %}
    {% bootstrap5_form form %}
"""

from django import forms
from django.template import Library

register = Library()

# Bootstrap 5 wants a different class per widget family. This cannot be applied
# from the template, because a widget rendered through {{ field }} has already
# had its attributes resolved, so it is done here before rendering instead.
SELECT_CLASS = "form-select"
CHECK_CLASS = "form-check-input"
CONTROL_CLASS = "form-control"

# Bootstrap 4 name, no effect in Bootstrap 5, which styles file inputs with the
# ordinary form-control.
OBSOLETE_CLASSES = {"form-control-file"}


def widget_class(widget):
    """The Bootstrap 5 class the given widget family needs, or None to leave it."""
    if isinstance(widget, (forms.HiddenInput, forms.MultipleHiddenInput)):
        return None
    if isinstance(widget, (forms.CheckboxInput, forms.RadioSelect)):
        return CHECK_CLASS
    if isinstance(widget, forms.CheckboxSelectMultiple):
        return CHECK_CLASS
    if isinstance(widget, forms.Select):
        return SELECT_CLASS
    return CONTROL_CLASS


def apply_classes(form):
    """Give every widget the class its Bootstrap 5 family requires.

    Classes already set in forms.py are kept: several widgets declare
    `form-control` there, and some carry sizing or behaviour classes unrelated to
    Bootstrap. Running this twice on the same form is harmless.
    """
    for name, field in form.fields.items():
        wanted = widget_class(field.widget)
        if wanted is None:
            continue
        classes = [
            c
            for c in field.widget.attrs.get("class", "").split()
            if c not in OBSOLETE_CLASSES and c != wanted and c != "is-invalid"
        ]
        classes.insert(0, wanted)
        if form.is_bound and form[name].errors:
            classes.append("is-invalid")
        field.widget.attrs["class"] = " ".join(classes)


@register.filter
def is_checkbox(field):
    return isinstance(field.field.widget, forms.CheckboxInput)


@register.filter
def is_choice_group(field):
    """Radio buttons and multiple checkboxes render one input per choice."""
    return isinstance(
        field.field.widget, (forms.RadioSelect, forms.CheckboxSelectMultiple)
    )


@register.inclusion_tag("helpdesk/include/form.html")
def bootstrap5_form(form):
    apply_classes(form)
    return {"form": form}
