from django.contrib import admin
from django import forms
from django.utils.translation import ugettext_lazy as _
from django.utils.html import format_html
from helpdesk.models import (
    Queue, Ticket, FollowUp, TimeSpent, PreSetReply, KBCategory, EscalationExclusion, EmailTemplate, KBItem, TicketChange,
    KBIAttachment, FollowUpAttachment, IgnoreEmail, CustomField, FormType, is_extra_data)
from seed.models import Column, Property, TaxLot
from seed.lib.superperms.orgs.models import get_helpdesk_organizations
from pinax.teams.models import JoinInvitation, Membership, Team
from pinax.invitations.admin import InvitationStat

admin.site.unregister(JoinInvitation)
admin.site.unregister(Membership)
admin.site.unregister(Team)
admin.site.unregister(InvitationStat)


@admin.register(Queue)
class QueueAdmin(admin.ModelAdmin):
    list_display = ('organization', 'title', 'slug', 'importer', 'allow_public_submission',
                    'match_on', 'match_on_addresses')
    list_display_links = ('title',)
    list_filter = ('organization',)
    prepopulated_fields = {"slug": ("title",)}

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "organization":
            kwargs["queryset"] = get_helpdesk_organizations()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def time_spent(self, q):
        if q.dedicated_time:
            return "{} / {}".format(q.time_spent, q.dedicated_time)
        elif q.time_spent:
            return q.time_spent
        else:
            return "-"


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'title_view', 'status', 'assigned_to', 'queue', 'ticket_form',
                    'hidden_submitter_email')
    list_display_links = ('title_view',)
    list_filter = ('ticket_form__organization', 'queue', 'ticket_form', 'assigned_to', 'status')

    # TODO set a different ordering that doesn't require them all to be written out?
    fields = ('queue', 'ticket_form', 'title', 'description', 'contact_name', 'contact_email', 'submitter_email',
              'building_name', 'building_address', 'pm_id', 'building_id', 'extra_data',
              'beam_property', 'beam_taxlot',
              'assigned_to', 'status', 'on_hold', 'resolution', 'secret_key', 'kbitem', 'merged_to',
              'priority', 'due_date', 'tags')

    readonly_fields = ('beam_property', 'beam_taxlot')

    def title_view(self, obj):
        return '(no title)' if not obj.title else obj.title
    title_view.short_description = _('Title')

    def time_spent(self, ticket):
        return ticket.time_spent

    def hidden_submitter_email(self, ticket):
        if ticket.submitter_email:
            split = ticket.submitter_email.split("@")
            if len(split) == 2:
                username, domain = split
                username = username[:2] + "*" * (len(username) - 2)
                domain = domain[:1] + "*" * (len(domain) - 2) + domain[-1:]
                return "%s@%s" % (username, domain)
            else:
                return ticket.submitter_email
        else:
            return ticket.submitter_email
    hidden_submitter_email.short_description = _('Submitter E-Mail')


class CustomFieldAdminForm(forms.ModelForm):
    # Overrides admin form for CustomField to add filtering for column's queryset.
    class Meta:
        model = CustomField
        fields = '__all__'

    def update_column_set(self, obj):
        if obj and hasattr(obj, 'ticket_form'):
            self.fields['column'].queryset = Column.objects \
                .filter(organization_id=obj.ticket_form.organization_id) \
                .exclude(table_name='') \
                .exclude(table_name=None) \
                .order_by('column_name')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.update_column_set(self.instance)


@admin.register(CustomField)
class CustomFieldAdmin(admin.ModelAdmin):
    form = CustomFieldAdminForm
    list_display = ('ticket_form_type', 'field_name', 'label', 'data_type', 'beam_column',
                    'required', 'staff', 'public', 'is_extra_data',)
    list_filter = ('ticket_form__organization', 'ticket_form',)
    list_display_links = ('field_name',)

    def ticket_form_type(self, field):
        if field.ticket_form:
            return field.ticket_form.name
    ticket_form_type.short_description = _('Ticket Form')

    def beam_column(self, field):
        if field.column:
            return field.column.column_name
    beam_column.short_description = _('BEAM Column')

    @admin.display(boolean=True)
    def is_extra_data(self, field):
        if field.field_name:
            return is_extra_data(field.field_name)
    is_extra_data.short_description = _('Non-default field?')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        form.update_column_set(obj)

    @admin.action(description="Mark field as required")
    def make_required_true(modeladmin, request, queryset):
        queryset.update(required=True)

    @admin.action(description="Mark field as optional")
    def make_required_false(modeladmin, request, queryset):
        queryset.update(required=False)

    @admin.action(description="Display on staff form")
    def make_staff_true(modeladmin, request, queryset):
        queryset.update(staff=True)

    @admin.action(description="Remove from staff form")
    def make_staff_false(modeladmin, request, queryset):
        queryset.update(staff=False)

    @admin.action(description="Display on public form")
    def make_public_true(modeladmin, request, queryset):
        queryset.update(public=True)

    @admin.action(description="Remove from public form")
    def make_public_false(modeladmin, request, queryset):
        queryset.update(public=False)

    actions = [make_required_true, make_required_false,
               make_staff_true, make_staff_false,
               make_public_true, make_public_false]


class CustomFieldInline(admin.TabularInline):
    # Allows user to edit form fields on the same page as the Form Type model.
    model = CustomField
    exclude = ('empty_selection_list',)
    can_delete = False
    extra = 0
    form = CustomFieldAdminForm

    class Media:
        css = {'all': ("helpdesk/admin_inline.css",)}

    def empty_selection_list_display(self, object):
        return object.empty_selection_list
    empty_selection_list_display.short_description = _("Add empty choice?")


@admin.register(FormType)
class FormTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'extra_data_cleaned', 'queue', 'public', 'staff', 'organization', )
    list_display_links = ('name',)
    list_filter = ('organization',)
    inlines = [CustomFieldInline]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "organization":
            kwargs["queryset"] = get_helpdesk_organizations()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def extra_data_cleaned(self, form):
        display = ''
        extra_fields = form.get_extra_field_names()
        for item in extra_fields:
            display += ('%s,<br />' % item)
        return format_html(display)
    extra_data_cleaned.short_description = _('Extra Data')


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
                    'user', 'new_status')
    list_filter = ('ticket__ticket_form__organization', 'ticket__ticket_form', 'user', 'date', 'new_status')

    def ticket_get_ticket_for_url(self, obj):
        return obj.ticket.ticket_for_url
    ticket_get_ticket_for_url.short_description = _('Slug')

@admin.register(TimeSpent)
class TimeSpentAdmin(admin.ModelAdmin):
    list_display = ('ticket_get_ticket_for_url', 'user', 'start_time', 'stop_time')

    def ticket_get_ticket_for_url(self, obj):
        return obj.ticket.ticket_for_url
    ticket_get_ticket_for_url.short_description = _('Slug')


@admin.register(KBItem)
class KBItemAdmin(admin.ModelAdmin):
    list_display = ('category', 'title', 'last_updated', 'team', 'order', 'enabled')
    list_filter = ('category__organization', 'category')
    inlines = [KBIAttachmentInline]
    readonly_fields = ('voted_by', 'downvoted_by')

    list_display_links = ('title',)


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ('template_name', 'heading', 'organization', 'locale')
    list_filter = ('organization', 'locale', )


@admin.register(IgnoreEmail)
class IgnoreEmailAdmin(admin.ModelAdmin):
    list_display = ('name', 'email_address', 'keep_in_mailbox')


@admin.register(KBCategory)
class KBCategoryAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'title', 'slug', 'public', 'organization', )
    list_filter = ('organization',)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "organization":
            kwargs["queryset"] = get_helpdesk_organizations()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


admin.site.register(PreSetReply)
admin.site.register(EscalationExclusion)
