import django_filters as df
from django import forms
from django.db.models import Q
from django_select2.forms import Select2MultipleWidget, ModelSelect2MultipleWidget
from helpdesk.lib import get_assignable_users
from helpdesk.models import Ticket, FeedbackSurvey

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


class FeedbackSurveyFilter(df.FilterSet):
    tickets = df.ModelMultipleChoiceFilter(
        field_name='ticket',
        label='Tickets',
        queryset=Ticket.objects.all(),
        widget=ModelSelect2MultipleWidget(
            model=Ticket,
            search_fields=['id__iexact', 'title__icontains'],
            attrs={'style': 'width: 100%'}
        )
    )
    score = df.MultipleChoiceFilter(
        field_name='score',
        label='Score',
        choices=[(2, "Très bon"), (1, "Moyen"), (0, "À améliorer")],
        widget=forms.CheckboxSelectMultiple(
            attrs={'class': 'list-inline flat'}
        )
    )
    created_between = df.DateFromToRangeFilter(
        field_name='created_at',
        label='Date de création entre',
        widget=MyCustomDateRangeWidget()
    )
    assigned_to = df.ModelMultipleChoiceFilter(
        method='filter_assigned_to',
        label='Assigné à',
        queryset=get_assignable_users(),
        widget=Select2MultipleWidget(attrs={'style': 'width: 100%'})
    )

    class Meta:
        model = FeedbackSurvey
        fields = ('tickets', 'score', 'created_between')

    def filter_assigned_to(self, queryset, name, value):
        """ Custom method to filter tickets by assigned_to """
        if value:
            return queryset.filter(ticket__assigned_to__in=value).distinct()
        return queryset
