Registering webhooks to be notified of helpesk events
-----------------------------------------------------

You can register webhooks to allow third party apps to be notified of helpdesk events. Webhooks can be registered in one of two ways:

1. Setting the following environement variables to a comma separated list of URLs; ``HELPDESK_NEW_TICKET_WEBHOOK_URLS``& ``HELPDESK_FOLLOWUP_WEBHOOK_URLS``.

2. Adding getter functions to your ``settings.py``. These should return a list of strings (urls); ``HELPDESK_GET_NEW_TICKET_WEBHOOK_URLS`` & ``HELPDESK_GET_FOLLOWUP_WEBHOOK_URLS``.

3. You can optionally set ``HELPDESK_WEBHOOK_TIMEOUT`` which defaults to 3 seconds. Warning, however, webhook requests are sent out sychronously on ticket update. If your webhook handling server is too slow, you should fix this rather than causing helpdesk freezes by messing with this variable.

Once these URLs are configured, a serialized copy of the ticket object will be posted to each of these URLs each time a ticket is created or followed up on respectively.


Signals
--------------

Webhooks are triggered through `Django Signals <https://docs.djangoproject.com/en/stable/topics/signals/>_`.

The two available signals are:
  - new_ticket_done
  - update_ticket_done

You have the opportunity to listen to those in your project if you have post processing workflows outside of webhooks::

  
  from django.dispatch import receiver
  from helpdesk.signals import new_ticket_done, update_ticket_done
  
  @receiver(new_ticket_done)
  def process_new_ticket(sender, ticket, **kwargs):
      "Triggers this code when a ticket is created."
      pass
      
  @receiver(update_ticket_done)
  def process_followup_update(sender, followup, **kwargs):
      "Triggers this code when a follow-up is created."
      pass
