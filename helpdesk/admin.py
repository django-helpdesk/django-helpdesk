"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008-2025 Jutda. All Rights Reserved. See LICENSE for details.

models.py - Model (and hence database) definitions. This is the core of the
            helpdesk structure.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.apps import apps
from helpdesk import settings as helpdesk_settings
from helpdesk.models import (
    ChecklistTask,
    FollowUpAttachment,
    TicketChange,
    KBIAttachment,
)


class QueueAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "email_address", "locale", "time_spent")
    prepopulated_fields = {"slug": ("title",)}

    def time_spent(self, q):
        if q.dedicated_time:
            return "{} / {}".format(q.time_spent, q.dedicated_time)
        elif q.time_spent:
            return q.time_spent
        else:
            return "-"

    def delete_queryset(self, request, queryset):
        for queue in queryset:
            queue.delete()


class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "status",
        "assigned_to",
        "queue",
        "hidden_submitter_email",
        "time_spent",
    )
    date_hierarchy = "created"
    list_filter = ("queue", "assigned_to", "status")
    search_fields = ("id", "title")

    @admin.display(description=_("Submitter E-Mail"))
    def hidden_submitter_email(self, ticket):
        if ticket.submitter_email:
            username, domain = ticket.submitter_email.split("@")
            username = username[:2] + "*" * (len(username) - 2)
            domain = domain[:1] + "*" * (len(domain) - 2) + domain[-1:]
            return "%s@%s" % (username, domain)
        else:
            return ticket.submitter_email

    def time_spent(self, ticket):
        return ticket.time_spent


class TicketChangeInline(admin.StackedInline):
    model = TicketChange
    extra = 0


class FollowUpAttachmentInline(admin.StackedInline):
    model = FollowUpAttachment
    extra = 0


class KBIAttachmentInline(admin.StackedInline):
    model = KBIAttachment
    extra = 0


class FollowUpAdmin(admin.ModelAdmin):
    inlines = [TicketChangeInline, FollowUpAttachmentInline]
    list_display = (
        "ticket_get_ticket_for_url",
        "title",
        "date",
        "ticket",
        "user",
        "new_status",
        "time_spent",
    )
    list_filter = ("user", "date", "new_status")

    @admin.display(description=_("Slug"))
    def ticket_get_ticket_for_url(self, obj):
        return obj.ticket.ticket_for_url


if helpdesk_settings.HELPDESK_KB_ENABLED:

    class KBItemAdmin(admin.ModelAdmin):
        list_display = ("category", "title", "last_updated", "team", "order", "enabled")
        inlines = [KBIAttachmentInline]
        readonly_fields = ("voted_by", "downvoted_by")

        list_display_links = ("title",)

    if helpdesk_settings.HELPDESK_KB_ENABLED:

        class KBCategoryAdmin(admin.ModelAdmin):
            list_display = ("name", "title", "slug", "public")


class CustomFieldAdmin(admin.ModelAdmin):
    list_display = ("name", "label", "data_type")


class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ("template_name", "heading", "locale")
    list_filter = ("locale",)


class IgnoreEmailAdmin(admin.ModelAdmin):
    list_display = ("name", "queue_list", "email_address", "keep_in_mailbox")


class ChecklistTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "task_list")
    search_fields = ("name", "task_list")


class ChecklistTaskInline(admin.TabularInline):
    model = ChecklistTask


class ChecklistAdmin(admin.ModelAdmin):
    list_display = ("name", "ticket")
    search_fields = ("name", "ticket__id", "ticket__title")
    autocomplete_fields = ("ticket",)
    list_select_related = ("ticket",)
    inlines = (ChecklistTaskInline,)


admin.site.register(apps.get_model("helpdesk", "PreSetReply"))
admin.site.register(apps.get_model("helpdesk", "EscalationExclusion"))
admin.site.register(apps.get_model("helpdesk", "Queue"), QueueAdmin)
admin.site.register(apps.get_model("helpdesk", "Ticket"), TicketAdmin)
admin.site.register(apps.get_model("helpdesk", "FollowUp"), FollowUpAdmin)
admin.site.register(apps.get_model("helpdesk", "CustomField"), CustomFieldAdmin)
admin.site.register(apps.get_model("helpdesk", "EmailTemplate"), EmailTemplateAdmin)

admin.site.register(apps.get_model("helpdesk", "Checklist"), ChecklistAdmin)
admin.site.register(
    apps.get_model("helpdesk", "ChecklistTemplate"), ChecklistTemplateAdmin
)
admin.site.register(apps.get_model("helpdesk", "IgnoreEmail"), IgnoreEmailAdmin)


if helpdesk_settings.HELPDESK_KB_ENABLED:
    admin.site.register(apps.get_model("helpdesk", "KBItem"), KBItemAdmin)
    admin.site.register(apps.get_model("helpdesk", "KBCategory"), KBCategoryAdmin)
