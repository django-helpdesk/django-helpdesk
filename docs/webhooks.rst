Registering webhooks to be notified of helpesk events
-----------------------------------------------------

You can register webhooks to allow third party apps to be notified of helpdesk events. Webhooks can be registered in one of two ways:

1. Setting the following environement variables to a comma separated list of URLs; ``HELPDESK_NEW_TICKET_WEBHOOK_URLS``& ``HELPDESK_FOLLOWUP_WEBHOOK_URLS``.

2. Adding getter functions to your ``settings.py``. These should return a list of strings (urls); ``HELPDESK_GET_NEW_TICKET_WEBHOOK_URLS`` & ``HELPDESK_GET_FOLLOWUP_WEBHOOK_URLS``.

3. You can optionally set ``HELPDESK_WEBHOOK_TIMEOUT`` which defaults to 3 seconds. Warning, however, webhook requests are sent out sychronously on ticket update. If your webhook handling server is too slow, you should fix this rather than causing helpdesk freezes by messing with this variable.

Once these URLs are configured, a serialized copy of the ticket object will be posted to each of these URLs each time a ticket is created or followed up on respectively.
