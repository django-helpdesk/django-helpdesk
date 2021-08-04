from django.template import Library
from django.template.defaultfilters import date as date_filter
from django.conf import settings

from datetime import datetime

from helpdesk.forms import CUSTOMFIELD_DATE_FORMAT, CUSTOMFIELD_TIME_FORMAT, CUSTOMFIELD_DATETIME_FORMAT

register = Library()


@register.filter
def get(value, arg, default=None):
    """ Call the dictionary get function """
    return value.get(arg, default)


@register.filter(expects_localtime=True)
def datetime_string_format(value):
    """
    :param value: String - Expected to be a datetime, date, or time in specific format
    :return: String - reformatted to default datetime, date, or time string if received in one of the expected formats
    """
    try:
        new_value = date_filter(datetime.strptime(value, CUSTOMFIELD_DATETIME_FORMAT), settings.DATETIME_FORMAT)
    except (TypeError, ValueError):
        try:
            new_value = date_filter(datetime.strptime(value, CUSTOMFIELD_DATE_FORMAT), settings.DATE_FORMAT)
        except (TypeError, ValueError):
            try:
                new_value = date_filter(datetime.strptime(value, CUSTOMFIELD_TIME_FORMAT), settings.TIME_FORMAT)
            except (TypeError, ValueError):
                # If NoneType return empty string, else return original value
                new_value = "" if value is None else value
    return new_value
