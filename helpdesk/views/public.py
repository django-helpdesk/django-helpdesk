"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008-2025 Jutda. All Rights Reserved. See LICENSE for details.

views/public.py - All public facing views, eg non-staff (no authentication
                  required) views.
"""

from django.conf import settings
from django.core.exceptions import (
    ImproperlyConfigured,
    ObjectDoesNotExist,
    PermissionDenied,
)
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import TemplateView
from django.views.generic.edit import FormView
from helpdesk import settings as helpdesk_settings
from helpdesk.decorators import is_helpdesk_staff, protect_view
from helpdesk.lib import text_is_spam
from helpdesk.models import Queue, Ticket, UserSettings
from helpdesk.user import huser_from_request
import helpdesk.views.abstract_views as abstract_views
import helpdesk.views.staff as staff
from importlib import import_module
import logging
from urllib.parse import quote


logger = logging.getLogger(__name__)


def create_ticket(request, *args, **kwargs):
    if is_helpdesk_staff(request.user):
        return staff.CreateTicketView.as_view()(request, *args, **kwargs)
    else:
        return protect_view(CreateTicketView.as_view())(request, *args, **kwargs)


class BaseCreateTicketView(abstract_views.AbstractCreateTicketMixin, FormView):
    def get_form_class(self):
        try:
            the_module, the_form_class = (
                helpdesk_settings.HELPDESK_PUBLIC_TICKET_FORM_CLASS.rsplit(".", 1)
            )
            the_module = import_module(the_module)
            the_form_class = getattr(the_module, the_form_class)
        except Exception as e:
            raise ImproperlyConfigured(
                f"Invalid custom form class {helpdesk_settings.HELPDESK_PUBLIC_TICKET_FORM_CLASS}"
            ) from e
        return the_form_class

    def dispatch(self, *args, **kwargs):
        request = self.request
        if (
            not request.user.is_authenticated
            and helpdesk_settings.HELPDESK_REDIRECT_TO_LOGIN_BY_DEFAULT
        ):
            return HttpResponseRedirect(reverse("login"))

        if is_helpdesk_staff(request.user) or (
            request.user.is_authenticated
            and helpdesk_settings.HELPDESK_ALLOW_NON_STAFF_TICKET_UPDATE
        ):
            try:
                if request.user.usersettings_helpdesk.login_view_ticketlist:
                    return HttpResponseRedirect(reverse("helpdesk:list"))
                else:
                    return HttpResponseRedirect(reverse("helpdesk:dashboard"))
            except UserSettings.DoesNotExist:
                return HttpResponseRedirect(reverse("helpdesk:dashboard"))
        return super().dispatch(*args, **kwargs)

    def get_initial(self):
        initial_data = super().get_initial()

        # add pre-defined data for public ticket
        if hasattr(settings, "HELPDESK_PUBLIC_TICKET_QUEUE"):
            # get the requested queue; return an error if queue not found
            try:
                initial_data["queue"] = Queue.objects.get(
                    slug=settings.HELPDESK_PUBLIC_TICKET_QUEUE,
                    allow_public_submission=True,
                ).id
            except Queue.DoesNotExist as e:
                logger.fatal(
                    "Public queue '%s' is configured as default but can't be found",
                    settings.HELPDESK_PUBLIC_TICKET_QUEUE,
                )
                raise ImproperlyConfigured("Wrong public queue configuration") from e
        if hasattr(settings, "HELPDESK_PUBLIC_TICKET_PRIORITY"):
            initial_data["priority"] = settings.HELPDESK_PUBLIC_TICKET_PRIORITY
        if hasattr(settings, "HELPDESK_PUBLIC_TICKET_DUE_DATE"):
            initial_data["due_date"] = settings.HELPDESK_PUBLIC_TICKET_DUE_DATE
        return initial_data

    def get_form_kwargs(self, *args, **kwargs):
        kwargs = super().get_form_kwargs(*args, **kwargs)
        if "_hide_fields_" in self.request.GET:
            kwargs["hidden_fields"] = self.request.GET.get("_hide_fields_", "").split(
                ","
            )
        kwargs["readonly_fields"] = self.request.GET.get("_readonly_fields_", "").split(
            ","
        )
        return kwargs

    def form_valid(self, form):
        request = self.request
        if text_is_spam(form.cleaned_data["body"], request):
            # This submission is spam. Let's not save it.
            return render(request, template_name="helpdesk/public_spam.html")
        else:
            ticket = form.save(
                user=self.request.user if self.request.user.is_authenticated else None
            )
            try:
                return HttpResponseRedirect(
                    "%s?ticket=%s&email=%s&key=%s"
                    % (
                        reverse("helpdesk:public_view"),
                        ticket.ticket_for_url,
                        quote(ticket.submitter_email),
                        ticket.secret_key,
                    )
                )
            except ValueError:
                # if someone enters a non-int string for the ticket
                return HttpResponseRedirect(reverse("helpdesk:home"))


class CreateTicketIframeView(BaseCreateTicketView):
    template_name = "helpdesk/public_create_ticket_iframe.html"

    @csrf_exempt
    @xframe_options_exempt
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def form_valid(self, form):
        if super().form_valid(form).status_code == 302:
            return HttpResponseRedirect(reverse("helpdesk:success_iframe"))


class SuccessIframeView(TemplateView):
    template_name = "helpdesk/success_iframe.html"

    @xframe_options_exempt
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class CreateTicketView(BaseCreateTicketView):
    template_name = "helpdesk/public_create_ticket.html"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Add the CSS error class to the form in order to better see them in
        # the page
        form.error_css_class = "text-danger"
        return form


class Homepage(CreateTicketView):
    template_name = "helpdesk/public_homepage.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["kb_categories"] = huser_from_request(
            self.request
        ).get_allowed_kb_categories()
        return context


class SearchForTicketView(TemplateView):
    template_name = "helpdesk/public_view_form.html"

    def get(self, request, *args, **kwargs):
        if (
            hasattr(settings, "HELPDESK_VIEW_A_TICKET_PUBLIC")
            and settings.HELPDESK_VIEW_A_TICKET_PUBLIC
        ):
            context = self.get_context_data(**kwargs)
            return self.render_to_response(context)
        else:
            raise PermissionDenied(
                "Public viewing of tickets without a secret key is forbidden."
            )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request
        email = request.GET.get("email", None)
        error_message = kwargs.get("error_message", None)

        context.update(
            {
                "ticket": False,
                "email": email,
                "error_message": error_message,
                "helpdesk_settings": helpdesk_settings,
            }
        )
        return context


class ViewTicket(TemplateView):
    template_name = "helpdesk/public_view_ticket.html"

    def get(self, request, *args, **kwargs):
        ticket_req = request.GET.get("ticket", None)
        email = request.GET.get("email", None)
        key = request.GET.get("key", "")

        if not (ticket_req and email):
            if ticket_req is None and email is None:
                return SearchForTicketView.as_view()(request)
            else:
                return SearchForTicketView.as_view()(
                    request, _("Missing ticket ID or e-mail address. Please try again.")
                )

        try:
            queue, ticket_id = Ticket.queue_and_id_from_query(ticket_req)
            if request.user.is_authenticated and request.user.email == email:
                ticket = Ticket.objects.get(id=ticket_id, submitter_email__iexact=email)
            elif (
                hasattr(settings, "HELPDESK_VIEW_A_TICKET_PUBLIC")
                and settings.HELPDESK_VIEW_A_TICKET_PUBLIC
            ):
                ticket = Ticket.objects.get(id=ticket_id, submitter_email__iexact=email)
            else:
                ticket = Ticket.objects.get(
                    id=ticket_id, submitter_email__iexact=email, secret_key__iexact=key
                )
        except (ObjectDoesNotExist, ValueError):
            return SearchForTicketView.as_view()(
                request, _("Invalid ticket ID or e-mail address. Please try again.")
            )

        if "close" in request.GET and ticket.status == Ticket.RESOLVED_STATUS:
            from helpdesk.update_ticket import update_ticket

            update_ticket(
                request.user,
                ticket,
                public=True,
                comment=_("Submitter accepted resolution and closed ticket"),
                new_status=Ticket.CLOSED_STATUS,
            )
            return HttpResponseRedirect(ticket.ticket_url)

        # Prepare context for rendering
        context = {
            "key": key,
            "mail": email,
            "ticket": ticket,
            "helpdesk_settings": helpdesk_settings,
            "next": self.get_next_url(ticket_id),
        }
        return self.render_to_response(context)

    def get_next_url(self, ticket_id):
        redirect_url = ""
        if is_helpdesk_staff(self.request.user):
            redirect_url = reverse("helpdesk:view", args=[ticket_id])
            if "close" in self.request.GET:
                redirect_url += "?close"
        elif helpdesk_settings.HELPDESK_NAVIGATION_ENABLED:
            redirect_url = reverse("helpdesk:view", args=[ticket_id])
        return redirect_url


class MyTickets(TemplateView):
    template_name = "helpdesk/my_tickets.html"

    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseRedirect(reverse("helpdesk:login"))

        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)


def change_language(request):
    return_to = ""
    if "return_to" in request.GET:
        return_to = request.GET["return_to"]

    return render(request, "helpdesk/public_change_language.html", {"next": return_to})
