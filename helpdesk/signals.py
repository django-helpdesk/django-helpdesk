import django.dispatch

# create a signal for *TicketForm
new_ticket_done = django.dispatch.Signal()

# create a signal for ticket_update view
update_ticket_done = django.dispatch.Signal()