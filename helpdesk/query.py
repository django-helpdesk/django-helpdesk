from django.core.cache import cache
from django.db.models import Q, Count, Max, F, Value, CharField
from django.db.models.functions import Concat
from django.urls import reverse
from django.utils.html import escape
from django.utils.translation import ugettext as _

from base64 import b64encode
from base64 import b64decode
import json
from functools import reduce
import operator

from helpdesk.decorators import is_helpdesk_staff
from helpdesk.models import Ticket, CustomField, FormType
from helpdesk.serializers import DatatablesTicketSerializer
from seed.landing.models import SEEDUser as User


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
    # Returns a list of Q objects that will search all built-in fields of tickets for keywords.
    # The search list comes from the query box, "Keywords".

    if search.startswith('queue:'):
        return Q(queue__title__icontains=search[len('queue:'):])
    if search.startswith('priority:'):
        return Q(priority__icontains=search[len('priority:'):])
    filter = Q()
    for subsearch in search.split("OR"):
        if subsearch:
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
                Q(due_date__icontains=subsearch) |
                Q(contact_name__icontains=subsearch) |
                Q(contact_email__icontains=subsearch) |
                Q(building_name__icontains=subsearch) |
                Q(building_address__icontains=subsearch) |
                Q(pm_id__icontains=subsearch) |
                Q(building_id__icontains=subsearch)
            )
    return filter


DATATABLES_ORDER_COLUMN_CHOICES = dict([
    ('0', 'id'),
    ('1', 'title'),
    ('2', 'priority'),
    ('3', 'queue'),
    ('4', 'status'),
    ('5', 'assigned_to'),
    ('6', 'submitter_email'),
    ('7', 'paired_count'),
    ('8', 'created'),
    ('9', 'last_reply'),
    ('10', 'due_date'),
    # ('11', 'time_spent'),
    ('12', 'kbitem'),
])

DATATABLES_DJANGO_FILTER_COLUMN_CHOICES = [
    ('0', 'id__icontains'),
    ('3', 'queue__title__icontains'),
    ('6', 'submitter_email__icontains'),
    ('12', 'kbitem__title__icontains'),
]

ASSIGNED_TO_FILTER_FORMATS = [
    ('5', 'assigned_to__email__icontains'),
    ('5', 'assigned_to__first_name__icontains'),
    ('5', 'assigned_to__last_name__icontains'),
    ('5', 'assigned_to__username__icontains'),
]

# These fields go through some post-processing, which is why django filters won't work and why they aren't in the
# above dict
DATATABLES_CUSTOM_FILTER_COLUMN_CHOICES = dict([
    ('1', 'title'),                 # [id]. [title]
    ('2', 'priority'),              # [1:5 => Critical/High/.../Low]
    ('4', 'status'),                # [1:7 => Open/Closed../New]
    ('7', 'paired_count'),          # Sum of ticket.beam_property and ticket.beam_taxlot
    ('8', 'created'),               # [datetime object => humanized time]
    ('9', 'last_reply'),       # [followup datetime object => humanized time]
    ('10', 'due_date'),              # [datetime object => humanized time]
    ('11', 'time_spent'),           # "{0:02d}h:{1:02d}m"
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
        if 'paired_count__lte' in filter or 'paired_count__gte' in filter:
            queryset = queryset.annotate(paired_count=Count('beam_property') + Count('beam_taxlot'))
        if 'last_reply__lte' in filter or 'last_reply__gte' in filter:
            queryset = queryset.annotate(last_reply=Max('followup__date'))
        queryset = queryset.filter((Q(**filter) | Q(**filter_or)) & self.get_search_filter_args())
        sorting = self.params.get('sorting', None)
        if sorting:
            sortreverse = self.params.get('sortreverse', None)
            if sortreverse:
                sorting = "-%s" % sorting
            if 'paired_count' in sorting:
                queryset = queryset.annotate(paired_count=Count('beam_property') + Count('beam_taxlot')).order_by(
                    sorting)
            else:
                queryset = queryset.order_by(sorting)
        # https://stackoverflow.com/questions/30487056/django-queryset-contains-duplicate-entries
        return queryset.distinct()

    def get_cache_key(self):
        return str(self.huser.user.pk) + ":" + self.base64

    def refresh_query(self):
        tickets = self.huser.get_tickets_in_queues().select_related(
            'queue', 'ticket_form', 'assigned_to').prefetch_related(
            'followup_set__user', 'beam_property', 'beam_taxlot'
        )
        ticket_qs = self.__run__(tickets)
        cache.set(self.get_cache_key(), ticket_qs, timeout=3600)
        return ticket_qs

    def get(self):
        # Prefilter the allowed tickets
        objects = cache.get(self.get_cache_key())
        if objects is not None:
            return objects
        return self.refresh_query()

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

        sort_column = kwargs.get('order[0][column]', ['0'])[0]
        sort_order = kwargs.get('order[0][dir]', ["asc"])[0]
        # Validating sort data
        if sort_column != '0' and sort_column in DATATABLES_ORDER_COLUMN_CHOICES.keys():
            sort_column = DATATABLES_ORDER_COLUMN_CHOICES[sort_column]
        elif sort_column != '0' and sort_column not in DATATABLES_ORDER_COLUMN_CHOICES.keys():
            sort_column = 'extra_data__' + kwargs.get('order[0][name]', [''])[0]
        elif 'sorting' in self.params and self.params['sorting'] in DATATABLES_ORDER_COLUMN_CHOICES.values():
            sort_column = self.params['sorting']
            sort_order = 'desc' if self.params['sortreverse'] is None else 'asc'

        if sort_order == 'desc':
            sort_column = '-' + sort_column  # django orm '-' -> desc

        queryset = objects.all()  # .order_by(order_by)
        total = queryset.count()
        all_ticket_ids = list(objects.values_list('id', flat=True))

        if search_value:  # Dead code currently
            queryset = queryset.filter(get_search_filter_args(search_value))

        # Collect and apply column-based filters that can be done using Django Filtering (Q functions)
        filters_list = []
        for i, choices in enumerate([DATATABLES_DJANGO_FILTER_COLUMN_CHOICES, ASSIGNED_TO_FILTER_FORMATS]):
            op = operator.and_ if i == 0 else operator.or_
            for col_index, field in choices:
                column_filter_key = 'columns[%s][search][value]' % col_index
                column_filter = kwargs.get(column_filter_key, [None])[0]
                if column_filter:
                    filters_list.append({field: column_filter})
            if filters_list:
                filters = reduce(op, (Q(**d) for d in filters_list))
                queryset = queryset.filter(filters)
                filters_list = []

        if 'paired_count' in sort_column:
            queryset = queryset.annotate(paired_count=Count('beam_property') + Count('beam_taxlot'))
        elif 'last_reply' in sort_column:
            queryset = queryset.annotate(last_reply=Max('followup__date'))
        elif 'title' in sort_column:
            queryset = queryset.annotate(
                modified_title=Concat(F('id'), Value('. '), F('title'), output_field=CharField()))
            sort_column = sort_column.replace('title', 'modified_title')

        queryset = queryset.order_by(sort_column)

        data = DatatablesTicketSerializer(queryset, many=True).data

        extra_data_columns = {}
        # If filter options chooses one queue, get extra_data columns to show in ticket list
        if len(self.params['filtering'].get('queue__id__in', [])) == 1:
            extra_data_columns, data = process_extra_data_columns(data, self.params['filtering']['queue__id__in'][0])

        # Collect and apply column-based filters that CAN'T be done using Django because of post-processing
        data = do_custom_filtering(data, extra_data_columns, **kwargs)

        # If we filter after post-processing in the ticket_list js, we wouldn't have the correct count value since that
        # page only sees the paginated subset of 10-25-50 or 100 Won't be able to paginate properly with that method
        count = len(data)
        data = data[start: start + length]

        return {
            'data': data,
            'recordsFiltered': count,   # Total records, after filtering (i.e. the total number of records after filtering has been applied - not just the number of records being returned for this page of data).
            'recordsTotal': total,      # Total records, before filtering (i.e. the total number of records in the database)
            'draw': draw,
            'all_ticket_ids': all_ticket_ids,
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


def do_custom_filtering(data, extra_data_columns, **kwargs):
    # Update filter choices with extra_data columns, keeping the same format [int: col_name]
    CUSTOM_FILTER_COLUMN_CHOICES = dict(DATATABLES_CUSTOM_FILTER_COLUMN_CHOICES)
    num_columns = len(DATATABLES_ORDER_COLUMN_CHOICES) + 1  # Add + 1 since time_spent is commented out
    CUSTOM_FILTER_COLUMN_CHOICES.update(
        dict(zip(range(num_columns, num_columns + len(extra_data_columns)), extra_data_columns.keys()))
    )

    for i, field in CUSTOM_FILTER_COLUMN_CHOICES.items():
        column_filter_key = 'columns[%s][search][value]' % i
        column_filter = kwargs.get(column_filter_key, [None])[0]
        if column_filter:
            column_filter = column_filter.lower()
            for j, row in enumerate(data):
                if row[field] is not None:
                    # Handling post-processing
                    if field == 'title':
                        contents = str(row['id']) + '. ' + row[field]
                    else:       # Contains ['priority', 'status', 'time_spent'] and any extra_data
                        contents = str(row[field])

                    contents = contents.lower()
                    # Apply filtering and set placeholder var to later prune data
                    if 'remove' in data[j]:
                        if not data[j]['remove']:
                            data[j]['remove'] = column_filter not in contents
                    else:
                        data[j]['remove'] = column_filter not in contents
                else:
                    data[j]['remove'] = True    # No data found and a filter is applied, gets pruned

    for row in list(data):
        if 'remove' in row and row['remove']:
            data.remove(row)

    return data


def process_extra_data_columns(data, queue_id):
    """
    Get the list of extra_data columns in all of the Tickets. Remove it as a nested field and add it back as just
    another field
    :param data: json data from DatatablesTicketSerializer
    :param queue_id: Queue id for tickets being serialized in data
    :return: modified json data where nested extra_data field is expanded
    """
    extra_data_cols = get_extra_data_columns(queue_id)

    # Replace extra_data with individual columns
    for row in data:
        row['extra_data'] = {} if row['extra_data'] == '' else row['extra_data']
        # Add in any other col not in extra_data
        missing_data = {k: '' for k in extra_data_cols.keys() if k not in row['extra_data'].keys()}
        row['extra_data'].update(missing_data)

        # Replace extra_data with the cols themselves
        extra_data = row.pop('extra_data')
        row.update(extra_data)

    return extra_data_cols, data


def get_extra_data_columns(queue_id=None):
    """
    Helper function to get all Form extra data fields in a Queue
    """
    extra_data_columns = {}
    forms = FormType.objects.filter(queue_id=queue_id)
    for form in forms:
        mappings = form.get_extra_fields_mapping()
        for field_name, label in mappings.items():
            if field_name not in extra_data_columns:
                extra_data_columns[field_name] = label

    return extra_data_columns

