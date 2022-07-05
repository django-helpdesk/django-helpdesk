from django.contrib import admin
from django import forms
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils.html import format_html
from helpdesk.models import Queue, Ticket, FollowUp, PreSetReply, KBCategory
from helpdesk.models import EscalationExclusion, EmailTemplate, KBItem
from helpdesk.models import TicketChange, KBIAttachment, FollowUpAttachment, IgnoreEmail
from helpdesk.models import CustomField, FormType
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
    list_display = ('organization', 'title', 'slug', 'importer_sender', 'allow_public_submission',
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


class CustomFieldInline(admin.TabularInline):
    # Allows user to edit form fields on the same page as the Form Type model.
    model = CustomField
    exclude = ('empty_selection_list',)
    raw_id_fields = ("columns",)
    can_delete = False
    extra = 0

    class Media:
        css = {'all': ("helpdesk/admin_inline.css",)}

    def empty_selection_list_display(self, object):
        return object.empty_selection_list
    empty_selection_list_display.short_description = _("Add empty choice?")


@admin.register(FormType)
class FormTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'extra_data_cleaned', 'queue', 'public', 'staff', 'organization', )
    list_display_links = ('name',)
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


class TicketAdminForm(forms.ModelForm):
    # Allows beam_property and beam_taxlot's querysets to be filtered.
    class Meta:
        model = Ticket
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.update_ticket_set(self.instance)

    def update_ticket_set(self, obj):
        if obj and hasattr(obj, 'ticket_form'):
            self.fields['beam_property'].queryset = Property.objects.filter(
                organization_id=obj.ticket_form.organization_id).order_by('id')
            self.fields['beam_taxlot'].queryset = TaxLot.objects.filter(
                organization_id=obj.ticket_form.organization_id).order_by('id')


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'title_view', 'status', 'assigned_to', 'queue', 'ticket_form',
                    'hidden_submitter_email')
    list_display_links = ('title_view',)
    list_filter = ('queue', 'ticket_form', 'assigned_to', 'status')
    date_hierarchy = 'created'

    # TODO set a different ordering that doesn't require them all to be written out?
    fields = ('queue', 'ticket_form', 'title', 'description', 'contact_name', 'contact_email', 'submitter_email',
              'building_name', 'building_address', 'pm_id', 'building_id', 'extra_data',
              'beam_property', 'beam_taxlot',
              'assigned_to', 'status', 'on_hold', 'resolution', 'secret_key', 'kbitem', 'merged_to',
              'priority', 'due_date',)

    form = TicketAdminForm
    filter_horizontal = ('beam_property', 'beam_taxlot')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        form.update_ticket_set(obj)

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
    # Overrides admin form for CustomField to add filtering for columns' queryset.
    class Meta:
        model = CustomField
        fields = '__all__'

    def update_columns_set(self, obj):
        if obj and hasattr(obj, 'ticket_form'):
            self.fields['columns'].queryset = Column.objects \
                .filter(organization_id=obj.ticket_form.organization_id) \
                .exclude(table_name='') \
                .exclude(table_name=None) \
                .order_by('id')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.update_columns_set(self.instance)


@admin.register(CustomField)
class CustomFieldAdmin(admin.ModelAdmin):
    form = CustomFieldAdminForm
    list_display = ('ticket_form_type', 'field_name', 'label', 'data_type',
                    'required', 'staff_only', 'is_extra_data')
    list_filter = ('ticket_form',)
    list_display_links = ('field_name',)
    filter_horizontal = ('columns',)

    def ticket_form_type(self, ticket):
        if ticket.ticket_form:
            return ticket.ticket_form.name
    ticket_form_type.short_description = _('Ticket Form')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        form.update_columns_set(obj)

    @admin.action(description="Mark field as required")
    def make_required_true(modeladmin, request, queryset):
        queryset.update(required=True)

    @admin.action(description="Mark field as optional")
    def make_required_false(modeladmin, request, queryset):
        queryset.update(required=False)

    @admin.action(description="Display only on staff form")
    def make_staff_true(modeladmin, request, queryset):
        queryset.update(staff_only=True)

    @admin.action(description="Display on public form")
    def make_staff_false(modeladmin, request, queryset):
        queryset.update(staff_only=False)

    @admin.action(description="Mark as a non-default field")
    def make_extra_data_true(modeladmin, request, queryset):
        queryset.update(is_extra_data=True)

    @admin.action(description="Mark as a default field")
    def make_extra_data_false(modeladmin, request, queryset):
        queryset.update(is_extra_data=False)

    actions = [make_required_true, make_required_false,
               make_staff_true, make_staff_false,
               make_extra_data_true, make_extra_data_false]


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
    list_display = ('name', 'importer_list', 'email_address', 'keep_in_mailbox')


@admin.register(KBCategory)
class KBCategoryAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'title', 'slug', 'public', 'organization', )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "organization":
            kwargs["queryset"] = get_helpdesk_organizations()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


admin.site.register(PreSetReply)
admin.site.register(EscalationExclusion)
