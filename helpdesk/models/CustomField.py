"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008-2025 Jutda. All Rights Reserved. See LICENSE for details.

models.py - Model (and hence database) definitions. This is the core of the
            helpdesk structure.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from io import StringIO
from rest_framework import serializers

from .CustomFieldManager import CustomFieldManager


class CustomField(models.Model):
    """
    Definitions for custom fields that are glued onto each ticket.
    """

    name = models.SlugField(
        _("Field Name"),
        help_text=_(
            "As used in the database and behind the scenes. "
            "Must be unique and consist of only lowercase letters with no punctuation."
        ),
        unique=True,
    )

    label = models.CharField(
        _("Label"),
        max_length=30,
        help_text=_("The display label for this field"),
    )

    help_text = models.TextField(
        _("Help Text"),
        help_text=_("Shown to the user when editing the ticket"),
        blank=True,
        null=True,
    )

    DATA_TYPE_CHOICES = (
        ("varchar", _("Character (single line)")),
        ("text", _("Text (multi-line)")),
        ("integer", _("Integer")),
        ("decimal", _("Decimal")),
        ("list", _("List")),
        ("boolean", _("Boolean (checkbox yes/no)")),
        ("date", _("Date")),
        ("time", _("Time")),
        ("datetime", _("Date & Time")),
        ("email", _("E-Mail Address")),
        ("url", _("URL")),
        ("ipaddress", _("IP Address")),
        ("slug", _("Slug")),
    )

    data_type = models.CharField(
        _("Data Type"),
        max_length=100,
        help_text=_("Allows you to restrict the data entered into this field"),
        choices=DATA_TYPE_CHOICES,
    )

    max_length = models.IntegerField(
        _("Maximum Length (characters)"),
        blank=True,
        null=True,
    )

    decimal_places = models.IntegerField(
        _("Decimal Places"),
        help_text=_("Only used for decimal fields"),
        blank=True,
        null=True,
    )

    empty_selection_list = models.BooleanField(
        _("Add empty first choice to List?"),
        default=False,
        help_text=_(
            "Only for List: adds an empty first entry to the choices list, "
            "which enforces that the user makes an active choice."
        ),
    )

    list_values = models.TextField(
        _("List Values"),
        help_text=_("For list fields only. Enter one option per line."),
        blank=True,
        null=True,
    )

    ordering = models.IntegerField(
        _("Ordering"),
        help_text=_(
            "Lower numbers are displayed first; higher numbers are listed later"
        ),
        blank=True,
        null=True,
    )

    def _choices_as_array(self):
        valuebuffer = StringIO(self.list_values)
        choices = [[item.strip(), item.strip()] for item in valuebuffer.readlines()]
        valuebuffer.close()
        return choices

    choices_as_array = property(_choices_as_array)

    required = models.BooleanField(
        _("Required?"),
        help_text=_("Does the user have to enter a value for this field?"),
        default=False,
    )

    staff_only = models.BooleanField(
        _("Staff Only?"),
        help_text=_(
            "If this is ticked, then the public submission form "
            "will NOT show this field"
        ),
        default=False,
    )

    objects = CustomFieldManager()

    def __str__(self):
        return "%s" % self.name

    class Meta:
        verbose_name = _("Custom field")
        verbose_name_plural = _("Custom fields")

    def get_choices(self):
        if not self.data_type == "list":
            return None
        choices = self.choices_as_array
        if self.empty_selection_list:
            choices.insert(0, ("", "---------"))
        return choices

    def build_api_field(self):
        customfield_to_api_field_dict = {
            "varchar": serializers.CharField,
            "text": serializers.CharField,
            "integer": serializers.IntegerField,
            "decimal": serializers.DecimalField,
            "list": serializers.ChoiceField,
            "boolean": serializers.BooleanField,
            "date": serializers.DateField,
            "time": serializers.TimeField,
            "datetime": serializers.DateTimeField,
            "email": serializers.EmailField,
            "url": serializers.URLField,
            "ipaddress": serializers.IPAddressField,
            "slug": serializers.SlugField,
        }

        # Prepare attributes for each types
        attributes = {
            "label": self.label,
            "help_text": self.help_text,
            "required": self.required,
        }
        if self.data_type in ("varchar", "text"):
            attributes["max_length"] = self.max_length
            if self.data_type == "text":
                attributes["style"] = {"base_template": "textarea.html"}
        elif self.data_type == "decimal":
            attributes["decimal_places"] = self.decimal_places
            attributes["max_digits"] = self.max_length
        elif self.data_type == "list":
            attributes["choices"] = self.get_choices()

        try:
            return customfield_to_api_field_dict[self.data_type](**attributes)
        except KeyError:
            raise NameError("Unrecognized data_type %s" % self.data_type)
