from django.contrib import admin
from django.utils.translation import ugettext_lazy as _
from django.utils.html import format_html
from helpdesk.models import Queue, Ticket, FollowUp, PreSetReply, KBCategory
from helpdesk.models import EscalationExclusion, EmailTemplate, KBItem
from helpdesk.models import TicketChange, KBIAttachment, FollowUpAttachment, IgnoreEmail
from helpdesk.models import CustomField, FormType


@admin.register(Queue)
class QueueAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'email_address', 'locale', 'time_spent')
    prepopulated_fields = {"slug": ("title",)}

    def time_spent(self, q):
        if q.dedicated_time:
            return "{} / {}".format(q.time_spent, q.dedicated_time)
        elif q.time_spent:
            return q.time_spent
        else:
            return "-"


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('title_view', 'status', 'assigned_to', 'queue',
                    'hidden_submitter_email', 'time_spent')
    date_hierarchy = 'created'
    list_filter = ('queue', 'assigned_to', 'status')

    def hidden_submitter_email(self, ticket):
        if ticket.submitter_email:
            username, domain = ticket.submitter_email.split("@")
            username = username[:2] + "*" * (len(username) - 2)
            domain = domain[:1] + "*" * (len(domain) - 2) + domain[-1:]
            return "%s@%s" % (username, domain)
        else:
            return ticket.submitter_email
    hidden_submitter_email.short_description = _('Submitter E-Mail')

    def time_spent(self, ticket):
        return ticket.time_spent

    def title_view(self, obj):
        if not obj.title:
            return '(no title)'
        return obj.title
    title_view.short_description = _('Title')


class TicketChangeInline(admin.StackedInline):
    model = TicketChange
    extra = 0


class FollowUpAttachmentInline(admin.StackedInline):
    model = FollowUpAttachment
    extra = 0


class KBIAttachmentInline(admin.StackedInline):
    model = KBIAttachment
    extra = 0


@admin.register(FollowUp)
class FollowUpAdmin(admin.ModelAdmin):
    inlines = [TicketChangeInline, FollowUpAttachmentInline]
    list_display = ('ticket_get_ticket_for_url', 'title', 'date', 'ticket',
                    'user', 'new_status', 'time_spent')
    list_filter = ('user', 'date', 'new_status')

    def ticket_get_ticket_for_url(self, obj):
        return obj.ticket.ticket_for_url
    ticket_get_ticket_for_url.short_description = _('Slug')


@admin.register(KBItem)
class KBItemAdmin(admin.ModelAdmin):
    list_display = ('category', 'title', 'last_updated', 'team', 'order', 'enabled')
    inlines = [KBIAttachmentInline]
    readonly_fields = ('voted_by', 'downvoted_by')

    list_display_links = ('title',)

def make_extra_data_true(modeladmin, request, queryset):
    queryset.update(is_extra_data=True)

def make_extra_data_false(modeladmin, request, queryset):
    queryset.update(is_extra_data=False)

def make_required_true(modeladmin, request, queryset):
    queryset.update(required=True)

def make_required_false(modeladmin, request, queryset):
    queryset.update(required=False)

def make_staff_true(modeladmin, request, queryset):
    queryset.update(staff_only=True)

def make_staff_false(modeladmin, request, queryset):
    queryset.update(staff_only=False)


make_extra_data_true.short_description = "Set 'is_extra_data' to True"
make_extra_data_false.short_description = "Set 'is_extra_data' to False"
make_required_true.short_description = "Set 'required' to True"
make_required_false.short_description = "Set 'required' to False"
make_staff_true.short_description = "Set 'staff_only' to True"
make_staff_false.short_description = "Set 'staff_only' to False"

@admin.register(CustomField)
class CustomFieldAdmin(admin.ModelAdmin):
    list_display = ('ticket_form_type', 'field_name', 'label', 'data_type',
                    'required', 'staff_only', 'is_extra_data')
    list_filter = ('ticket_form',)
    list_display_links = ('field_name',)
    actions = [make_extra_data_true, make_extra_data_false,
               make_required_true, make_required_false,
               make_staff_true, make_staff_false]

    def ticket_form_type(self, ticket):
        if ticket.ticket_form:
            return ticket.ticket_form.name
    ticket_form_type.short_description = _('Ticket Form')


@admin.register(FormType)
class FormTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'extra_data_cleaned', 'organization', )
    list_display_links = ('name',)

    def extra_data_cleaned(self, form):
        display = ''
        for item in form.extra_data:
            display += ('%s<br />' % item)
        return format_html(display)
    extra_data_cleaned.short_description = _('Extra Data')


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ('template_name', 'heading', 'locale')
    list_filter = ('locale', )


@admin.register(IgnoreEmail)
class IgnoreEmailAdmin(admin.ModelAdmin):
    list_display = ('name', 'queue_list', 'email_address', 'keep_in_mailbox')


@admin.register(KBCategory)
class KBCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'title', 'slug', 'public')


admin.site.register(PreSetReply)
admin.site.register(EscalationExclusion)
