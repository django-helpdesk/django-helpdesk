from django import template

register = template.Library()


@register.filter
def get(value, arg, default=None):
    """ Call the dictionary get function """
    return value.get(arg, default)
