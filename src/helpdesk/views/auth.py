from django.conf import settings
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeDoneView,
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
    redirect_to_login,
)
from django.http import HttpRequest, HttpResponse
from django.shortcuts import resolve_url
from django.urls import reverse_lazy


def _t(fragment: str) -> str:
    return f"helpdesk/registration/{fragment}"


default_login_view = LoginView.as_view(template_name=_t("login.html"))

logout = LogoutView.as_view(template_name=_t("logged_out.html"))

password_change = PasswordChangeView.as_view(
    template_name=_t("change_password.html"),
    success_url=reverse_lazy("helpdesk:password_change_done"),
)

password_change_done = PasswordChangeDoneView.as_view(
    template_name=_t("change_password_done.html")
)

password_reset = PasswordResetView.as_view(
    template_name=_t("password_reset_form.html"),
    email_template_name=_t("password_reset_email.html"),
    subject_template_name=_t("password_reset_subject.txt"),
    success_url=reverse_lazy("helpdesk:password_reset_done"),
)

password_reset_done = PasswordResetDoneView.as_view(
    template_name=_t("password_reset_done.html")
)

password_reset_confirm = PasswordResetConfirmView.as_view(
    template_name=_t("password_reset_confirm.html"),
    success_url=reverse_lazy("helpdesk:password_reset_complete"),
)

password_reset_complete = PasswordResetCompleteView.as_view(
    template_name=_t("password_reset_complete.html")
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
