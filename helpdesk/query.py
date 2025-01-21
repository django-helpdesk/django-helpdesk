
from base64 import b64decode, b64encode
from django.db.models import Q
from django.urls import reverse
from django.utils.html import escape
from django.utils.translation import gettext as _
from helpdesk.serializers import DatatablesTicketSerializer
import json
from model_utils import Choices


def query_to_base64(query):
    """
    Converts a query dict object to a base64-encoded bytes object.
    """
    return b64encode(json.dumps(query).encode('UTF-8')).decode("ascii")


def query_from_base64(b64data):
    """
    Converts base64-encoded bytes object back to a query dict object.
    """
    query = {'search_string': ''}
    query.update(json.loads(b64decode(b64data).decode('utf-8')))
    if query['search_string'] is None:
        query['search_string'] = ''
    return query


def get_search_filter_args(search):
    if search.startswith('queue:'):
        return Q(queue__title__icontains=search[len('queue:'):])
    if search.startswith('priority:'):
        return Q(priority__icontains=search[len('priority:'):])
    filter = Q()
    for subsearch in search.split("OR"):
        subsearch = subsearch.strip()
        filter = (
            filter |
            Q(id__icontains=subsearch) |
            Q(title__icontains=subsearch) |
            Q(description__icontains=subsearch) |
            Q(priority__icontains=subsearch) |
            Q(resolution__icontains=subsearch) |
            Q(submitter_email__icontains=subsearch) |
            Q(assigned_to__email__icontains=subsearch) |
            Q(ticketcustomfieldvalue__value__icontains=subsearch) |
            Q(created__icontains=subsearch) |
            Q(due_date__icontains=subsearch)
        )
    return filter


DATATABLES_ORDER_COLUMN_CHOICES = Choices(
    ('0', 'id'),
    ('1', 'title'),
    ('2', 'priority'),
    ('3', 'queue'),
    ('4', 'status'),
    ('5', 'created'),
    ('6', 'due_date'),
    ('7', 'assigned_to'),
    ('8', 'submitter_email'),
    # ('9', 'time_spent'),
    ('10', 'kbitem'),
)


def get_query_class():
    from django.conf import settings

    def _get_query_class():
        return __Query__
    return getattr(settings,
                   'HELPDESK_QUERY_CLASS',
                   _get_query_class)()


class __Query__:
    def __init__(self, huser, base64query=None, query_params=None):
        self.huser = huser
        self.params = query_params if query_params else query_from_base64(
            base64query)
        self.base64 = base64query if base64query else query_to_base64(
            query_params)
        self.result = None

    def get_search_filter_args(self):
        search = self.params.get('search_string', '')
        return get_search_filter_args(search)

    def __run__(self, queryset):
        """
        Apply a dict-based set of filters & parameters to a queryset.

        queryset is a Django queryset, eg MyModel.objects.all() or
            MyModel.objects.filter(user=request.user)

        params is a dictionary that contains the following:
           filtering: A dict of Django ORM filters, eg:
            {'user__id__in': [1, 3, 103], 'title__contains': 'foo'}

        search_string: A freetext search string

        sorting: The name of the column to sort by
        """
        filter = self.params.get('filtering', {})
        filter_or = self.params.get('filtering_or')

        query_filter = Q(**filter)

        if 'filtering_or' in self.params:
            print(self.params)
            #query_filter |= Q(**filter_or)

        queryset = queryset.filter(query_filter & self.get_search_filter_args())
        sorting = self.params.get('sorting', None)
        if sorting:
            sortreverse = self.params.get('sortreverse', None)
            if sortreverse:
                sorting = "-%s" % sorting
            queryset = queryset.order_by(sorting)
        # https://stackoverflow.com/questions/30487056/django-queryset-contains-duplicate-entries
        return queryset.distinct()

    def get(self):
        # Prefilter the allowed tickets
        tickets = self.huser.get_tickets_in_queues().select_related()
        return self.__run__(tickets)

    def get_datatables_context(self, **kwargs):
        """
        This function takes in a list of ticket objects from the views and throws it
        to the datatables on ticket_list.html. If a search string was entered, this
        function filters existing dataset on search string and returns a filtered
        filtered list. The `draw`, `length` etc parameters are for datatables to
        display meta data on the table contents. The returning queryset is passed
        to a Serializer called DatatablesTicketSerializer in serializers.py.
        """
        objects = self.get()
        order_by = '-created'
        draw = int(kwargs.get('draw', [0])[0])
        length = int(kwargs.get('length', [25])[0])
        start = int(kwargs.get('start', [0])[0])
        search_value = kwargs.get('search[value]', [""])[0]
        order_column = kwargs.get('order[0][column]', ['5'])[0]
        order = kwargs.get('order[0][dir]', ["asc"])[0]

        order_column = DATATABLES_ORDER_COLUMN_CHOICES[order_column]
        # django orm '-' -> desc
        if order == 'desc':
            order_column = '-' + order_column

        queryset = objects.all().order_by(order_by)
        total = queryset.count()

        if search_value:  # Dead code currently
            queryset = queryset.filter(get_search_filter_args(search_value))

        count = queryset.count()
        queryset = queryset.order_by(order_column)[start:start + length]
        return {
            'data': DatatablesTicketSerializer(queryset, many=True).data,
            'recordsFiltered': count,
            'recordsTotal': total,
            'draw': draw
        }

    def get_timeline_context(self):
        events = []

        for ticket in self.get():
            for followup in ticket.followup_set.all():
                event = {
                    'start_date': self.mk_timeline_date(followup.date),
                    'text': {
                        'headline': ticket.title + ' - ' + followup.title,
                        'text': (
                            (escape(followup.comment)
                             if followup.comment else _('No text'))
                            +
                            '<br/> <a href="%s" class="btn" role="button">%s</a>'
                            %
                            (reverse('helpdesk:view', kwargs={
                             'ticket_id': ticket.pk}), _("View ticket"))
                        ),
                    },
                    'group': _('Messages'),
                }
                events.append(event)

        return {
            'events': events,
        }

    def mk_timeline_date(self, date):
        return {
            'year': date.year,
            'month': date.month,
            'day': date.day,
            'hour': date.hour,
            'minute': date.minute,
            'second': date.second,
        }
