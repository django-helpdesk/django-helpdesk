django-helpdesk - A Django powered ticket tracker for small businesses.
=======================================================================

.. image:: https://dev.azure.com/django-helpdesk/django-helpdesk/_apis/build/status/django-helpdesk.django-helpdesk?branchName=master
  :target: https://dev.azure.com/django-helpdesk/django-helpdesk/_build/latest?definitionId=1&branchName=master
  :alt: Build Status

.. image:: https://codecov.io/gh/django-helpdesk/django-helpdesk/branch/develop/graph/badge.svg
  :target: https://codecov.io/gh/django-helpdesk/django-helpdesk

Copyright 2009-2023 Ross Poulton and django-helpdesk contributors. All Rights Reserved.
See LICENSE for details.

django-helpdesk was formerly known as Jutda Helpdesk, named after the
company which originally created it. As of January 2011 the name has been
changed to reflect what it really is: a Django-powered ticket tracker with
contributors reaching far beyond Jutda.

Complete documentation is available in the docs/ directory,
or online at http://django-helpdesk.readthedocs.org/.


Demo Quickstart
---------------

`django-helpdesk` includes a basic demo Django project so that you may easily
get started with testing or developing `django-helpdesk`. The demo project
resides in the `demo/` top-level folder.

It's likely that you can start up a demo project server by running
only the command (consider creating a virtualenv before):

    make rundemo

or with docker::

    docker build . -t demodesk
    docker run --rm -v "$PWD:/app" -p 8080:8080 demodesk

then pointing your web browser at http://localhost:8080 (log in as user
`admin`` with password `Test1234`).

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

* |standalone_icon| For **standalone** installation, refer to `standalone documentation <./docs/standalone.rst>`_.

* |django_icon| To **integrate** with an existing Django application, follow the guidelines in `installation documentation <./docs/install.rst>`_ and `configuration documentation <./docs/configuration.rst>`_.

.. |standalone_icon| image:: helpdesk/static/helpdesk/img/icon512.png
   :height: 24px
   :width: 24px
   :align: middle

.. |django_icon| image:: helpdesk/static/helpdesk/img/django-logo-positive.png
   :height: 24px
   :width: 60px
   :align: middle

Developer Environment
---------------------

Follow these steps to set up your development environment to contribute to helpdesk:
 - check out the helpdesk app to your local file system::

    git clone https://github.com/django-helpdesk/django-helpdesk.git
 
 - install a virtual environment and activate it::
  
    python -m venv .venv && source .venv/bin/activate

 - install the requirements for development::

    pip install -r requirements.txt -r requirements-dev.txt

 - you can install the requirements for testing as well::

    pip install -r requirements-testing.txt

To deactivate the virtual environment, use ``deactivate``. Then to reactivate it, just run::

    source .venv/bin/activate

To see option for the Makefile run: `make`

The project enforces a standardized formatting in the CI/CD pipeline. To ensure you have the correct formatting run::

    make checkformat
    
To auto format any code use this::

    make format

Testing
-------

From the command line you can run the tests using: `make test`

See `quicktest.py` for usage details.

If you need to create tests for new features, add your tests in a test file to the `tests` module and call them in the test VENV with::
    python quicktest.py helpdesk.tests.test_my_new_features -v 2

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

.. _note: https://docs.djangoproject.com/en/dev/ref/databases/#substring-matching-and-case-sensitivity

