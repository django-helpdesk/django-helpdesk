Custom Fields
=============

django-helpdesk supports custom fields on the ``Ticket`` model. These fields are created by using the Django administration tool, and are shown on both the public and staff submission forms. You can use most Django field types including text, integer, boolean, and list.

The demo at http://django-helpdesk-demo.herokuapp.com contains an example of each type of custom field, including a mix of mandatory and optional fields.

Custom fields are relatively inefficient; you can search them, but this might degrade performance of your installation if you make use of custom fields. They can be useful for tracking extra information that your organisation needs but that isn't supported out of the box.
