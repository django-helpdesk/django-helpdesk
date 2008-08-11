from django.contrib import admin
from helpdesk.models import Queue, Ticket, FollowUp, PreSetReply, KBCategory
from helpdesk.models import EscalationExclusion, EmailTemplate, KBItem

class QueueAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'email_address')

class TicketAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'assigned_to', 'submitter_email',)
    date_hierarchy = 'created'
    list_filter = ('assigned_to', 'status', )

class GenericAdmin(admin.ModelAdmin):
    pass

class PreSetReplyAdmin(admin.ModelAdmin):
    list_display = ('name',)

admin.site.register(Ticket, TicketAdmin)
admin.site.register(Queue, QueueAdmin)
admin.site.register(FollowUp, GenericAdmin)
admin.site.register(PreSetReply, GenericAdmin)
admin.site.register(EscalationExclusion, GenericAdmin)
admin.site.register(EmailTemplate, GenericAdmin)
admin.site.register(KBCategory, GenericAdmin)
admin.site.register(KBItem, GenericAdmin)
