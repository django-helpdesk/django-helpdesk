from django.contrib import admin
from helpdesk.models import Queue, Ticket, FollowUp, PreSetReply, KBCategory
from helpdesk.models import EscalationExclusion, EmailTemplate, KBItem
from helpdesk.models import TicketChange, Attachment, IgnoreEmail
from helpdesk.models import CustomField

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
