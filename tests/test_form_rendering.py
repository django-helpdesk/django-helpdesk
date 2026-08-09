"""
Forms are rendered by helpdesk's own Bootstrap 5 templates rather than by
django-bootstrap4-form, which emitted Bootstrap 3 markup into a Bootstrap 5 UI.

These tests assert the markup the stylesheet we ship actually understands, and
assert the absence of the classes that used to be emitted, so a regression to
the old rendering fails here rather than being noticed by a user.
"""

from django import forms
from django.template import Context, Template
from django.test import TestCase
from django.urls import reverse

from helpdesk.models import Queue
from helpdesk.templatetags.bootstrap5_form import apply_classes

from .helpers import get_staff_user

# Classes emitted by the old dependency. None of them exists in Bootstrap 5.
LEGACY_CLASSES = ["form-group", "control-label", "has-error"]


class SampleForm(forms.Form):
    text = forms.CharField(label="Text", help_text="Some help")
    choice = forms.ChoiceField(label="Choice", choices=[("a", "A"), ("b", "B")])
    agree = forms.BooleanField(label="Agree", required=False)
    radio = forms.ChoiceField(
        label="Radio", choices=[("x", "X"), ("y", "Y")], widget=forms.RadioSelect
    )
    secret = forms.CharField(widget=forms.HiddenInput, required=False)
    preset = forms.CharField(
        label="Preset", widget=forms.TextInput(attrs={"class": "form-control custom"})
    )


def render(form):
    return Template("{% load bootstrap5_form %}{% bootstrap5_form form %}").render(
        Context({"form": form})
    )


class WidgetClassTestCase(TestCase):
    def test_each_widget_family_gets_its_bootstrap5_class(self):
        form = SampleForm()
        apply_classes(form)
        attrs = {
            name: f.widget.attrs.get("class", "") for name, f in form.fields.items()
        }
        self.assertIn("form-control", attrs["text"])
        self.assertIn("form-select", attrs["choice"])
        self.assertIn("form-check-input", attrs["agree"])
        self.assertIn("form-check-input", attrs["radio"])

    def test_hidden_widgets_are_left_alone(self):
        form = SampleForm()
        apply_classes(form)
        self.assertEqual(form.fields["secret"].widget.attrs.get("class", ""), "")

    def test_classes_already_set_in_forms_py_are_kept(self):
        form = SampleForm()
        apply_classes(form)
        classes = form.fields["preset"].widget.attrs["class"].split()
        self.assertIn("custom", classes)
        self.assertEqual(classes.count("form-control"), 1, classes)

    def test_applying_twice_does_not_duplicate(self):
        form = SampleForm()
        apply_classes(form)
        apply_classes(form)
        for name, field in form.fields.items():
            classes = field.widget.attrs.get("class", "").split()
            self.assertEqual(len(classes), len(set(classes)), f"{name}: {classes}")

    def test_invalid_fields_are_marked(self):
        form = SampleForm(data={"text": "", "choice": "a", "radio": "x", "preset": "p"})
        self.assertFalse(form.is_valid())
        apply_classes(form)
        self.assertIn("is-invalid", form.fields["text"].widget.attrs["class"])
        self.assertNotIn("is-invalid", form.fields["preset"].widget.attrs["class"])


class RenderedMarkupTestCase(TestCase):
    def test_layout_is_bootstrap5(self):
        html = render(SampleForm())
        self.assertIn('class="mb-3"', html)
        self.assertIn('class="form-label', html)
        self.assertIn("form-check-label", html)
        self.assertIn('class="form-text"', html)

    def test_no_legacy_classes_remain(self):
        html = render(SampleForm())
        for legacy in LEGACY_CLASSES:
            self.assertNotIn(legacy, html, f"{legacy} should not be emitted any more")

    def test_hidden_fields_are_rendered_without_a_wrapper(self):
        html = render(SampleForm())
        self.assertIn('name="secret"', html)
        self.assertNotIn("Secret", html)

    def test_errors_are_visible_without_relying_on_a_sibling(self):
        """`invalid-feedback` alone is only revealed by an adjacent
        `.is-invalid`, which does not hold for the choice groups."""
        form = SampleForm(data={"text": "", "choice": "a", "radio": "x", "preset": "p"})
        self.assertFalse(form.is_valid())
        html = render(form)
        self.assertIn("invalid-feedback d-block", html)

    def test_non_field_errors_use_a_dismissible_alert(self):
        class Failing(forms.Form):
            def clean(self):
                raise forms.ValidationError("nope")

        html = render(Failing(data={}))
        self.assertIn("alert alert-danger", html)
        self.assertIn("data-bs-dismiss", html)
        self.assertNotIn("data-dismiss=", html.replace("data-bs-dismiss=", ""))


class RealPagesTestCase(TestCase):
    """The three pages that used the old filter must still render."""

    def setUp(self):
        self.queue = Queue.objects.create(
            title="Queue", slug="q", allow_public_submission=True
        )
        self.user = get_staff_user()

    def assert_bootstrap5(self, response):
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("mb-3", html)
        for legacy in LEGACY_CLASSES:
            self.assertNotIn(legacy, html)

    def test_public_ticket_form(self):
        self.assert_bootstrap5(self.client.get(reverse("helpdesk:home")))

    def test_user_settings_form(self):
        self.client.login(username=self.user.username, password="password")
        self.assert_bootstrap5(self.client.get(reverse("helpdesk:user_settings")))
