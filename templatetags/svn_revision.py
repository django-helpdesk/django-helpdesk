from django import template
from django.utils.version import get_svn_revision
import helpdesk

def svn_revision(parser, token):
    path = helpdesk.__path__[0]
    return SVNRevisionNode(path)

class SVNRevisionNode(template.Node):
    def __init__(self, path):
        self.path = path
    def render(self, context):
        return get_svn_revision(self.path)

register = template.Library()
register.tag('helpdesk_svn_revision', svn_revision)
