from django import template

register = template.Library()


@register.filter
def floor_divide(value, arg):
    try:
        return int(value) // int(arg)
    except (ValueError, ZeroDivisionError):
        return None
