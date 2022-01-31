"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

templatetags/organization_info.py - This template tag returns an int converted to a string hex value:
"""
from django import template

register = template.Library()


@register.filter
def int_to_hex(value):
    """
    Given a decimal value for css styling, return the Hex value of that number
    Ex: Decimal 2198853 => Hex 0x218d45 => 218d45
    """
    if value:
        return hex(value)[2:]
    else:
        return hex(8421504)[2:]            # Default value
