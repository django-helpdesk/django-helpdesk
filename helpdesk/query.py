from django.db.models import Q

from model_utils import Choices

from base64 import b64encode
from base64 import b64decode
import json


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


def apply_query(queryset, params):
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
    for key in params['filtering'].keys():
        filter = {key: params['filtering'][key]}
        queryset = queryset.filter(**filter)

    search = params.get('search_string', '')
    if search:
        qset = (
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(resolution__icontains=search) |
            Q(submitter_email__icontains=search) |
            Q(ticketcustomfieldvalue__value__icontains=search)
        )

        queryset = queryset.filter(qset)

    sorting = params.get('sorting', None)
    if sorting:
        sortreverse = params.get('sortreverse', None)
        if sortreverse:
            sorting = "-%s" % sorting
        queryset = queryset.order_by(sorting)

    return queryset


ORDER_COLUMN_CHOICES = Choices(
    ('0', 'id'),
    ('2', 'priority'),
    ('3', 'title'),
    ('4', 'queue'),
    ('5', 'status'),
    ('6', 'created'),
    ('7', 'due_date'),
    ('8', 'assigned_to')
)


def query_tickets_by_args(objects, order_by, **kwargs):
    """
    This function takes in a list of ticket objects from the views and throws it
    to the datatables on ticket_list.html. If a search string was entered, this
    function filters existing dataset on search string and returns a filtered
    filtered list. The `draw`, `length` etc parameters are for datatables to
    display meta data on the table contents. The returning queryset is passed
    to a Serializer called DatatablesTicketSerializer in serializers.py.
    """
    draw = int(kwargs.get('draw', None)[0])
    length = int(kwargs.get('length', None)[0])
    start = int(kwargs.get('start', None)[0])
    search_value = kwargs.get('search[value]', None)[0]
    order_column = kwargs.get('order[0][column]', None)[0]
    order = kwargs.get('order[0][dir]', None)[0]

    order_column = ORDER_COLUMN_CHOICES[order_column]
    # django orm '-' -> desc
    if order == 'desc':
        order_column = '-' + order_column

    queryset = objects.all().order_by(order_by)
    total = queryset.count()

    if search_value:
        queryset = queryset.filter(Q(id__icontains=search_value) |
                                   Q(priority__icontains=search_value) |
                                   Q(title__icontains=search_value) |
                                   Q(queue__title__icontains=search_value) |
                                   Q(status__icontains=search_value) |
                                   Q(created__icontains=search_value) |
                                   Q(due_date__icontains=search_value) |
                                   Q(assigned_to__email__icontains=search_value))

    count = queryset.count()
    queryset = queryset.order_by(order_column)[start:start + length]
    return {
        'items': queryset,
        'count': count,
        'total': total,
        'draw': draw
    }
