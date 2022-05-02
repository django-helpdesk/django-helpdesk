API
===

A REST API (built with ``djangorestframework``) is available in order to list, create, update and delete tickets from other tools thanks to HTTP requests.

If you wish to use it, you have to add this line in your settings::

    HELPDESK_ACTIVATE_API_ENDPOINT = True

You must be authenticated to access the API, the URL endpoint is ``/api/tickets/``. You can configure how you wish to authenticate to the API by customizing the ``DEFAULT_AUTHENTICATION_CLASSES`` key in the ``REST_FRAMEWORK`` setting (more information on this page : https://www.django-rest-framework.org/api-guide/authentication/)

GET
---

Accessing the endpoint ``/api/tickets/`` with a **GET** request will return you the complete list of tickets.

Accessing the endpoint ``/api/tickets/<ticket-id>`` with a **GET** request will return you the data of the ticket you provided the ID.

POST
----

Accessing the endpoint ``/api/tickets/`` with a **POST** request will let you create a new tickets.

You need to provide a JSON body with the following data :

- **queue**: ID of the queue
- **title**: the title (subject) of the ticket
- **description**: the description of the ticket
- **resolution**: an optional text for the resoltuion of the ticket
- **submitter_email**: the email of the ticket submitter
- **assigned_to**: ID of the ticket's assigned user
- **status**: integer corresponding to the status (OPEN=1, REOPENED=2, RESOLVED=3, CLOSED=4, DUPLICATE=5). It is OPEN by default.
- **on_hold**: boolean to indicates if the ticket is on hold
- **priority**: integer corresponding to different degrees of priority 1 to 5 (1 is Critical and 5 is Very Low)
- **due_date**: date representation for when the ticket is due
- **merged_to**: ID of the ticket to which it is merged

Note that ``status`` will automatically be set to OPEN. Also, some fields are not configurable during creation: ``resolution``, ``on_hold`` and ``merged_to``.

Moreover, if you created custom fields, you can add them into the body with the key ``custom_<custom-field-slug>``.

Here is an example of a cURL request to create a ticket (using Basic authentication) ::

    curl --location --request POST 'http://127.0.0.1:8000/api/tickets/' \
    --header 'Authorization: Basic YWRtaW46YWRtaW4=' \
    --header 'Content-Type: application/json' \
    --data-raw '{"queue": 1, "title": "Test Ticket API", "description": "Test create ticket from API", "submitter_email": "test@mail.com", "priority": 4}'

Accessing the endpoint ``/api/users/`` with a **POST** request will let you create a new user.

You need to provide a JSON body with the following data :

- **first_name**: first name
- **last_name**: last name
- **username**: username
- **email**: user email
- **password**: user password

PUT
---

Accessing the endpoint ``/api/tickets/<ticket-id>`` with a **PUT** request will let you update the data of the ticket you provided the ID.

You must include all fields in the JSON body.

PATCH
-----

Accessing the endpoint ``/api/tickets/<ticket-id>`` with a **PATCH** request will let you do a partial update of the data of the ticket you provided the ID.

You can include only the fields you need to update in the JSON body.

DELETE
------

Accessing the endpoint ``/api/tickets/<ticket-id>`` with a **DELETE** request will let you delete the ticket you provided the ID.
