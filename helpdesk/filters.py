import django_filters as df
from django import forms
from django.db.models import Q
from django_select2.forms import Select2MultipleWidget
from helpdesk.models import Ticket

from geant.filters import MyCustomDateRangeWidget


class TicketFilter(df.FilterSet):
    text = df.CharFilter(
        method='filter_text',
        label='Recherche',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    status = df.MultipleChoiceFilter(
        field_name='status',
        label='Statut',
        choices=Ticket.STATUS_CHOICES,
        widget=Select2MultipleWidget(attrs={'style': 'width: 100%', 'data-placeholder': 'Tous'})
    )
    created_between = df.DateFromToRangeFilter(
        field_name='created',
        label='Date de création entre',
        widget=MyCustomDateRangeWidget()
    )

    class Meta:
        model = Ticket
        fields = ('text', 'status', 'created_between')

    def filter_text(self, queryset, name, value):
        """ Custom method to find if the searched value is related to a ticket """
        return queryset.filter(
            Q(id__iexact=value) |
            Q(title__icontains=value) |
            Q(description__icontains=value) |
            Q(customer__group__name__icontains=value) |
            Q(customer_contact__last_name__icontains=value) |
            Q(customer_contact__first_name__icontains=value) |
            Q(customer_contact__username__icontains=value) |
            Q(customer_contact__email__icontains=value) |
            Q(assigned_to__last_name__icontains=value) |
            Q(assigned_to__first_name__icontains=value) |
            Q(assigned_to__username__icontains=value) |
            Q(assigned_to__email__icontains=value) |
            Q(submitter_email__icontains=value)
        ).distinct()
