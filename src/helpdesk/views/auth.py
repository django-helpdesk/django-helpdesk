from django.conf import settings
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeDoneView,
    PasswordChangeView,
    redirect_to_login,
)
from django.http import HttpRequest, HttpResponse
from django.shortcuts import resolve_url

default_login_view = LoginView.as_view(template_name="helpdesk/registration/login.html")

logout = LogoutView.as_view(template_name="helpdesk/registration/logged_out.html")

password_change = PasswordChangeView.as_view(
    template_name="helpdesk/registration/change_password.html", success_url="./done"
)

password_change_done = PasswordChangeDoneView.as_view(
    template_name="helpdesk/registration/change_password_done.html"
)


def login(request: HttpRequest) -> HttpResponse:
    login_url = settings.LOGIN_URL
    view_name = request.resolver_match.view_name
    # Prevent redirect loop by checking that LOGIN_URL is not this view's name
    condition = login_url and (
        login_url != resolve_url(view_name) and (login_url != view_name)
    )
    if condition:
        next_url = request.GET.get("next", resolve_url("helpdesk:home"))
        return redirect_to_login(next_url, login_url)
    return default_login_view(request)
