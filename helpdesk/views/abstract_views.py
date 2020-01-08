from django.views.generic.edit import FormView

from helpdesk.models import CustomField, KBItem, Queue


class AbstractCreateTicketMixin():
    def get_initial(self):
        initial_data = {}
        request = self.request
        try:
            initial_data['queue'] = Queue.objects.get(slug=request.GET.get('queue', None)).id
        except Queue.DoesNotExist:
            pass
        if request.user.is_authenticated and request.user.usersettings_helpdesk.use_email_as_submitter and request.user.email:
            initial_data['submitter_email'] = request.user.email


        query_param_fields = ['submitter_email', 'title', 'body', 'queue', 'kbitem']
        custom_fields = ["custom_%s" % f.name for f in CustomField.objects.filter(staff_only=False)]
        query_param_fields += custom_fields
        for qpf in query_param_fields:
            initial_data[qpf] = request.GET.get(qpf, initial_data.get(qpf, ""))

        return initial_data

    def get_form_kwargs(self, *args, **kwargs):
        kwargs = super().get_form_kwargs(*args, **kwargs)
        kbitem = self.request.GET.get(
            'kbitem',
            self.request.POST.get('kbitem', None),
        )
        if kbitem:
            try:
                kwargs['kbcategory'] = KBItem.objects.get(pk=int(kbitem)).category
            except (ValueError, KBItem.DoesNotExist):
                pass
        return kwargs
