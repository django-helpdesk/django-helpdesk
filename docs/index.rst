Welcome to django-helpdesk's documentation!
===========================================

django-helpdesk is a Django application to manage helpdesk tickets for your internal helpdesk. It was formerly known as Jutda Helpdesk.

Contents
--------

.. toctree::
   :maxdepth: 2
   :glob:

   standalone
   install
   upgrade
   configuration
   settings
   spam
   custom_fields
   custom_templates
   api
   webhooks
   iframe_submission
   teams
   license

Quick Start
-----------

django-helpdesk is just a Django application with models, views, templates, and some media. If you're comfortable with Django just try ``pip install django-helpdesk``. If not, continue to read the Installation document.

Key Features
------------

django-helpdesk has been designed for small businesses who need to receive, manage and respond to requests for help from customers. In this context *'customers'* may be external users, or other people within your company.

* Tickets can be opened via email
* Multiple queues / categories of tickets
* Integrated FAQ / knowledgebase
* API to manage tickets

Customer-facing Capabilities
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Customers (who are not 'staff' users in Django) can:

1. Browse your knowledgebase / FAQ
2. Submit support requests via web/email
3. Review open and closed requests they submitted

Staff Capabilities
~~~~~~~~~~~~~~~~~~

If a user is a staff member, they get general helpdesk access, including:

1. See the ticket dashboard showing unassigned tickets and basic status of the helpdesk
2. Review the tickets assigned to them
3. Search through all tickets, open and closed
4. Save their searches for future use
5. Follow up or respond to tickets
6. Assign tickets to themselves or other staff members
7. Resolve tickets
8. Merge multiple tickets into one
9. Create, Read, Update and Delete tickets through a REST API

Optionally, their access to view tickets, both on the dashboard and through searches and reports, may be restricted by a list of queues to which they have been granted membership. Create and update permissions for individual tickets are not limited by this optional restriction.

Licensing
---------
django-helpdesk is released under the BSD license, however it packages 3rd party applications which may be using a different license. More details can be found in the :doc:`license` documentation.
