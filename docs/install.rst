Installation
============

``django-helpdesk`` installation isn't difficult, but it requires you have a bit of existing know-how about Django.


Prerequisites
-------------

Before getting started, ensure your system meets the following recommended dependencies:

* Python 3.8+
* Django 2.2 LTS or 3.2 LTS (strongly recommend migrating to 3.2 LTS as soon as possible)
  
Ensure any extra Django modules you wish to use are compatible before continuing.

**NOTE**: Python 2.7 support was deprecated in ``django-helpdesk`` as of version 0.2.x
and completely removed in version 0.3.0. Users that still need Python 2 support should
remain on version 0.2.x.


Getting The Code
----------------

Installing using PIP
~~~~~~~~~~~~~~~~~~~~

Try using ``pip install django-helpdesk``. Go and have a beer to celebrate Python packaging.

Checkout ``master`` from git (Cutting Edge)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you're planning on editing the code or just want to get whatever is the latest and greatest, you can clone the official Git repository with ``git clone git://github.com/django-helpdesk/django-helpdesk.git``. We use the ``master`` branch as our development branch for the next major release of ``django-helpdesk``.

Copy the ``helpdesk`` folder into your ``PYTHONPATH``.

I just want a .tar.gz!
~~~~~~~~~~~~~~~~~~~~~~

You can download the latest PyPi package from http://pypi.python.org/pypi/django-helpdesk/

Download, extract, and drop ``helpdesk`` into your ``PYTHONPATH``

Adding To Your Django Project
-----------------------------

If you're on a brand new Django installation, make sure you do a ``migrate``
**before** adding ``helpdesk`` to your ``INSTALLED_APPS``. This will avoid
errors with trying to create User settings.

1. Edit your ``settings.py`` file and add ``helpdesk`` to the ``INSTALLED_APPS`` setting. You also need ``django.contrib.admin`` in ``INSTALLED_APPS`` if you haven't already added it. eg::

    INSTALLED_APPS = (
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.sites',  # Required for determining domain url for use in emails
        'django.contrib.admin',  # Required for helpdesk admin/maintenance
        'django.contrib.humanize',  # Required for elapsed time formatting
        'bootstrap4form', # Required for nicer formatting of forms with the default templates
        'account',  # Required by pinax-teams
        'pinax.invitations',  # required by pinax-teams
        'pinax.teams',  # team support
        'reversion',  # required by pinax-teams
        'helpdesk',  # This is us!
    )

   Note: you do not need to use pinax-teams. To dissable teams see the :doc:`teams` section.

   Your ``settings.py`` file should also define a ``SITE_ID`` that allows multiple projects to share
   a single database, and is required by ``django.contrib.sites`` in Django 1.9+.
   If you aren't running multiple sites, you can simply add a default ``SITE_ID`` to ``settings.py``::

     SITE_ID = 1

2. Make sure django-helpdesk is accessible via ``urls.py``. Add the following line to ``urls.py``::

     url(r'helpdesk/', include('helpdesk.urls')),

   Note that you can change 'helpdesk/' to anything you like, such as 'support/' or 'help/'. If you want django-helpdesk to be available at the root of your site (for example at http://support.mysite.tld/) then the line will be as follows::

     url(r'', include('helpdesk.urls', namespace='helpdesk')),

   This line will have to come *after* any other lines in your urls.py such as those used by the Django admin.

   Note that the `helpdesk` namespace is no longer required for Django 1.9+ and you can use a different namespace.
   However, it is recommended to use the default namespace name for clarity.

3. Create the required database tables.

   Migrate using Django migrations::

     ./manage.py migrate helpdesk

4. Include your static files in your public web path::

      python manage.py collectstatic

5. Inside your ``MEDIA_ROOT`` folder, inside the ``helpdesk`` folder, is a folder called ``attachments``. Ensure your web server software can write to this folder - something like this should do the trick::

      chown www-data:www-data attachments/
      chmod 700 attachments

   (substitute www-data for the user / group that your web server runs as, eg 'apache' or 'httpd')

   If all else fails, you could ensure all users can write to it::

      chmod 777 attachments/

   But this is NOT recommended, especially if you're on a shared server.

6. Ensure that your ``attachments`` folder has directory listings turned off, to ensure users don't download files that they are not specifically linked to from their tickets.

   If you are using Apache, put a ``.htaccess`` file in the ``attachments`` folder with the following content::

      Options -Indexes

   You will also have to make sure that ``.htaccess`` files aren't being ignored.

   Ideally, accessing http://MEDIA_URL/helpdesk/attachments/ will give you a 403 access denied error.

7. If you already have a view handling your logins, then great! If not, add the following to ``settings.py`` to get your Django installation to use the login view included in ``django-helpdesk``::

      LOGIN_URL = '/helpdesk/login/'

   Alter the URL to suit your installation path.

8. Load initial e-mail templates, otherwise you will not be able to send e-mail::

        python manage.py loaddata emailtemplate.json

9. If you intend on using local mail directories for processing email into tickets, be sure to create the mail directory before adding it to the queue in the Django administrator interface. The default mail directory is ``/var/lib/mail/helpdesk/``. Ensure that the directory has appropriate permissions so that your Django/web server instance may read and write files from this directory.

   Note that by default, any mail files placed in your local directory will be permanently deleted after being successfully processed. It is strongly recommended that you take further steps to save emails if you wish to retain backups.

   Also, be aware that if a disk error occurs and the local file is not deleted, the mail may be processed multiple times and generate duplicate tickets until the file is removed. It is recommended to monitor log files for ERRORS when a file is unable to be deleted.

Upgrading from previous versions
--------------------------------

If you are upgrading from a previous version of django-helpdesk that used
migrations, get an up to date version of the code base (eg by using
``git pull`` or ``pip install --upgrade django-helpdesk``) then migrate the database::

    python manage.py migrate helpdesk --db-dry-run # DB untouched
    python manage.py migrate helpdesk

Lastly, restart your web server software (eg Apache) or FastCGI instance, to
ensure the latest changes are in use.

Unfortunately we are unable to assist if you are upgrading from a
version of django-helpdesk prior to migrations (ie pre-2011).

You can continue to the 'Initial Configuration' area, if needed.

Notes on database backends
--------------------------

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

You may be able to convert an existing MySQL database to use UTF-8 collation
by using the following SQL commands::

    ALTER DATABASE mydatabase CHARACTER SET utf8 COLLATE utf8_general_ci;
    ALTER TABLE helpdesk_emailtemplate CONVERT TO CHARACTER SET utf8 COLLATE utf8_general_ci;

Both ``utf8_general_ci`` or ``utf16_general_ci`` have been reported to work.

If you do NOT do this step, and you only want to use English-language templates,
you may be able to continue however you will receive a warning when running the
'migrate' commands.
