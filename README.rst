django-helpdesk - A Django powered ticket tracker for small businesses.
=======================================================================

[![Build Status](https://dev.azure.com/django-helpdesk/django-helpdesk/_apis/build/status/django-helpdesk.django-helpdesk?branchName=master)](https://dev.azure.com/django-helpdesk/django-helpdesk/_build/latest?definitionId=1&branchName=master)

.. image:: https://codecov.io/gh/django-helpdesk/django-helpdesk/branch/develop/graph/badge.svg
  :target: https://codecov.io/gh/django-helpdesk/django-helpdesk

Copyright 2009-2021 Ross Poulton and django-helpdesk contributors. All Rights Reserved.
See LICENSE for details.

django-helpdesk was formerly known as Jutda Helpdesk, named after the
company which originally created it. As of January 2011 the name has been
changed to reflect what it really is: a Django-powered ticket tracker with
contributors reaching far beyond Jutda.

Complete documentation is available in the docs/ directory,
or online at http://django-helpdesk.readthedocs.org/.

You can see a demo installation at https://django-helpdesk-demo.herokuapp.com/,
or run a demo locally in just a couple steps!

Demo Quickstart
---------------

`django-helpdesk` includes a basic demo Django project so that you may easily
get started with testing or developing `django-helpdesk`. The demo project
resides in the `demo/` top-level folder.

It's likely that you can start up a demo project server by running
only the command::

    make rundemo

then pointing your web browser at `localhost:8080`.

For more information and options, please read the `demo/README.rst` file.

**NOTE REGARDING SQLITE AND SEARCHING:**
The demo project uses `sqlite` as its database. Sqlite does not allow
case-insensitive searches and so the search function may not work as
effectively as it would on other database such as PostgreSQL or MySQL
that does support case-insensitive searches.
For more information, see this note_ in the Django documentation.

When you try to do a keyword search using `sqlite`, a message will be displayed
to alert you to this shortcoming. There is no way around it, sorry.

Installation
------------

`django-helpdesk` requires:

* Python 3.8+
* Django 3.2 LTS highly recommended (early adopters may test Django 4)

You can quickly install the latest stable version of `django-helpdesk`
app via `pip`::

    pip install django-helpdesk

You may also check out the `master` branch on GitHub, and install manually::

    python setup.py install

Either way, you will need to add `django-helpdesk` to an existing
Django project.

For further installation information see `docs/install.html`
and `docs/configuration.html`

Testing
-------

See `quicktest.py` for usage details.

Upgrading from previous versions
--------------------------------

If you are upgrading from a previous version of `django-helpdesk` that used
migrations, get an up to date version of the code base (eg by using
`git pull` or `pip install --upgrade django-helpdesk`) then migrate the database::

    python manage.py migrate helpdesk --db-dry-run # DB untouched
    python manage.py migrate helpdesk

Lastly, restart your web server software (eg Apache) or FastCGI instance, to
ensure the latest changes are in use.

Unfortunately we are unable to assist if you are upgrading from a
version of `django-helpdesk` prior to migrations (ie pre-2011).

You can continue to the 'Initial Configuration' area, if needed.

Contributing
------------

We're happy to include any type of contribution! This can be:

* back-end python/django code development
* front-end web development (HTML/Javascript, especially jQuery)
* language translations
* writing improved documentation and demos

For more information on contributing, please see the `CONTRIBUTING.rst` file.


Licensing
---------

django-helpdesk is licensed under terms of the BSD 3-clause license.
See the `LICENSE` file for full licensing terms.

Note that django-helpdesk is distributed with 3rd party products which
have their own licenses. See LICENSE.3RDPARTY for license terms for
included packages.

.. _note: http://docs.djangoproject.com/en/dev/ref/databases/#sqlite-string-matching

