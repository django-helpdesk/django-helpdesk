Welcome to django-helpdesk's documentation!
===========================================

django-helpdesk is a Django application to manage helpdesk tickets for your internal helpdesk. It was formerly known as Jutda Helpdesk.

How Does It Look?
-----------------

You can see a demo installation at http://demo.jutdahelpdesk.com

Quick Start
-----------

django-helpdesk is just a Django application with models, views, templates, and some media. If you're comfortable with Django just try ``pip install django-helpdesk``. If not, continue to read the Installation document.

Key Features
------------

django-helpdesk has been designed for small businesses who need to recieve, manage and respond to requests for help from customers. In this context *'customers'* may be external users, or other people within your company.

* Tickets can be opened vi a email
* Multiple queues / categories of tickets
* Integrated FAQ / knowledgebase

Customer-facing Capabilities
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Customers (who are not 'staff' users in Django) can:

1. Browse your knowledgebase / FAQ
2. Submit support requests via web/email
3. Review open and closed requests they submitted

Staff Capabilities
~~~~~~~~~~~~~~~~~~~~

If a user is a staff member, they get general helpdesk access, including:

1. See the ticket dashboard showing unassigned tickets and basic status of the helpdesk
2. Review the tickets assigned to them
3. Search through all tickets, open and closed
4. Save their searches for future use
5. Follow up or respond to tickets
6. Assign tickets to themselves or other staff members
7. Resolve tickets


Licensing
---------
django-helpdesk is released under the BSD license, however it packages 3rd party applications which may be using a different license. More details can be found in the :doc:`license` documentation.

Dependencies
------------

1. Python 2.4+
2. Django (1.2 or newer)
3. South for database migrations (highly recommended, but not required). Download from http://south.aeracode.org/
4. An existing **working** Django project with database etc. If you cannot log into the Admin, you won't get this product working!

Translation
-----------

.. image:: http://www.transifex.net/projects/p/django-helpdesk/resource/core/chart/image_png

If you want to help translate django-helpdesk into languages other than English, we encourage you to make use of our Transifex project.

http://www.transifex.net/projects/p/django-helpdesk/resource/core/

Feel free to request access to contribute your translations.

Contents:
---------

.. toctree::
   :maxdepth: 2
   :glob:

   license
   install
   configuration
   settings
   spam
   custom_fields
   api
   contributing

