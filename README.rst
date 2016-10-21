django-helpdesk - A Django powered ticket tracker for small businesses.
=======================================================================

.. image:: https://travis-ci.org/django-helpdesk/django-helpdesk.png?branch=master
    :target: https://travis-ci.org/django-helpdesk/django-helpdesk

.. image:: https://codecov.io/gh/django-helpdesk/django-helpdesk/branch/master/graph/badge.svg
  :target: https://codecov.io/gh/django-helpdesk/django-helpdesk

Copyright 2009- Ross Poulton and contributors. All Rights Reserved. See LICENSE for details.

django-helpdesk was formerly known as Jutda Helpdesk, named after the 
company who originally created it. As of January 2011 the name has been 
changed to reflect what it really is: a Django-powered ticket tracker with
contributors reaching far beyond Jutda.

Complete documentation is available in the docs/ directory, or online at http://django-helpdesk.readthedocs.org/.

You can see a demo installation at http://django-helpdesk-demo.herokuapp.com/

Licensing
---------

See the file 'LICENSE' for licensing terms. Note that django-helpdesk is 
distributed with 3rd party products which have their own licenses. See 
LICENSE.3RDPARTY for license terms for included packages.

Dependencies (pre-flight checklist)
-----------------------------------

1. Python 2.7 or 3.4+ (3.4+ support is new, please let us know how it goes)
2. Django (1.7, 1.8, 1.9 and 1.10, preferably 1.9 - Django 1.7 is not supported if you are using Python 3.5)
3. An existing WORKING Django project with database etc. If you
   cannot log into the Admin, you won't get this product working.
4. `pip install django-bootstrap-form` and add `bootstrapform` to `settings.INSTALLED_APPS`
5. `pip install django-markdown-deux` and add `markdown_deux` to `settings.INSTALLED_APPS`
6. `pip install email-reply-parser` to get smart email reply handling
7. Add 'django.contrib.sites' to settings.INSTALLED_APPS, ensure there is at least 1 site created.

**NOTE REGARDING SQLITE AND SEARCHING:**
If you use sqlite as your database, the search function will not work as
effectively as it will with other databases due to its inability to do
case-insensitive searches. It's recommended that you use PostgreSQL or MySQL
if possible. For more information, see this note in the Django documentation:
http://docs.djangoproject.com/en/dev/ref/databases/#sqlite-string-matching

When you try to do a keyword search using sqlite, a message will be displayed
to alert you to this shortcoming. There is no way around it, sorry.

**NOTE REGARDING MySQL:**
If you use MySQL, with most default configurations you will receive an error 
when creating the database tables as we populate a number of default templates 
in languages other than English. 

You must create the database the holds the django-helpdesk tables using the 
UTF-8 collation; see the MySQL manual for more information: 
http://dev.mysql.com/doc/refman/5.1/en/charset-database.html

If you do NOT do this step, and you only want to use English-language templates,
you can continue however you will receive a warning when running the 'migrate'
commands.

Fresh Django Installations
--------------------------

If you're on a brand new Django installation, make sure you do a ``migrate``
**before** adding ``helpdesk`` to your ``INSTALLED_APPS``. This will avoid 
errors with trying to create User settings.

Upgrading from previous versions
--------------------------------

If you are upgrading from a previous version of django-helpdesk that used
migrations, get an up to date version of the code base (eg by using 
`git pull` or `pip install --upgrade django-helpdesk`) then migrate the database::

    python manage.py migrate helpdesk --db-dry-run # DB untouched
    python manage.py migrate helpdesk 

Lastly, restart your web server software (eg Apache) or FastCGI instance, to 
ensure the latest changes are in use.

If you are using django-helpdesk pre-migrations (ie pre-2011) then you're
on your own, sorry.

You can continue to the 'Initial Configuration' area, if needed.

Installation
------------

``pip install django-helpdesk``

For further installation information see docs/install.html and docs/configuration.html

Contributing
------------

If you want to help translate django-helpdesk into languages other than English, we encourage you to make use of our Transifex project.

https://www.transifex.com/django-helpdesk/django-helpdesk/

Feel free to request access to contribute your translations.

Pull requests for all other changes are welcome. We're currently trying to add test cases wherever possible, so please continue to include tests with pull requests.