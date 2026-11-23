from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from helpdesk import settings as helpdesk_settings
from helpdesk.decorators import is_helpdesk_staff


class StaffViewProtectorMixin:
    """Return the HELPDESK_STAFF_VIEW_PROTECTOR redirect instead of the view."""

    def dispatch(self, request, *args, **kwargs):
        if auth_redirect := helpdesk_settings.HELPDESK_STAFF_VIEW_PROTECTOR(request):
            return auth_redirect
        return super().dispatch(request, *args, **kwargs)


class MustBeStaffMixin(
    LoginRequiredMixin, UserPassesTestMixin, StaffViewProtectorMixin
):
    # The protector comes last in the MRO so it only runs for users who
    # passed the login and staff checks.
    def test_func(self):
        return is_helpdesk_staff(self.request.user)
