import django.dispatch

# create a signal for ticket updates
update_ticket_done = django.dispatch.Signal()