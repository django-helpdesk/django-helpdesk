from django.db.models import Q
from django.core.cache import cache
from django.urls import reverse
from django.utils.html import escape
from django.utils.translation import ugettext as _

from base64 import b64encode
from base64 import b64decode
import json
from functools import reduce
import operator

from helpdesk.serializers import DatatablesTicketSerializer


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


def query_to_dict(results, descriptions):
    """
    Replacement method for cursor.dictfetchall() as that method no longer
    exists in psycopg2, and I'm guessing in other backends too.

    Converts the results of a raw SQL query into a list of dictionaries, suitable
    for use in templates etc.
    """

    output = []
    for data in results:
        row = {}
        i = 0
        for column in descriptions:
            row[column[0]] = data[i]
            i += 1

        output.append(row)
    return output


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
            Q(ticketcustomfieldvalue__value__icontains=subsearch) |  # TODO need to add custom stuff to querying
            Q(created__icontains=subsearch) |
            Q(due_date__icontains=subsearch)
        )
    return filter


DATATABLES_ORDER_COLUMN_CHOICES = dict([
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
])

# Commented out fields will have further filtering in the front-end since they are changed while rendering
DATATABLES_FILTER_COLUMN_CHOICES = dict([
    ('0', 'id__icontains'),
    # ('1', 'title__icontains'),
    ('2', 'priority__icontains'),
    ('3', 'queue__title__icontains'),
    # ('4', 'status__icontains'),
    # ('5', 'created__icontains'),
    # ('6', 'due_date__icontains'),
    ('7', 'assigned_to__email__icontains'),
    ('8', 'submitter_email__icontains'),
    # ('9', 'time_spent__icontains'),
    ('10', 'kbitem__title__icontains'),
])


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
        self.params = query_params if query_params else query_from_base64(base64query)
        self.base64 = base64query if base64query else query_to_base64(query_params)
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
        filter_or = self.params.get('filtering_or', {})
        queryset = queryset.filter((Q(**filter) | Q(**filter_or)) & self.get_search_filter_args())
        sorting = self.params.get('sorting', None)
        if sorting:
            sortreverse = self.params.get('sortreverse', None)
            if sortreverse:
                sorting = "-%s" % sorting
            queryset = queryset.order_by(sorting)
        # https://stackoverflow.com/questions/30487056/django-queryset-contains-duplicate-entries
        return queryset.distinct()

    def get_cache_key(self):
        return str(self.huser.user.pk) + ":" + self.base64

    def refresh_query(self):
        tickets = self.huser.get_tickets_in_queues().select_related()
        ticket_qs = self.__run__(tickets)
        cache.set(self.get_cache_key(), ticket_qs, timeout=3600)
        return ticket_qs

    def get(self):
        # Prefilter the allowed tickets
        objects = cache.get(self.get_cache_key())
        if objects is not None:
            return objects
        return self.refresh_query()

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
        length = int(kwargs.get('length', [25])[0])
        start = int(kwargs.get('start', [0])[0])

        search_value = kwargs.get('search[value]', [""])[0]
        draw = int(kwargs.get('draw', [0])[0])

        sort_column = kwargs.get('order[0][column]', ['5'])[0]
        sort_order = kwargs.get('order[0][dir]', ["asc"])[0]
        # Validating sort data
        if sort_column != '0':
            sort_column = DATATABLES_ORDER_COLUMN_CHOICES[sort_column]
        elif 'sorting' in self.params and self.params['sorting'] in DATATABLES_ORDER_COLUMN_CHOICES.values():
            sort_column = self.params['sorting']
            sort_order = 'desc' if self.params['sortreverse'] is None else 'asc'

        if sort_order == 'desc':
            sort_column = '-' + sort_column  # django orm '-' -> desc

        queryset = objects.all()  # .order_by(order_by)
        total = queryset.count()

        if search_value:  # Dead code currently
            queryset = queryset.filter(get_search_filter_args(search_value))

        # Collect and apply column-based filters
        column_filters = {}
        for i, field in DATATABLES_FILTER_COLUMN_CHOICES.items():
            col_name = 'columns[%s][search][value]' % i
            column_filter = kwargs.get(col_name, [None])[0]
            if column_filter:
                column_filters[field] = column_filter
        if column_filters:
            filters = reduce(operator.and_, (Q(**d) for d in [dict([i]) for i in column_filters.items()]))
            queryset = queryset.filter(filters)

        count = queryset.count()
        queryset = queryset.order_by(sort_column)[start:start + length]
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
                            (escape(followup.comment) if followup.comment else _('No text'))
                            +
                            '<br/> <a href="%s" class="btn" role="button">%s</a>'
                            %
                            (reverse('helpdesk:view', kwargs={'ticket_id': ticket.pk}), _("View ticket"))
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
