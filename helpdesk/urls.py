"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

urls.py - Mapping of URL's to our various views. Note we always used NAMED
          views for simplicity in linking later on.
"""

from django.urls import path, re_path
from django.contrib.auth.decorators import login_required
from django.contrib.auth import views as auth_views
from django.urls import include
from django.views.generic import TemplateView
from rest_framework.routers import DefaultRouter

from helpdesk.decorators import helpdesk_staff_member_required, protect_view
from helpdesk.views import feeds, staff, public, login
from helpdesk import settings as helpdesk_settings
from helpdesk.views.api import TicketViewSet, CreateUserView

if helpdesk_settings.HELPDESK_KB_ENABLED:
    from helpdesk.views import kb

try:
    # TODO: why is it imported? due to some side-effect or by mistake?
    import helpdesk.tasks  # NOQA
except ImportError:
    pass


class DirectTemplateView(TemplateView):
    extra_context = None

    def get_context_data(self, **kwargs):
        context = super(self.__class__, self).get_context_data(**kwargs)
        if self.extra_context is not None:
            for key, value in self.extra_context.items():
                if callable(value):
                    context[key] = value()
                else:
                    context[key] = value
        return context


app_name = "helpdesk"

base64_pattern = r"(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$"

urlpatterns = [
    path("dashboard/", staff.dashboard, name="dashboard"),
    path("tickets/", staff.ticket_list, name="list"),
    path("tickets/update/", staff.mass_update, name="mass_update"),
    path("tickets/merge", staff.merge_tickets, name="merge_tickets"),
    path("tickets/<int:ticket_id>/", staff.view_ticket, name="view"),
    path(
        "tickets/<int:ticket_id>/followup_edit/<int:followup_id>/",
        staff.followup_edit,
        name="followup_edit",
    ),
    path(
        "tickets/<int:ticket_id>/followup_delete/<int:followup_id>/",
        staff.followup_delete,
        name="followup_delete",
    ),
    path("tickets/<int:ticket_id>/edit/", staff.edit_ticket, name="edit"),
    path("tickets/<int:ticket_id>/update/", staff.update_ticket, name="update"),
    path("tickets/<int:ticket_id>/delete/", staff.delete_ticket, name="delete"),
    path("tickets/<int:ticket_id>/hold/", staff.hold_ticket, name="hold"),
    path("tickets/<int:ticket_id>/unhold/", staff.unhold_ticket, name="unhold"),
    path("tickets/<int:ticket_id>/cc/", staff.ticket_cc, name="ticket_cc"),
    path("tickets/<int:ticket_id>/cc/add/", staff.ticket_cc_add, name="ticket_cc_add"),
    path(
        "tickets/<int:ticket_id>/cc/delete/<int:cc_id>/",
        staff.ticket_cc_del,
        name="ticket_cc_del",
    ),
    path(
        "tickets/<int:ticket_id>/dependency/add/",
        staff.ticket_dependency_add,
        name="ticket_dependency_add",
    ),
    path(
        "tickets/<int:ticket_id>/dependency/delete/<int:dependency_id>/",
        staff.ticket_dependency_del,
        name="ticket_dependency_del",
    ),
    path(
        "tickets/<int:ticket_id>/attachment_delete/<int:attachment_id>/",
        staff.attachment_del,
        name="attachment_del",
    ),
    re_path(r"^raw/(?P<type>\w+)/$", staff.raw_details, name="raw"),
    path("rss/", staff.rss_list, name="rss_index"),
    path("reports/", staff.report_index, name="report_index"),
    re_path(r"^reports/(?P<report>\w+)/$", staff.run_report, name="run_report"),
    path("save_query/", staff.save_query, name="savequery"),
    path("delete_query/<int:id>/", staff.delete_saved_query, name="delete_query"),
    path("settings/", staff.EditUserSettingsView.as_view(), name="user_settings"),
    path("ignore/", staff.email_ignore, name="email_ignore"),
    path("ignore/add/", staff.email_ignore_add, name="email_ignore_add"),
    path("ignore/delete/<int:id>/", staff.email_ignore_del, name="email_ignore_del"),
    re_path(
        r"^datatables_ticket_list/(?P<query>{})$".format(base64_pattern),
        staff.datatables_ticket_list,
        name="datatables_ticket_list",
    ),
    re_path(
        r"^timeline_ticket_list/(?P<query>{})$".format(base64_pattern),
        staff.timeline_ticket_list,
        name="timeline_ticket_list",
    ),
]

if helpdesk_settings.HELPDESK_ENABLE_DEPENDENCIES_ON_TICKET:
    urlpatterns += [
        re_path(
            r"^tickets/(?P<ticket_id>[0-9]+)/dependency/add/$",
            staff.ticket_dependency_add,
            name="ticket_dependency_add",
        ),
        re_path(
            r"^tickets/(?P<ticket_id>[0-9]+)/dependency/delete/(?P<dependency_id>[0-9]+)/$",
            staff.ticket_dependency_del,
            name="ticket_dependency_del",
        ),
    ]

urlpatterns += [
    path("", protect_view(public.Homepage.as_view()), name="home"),
    path("tickets/submit/", public.create_ticket, name="submit"),
    path(
        "tickets/submit_iframe/",
        public.CreateTicketIframeView.as_view(),
        name="submit_iframe",
    ),
    path(
        "tickets/success_iframe/",  # Ticket was submitted successfully
        public.SuccessIframeView.as_view(),
        name="success_iframe",
    ),
    path("view/", public.view_ticket, name="public_view"),
    path("change_language/", public.change_language, name="public_change_language"),
]

urlpatterns += [
    path(
        "rss/user/<str:user_name>/",
        helpdesk_staff_member_required(feeds.OpenTicketsByUser()),
        name="rss_user",
    ),
    re_path(
        r"^rss/user/(?P<user_name>[^/]+)/(?P<queue_slug>[A-Za-z0-9_-]+)/$",
        helpdesk_staff_member_required(feeds.OpenTicketsByUser()),
        name="rss_user_queue",
    ),
    re_path(
        r"^rss/queue/(?P<queue_slug>[A-Za-z0-9_-]+)/$",
        helpdesk_staff_member_required(feeds.OpenTicketsByQueue()),
        name="rss_queue",
    ),
    path(
        "rss/unassigned/",
        helpdesk_staff_member_required(feeds.UnassignedTickets()),
        name="rss_unassigned",
    ),
    path(
        "rss/recent_activity/",
        helpdesk_staff_member_required(feeds.RecentFollowUps()),
        name="rss_activity",
    ),
]


# API is added to url conf based on the setting (False by default)
if helpdesk_settings.HELPDESK_ACTIVATE_API_ENDPOINT:
    router = DefaultRouter()
    router.register(r"tickets", TicketViewSet, basename="ticket")
    router.register(r"users", CreateUserView, basename="user")
    urlpatterns += [re_path(r"^api/", include(router.urls))]


urlpatterns += [
    path("login/", login.login, name="login"),
    path(
        "logout/",
        auth_views.LogoutView.as_view(
            template_name="helpdesk/registration/login.html", next_page="../"
        ),
        name="logout",
    ),
    path(
        "password_change/",
        auth_views.PasswordChangeView.as_view(
            template_name="helpdesk/registration/change_password.html",
            success_url="./done",
        ),
        name="password_change",
    ),
    path(
        "password_change/done",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="helpdesk/registration/change_password_done.html",
        ),
        name="password_change_done",
    ),
]

if helpdesk_settings.HELPDESK_KB_ENABLED:
    urlpatterns += [
        path("kb/", kb.index, name="kb_index"),
        re_path(r"^kb/(?P<slug>[A-Za-z0-9_-]+)/$", kb.category, name="kb_category"),
        path("kb/<int:item>/vote/", kb.vote, name="kb_vote"),
        re_path(
            r"^kb_iframe/(?P<slug>[A-Za-z0-9_-]+)/$",
            kb.category_iframe,
            name="kb_category_iframe",
        ),
    ]

urlpatterns += [
    path(
        "help/context/",
        TemplateView.as_view(template_name="helpdesk/help_context.html"),
        name="help_context",
    ),
    path(
        "system_settings/",
        login_required(
            DirectTemplateView.as_view(template_name="helpdesk/system_settings.html")
        ),
        name="system_settings",
    ),
]
