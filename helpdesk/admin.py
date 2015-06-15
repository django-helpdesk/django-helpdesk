from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from helpdesk.models import Queue, Ticket, FollowUp, PreSetReply, KBCategory
from helpdesk.models import EscalationExclusion, EmailTemplate, KBItem
from helpdesk.models import TicketChange, Attachment, IgnoreEmail
from helpdesk.models import CustomField
from helpdesk.models import QueueMembership
from helpdesk import settings as helpdesk_settings

class QueueAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'email_address', 'locale')

class TicketAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'assigned_to', 'submitter_email',)
    date_hierarchy = 'created'
    list_filter = ('assigned_to', 'status', )

class TicketChangeInline(admin.StackedInline):
    model = TicketChange

class AttachmentInline(admin.StackedInline):
    model = Attachment

class FollowUpAdmin(admin.ModelAdmin):
    inlines = [TicketChangeInline, AttachmentInline]

class KBItemAdmin(admin.ModelAdmin):
    list_display = ('category', 'title', 'last_updated',)
    list_display_links = ('title',)

class CustomFieldAdmin(admin.ModelAdmin):
    list_display = ('name', 'label', 'data_type')

class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ('template_name', 'heading', 'locale')
    list_filter = ('locale', )

class QueueMembershipInline(admin.StackedInline):
    model = QueueMembership

class UserAdminWithQueueMemberships(UserAdmin):

    def change_view(self, request, object_id, form_url='', extra_context=None):
        self.inlines = (QueueMembershipInline,)

        return super(UserAdminWithQueueMemberships, self).change_view(
            request, object_id, form_url=form_url, extra_context=extra_context)


admin.site.register(Ticket, TicketAdmin)
admin.site.register(Queue, QueueAdmin)
admin.site.register(FollowUp, FollowUpAdmin)
admin.site.register(PreSetReply)
admin.site.register(EscalationExclusion)
admin.site.register(EmailTemplate, EmailTemplateAdmin)
admin.site.register(KBCategory)
admin.site.register(KBItem, KBItemAdmin)
admin.site.register(IgnoreEmail)
admin.site.register(CustomField, CustomFieldAdmin)
if helpdesk_settings.HELPDESK_ENABLE_PER_QUEUE_STAFF_MEMBERSHIP:
    admin.site.unregister(get_user_model())
    admin.site.register(get_user_model(), UserAdminWithQueueMemberships)
