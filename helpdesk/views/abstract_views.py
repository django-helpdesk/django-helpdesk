from helpdesk.models import CustomField, KBItem, Queue, FormType


class AbstractCreateTicketMixin():
    def get_initial(self):
        initial_data = {}
        request = self.request
        try:
            initial_data['queue'] = Queue.objects.get(slug=request.GET.get('queue', None)).id
        except Queue.DoesNotExist:
            pass
        u = request.user
        if u.is_authenticated and u.usersettings_helpdesk.use_email_as_submitter and u.email:
            initial_data['submitter_email'] = u.email

        query_param_fields = ['submitter_email', 'title', 'description', 'queue', 'kbitem']
        custom_fields = ["e_%s" % f.field_name for f in CustomField.objects.filter(staff_only=False,
                                                                                   ticket_form=self.form_id)]
        query_param_fields += custom_fields
        for qpf in query_param_fields:
            # Form only accepts qpf without the e_
            qpf_name = qpf[2:] if qpf[0:2] == 'e_' else qpf
            initial_data[qpf_name] = request.GET.get(qpf, initial_data.get(qpf_name, ""))

        initial_data = {k: ('' if v == 'null' else v) for k, v in initial_data.items()}

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
