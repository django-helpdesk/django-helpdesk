Installation
============

django-helpdesk installation isn't difficult, but it requires you have a bit of existing know-how about Django.


Getting The Code
----------------

Installing using PIP
~~~~~~~~~~~~~~~~~~~~

Try using ``pip install django-helpdesk``. Go and have a beer to celebrate Python packaging.

GIT Checkout (Cutting Edge)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you're planning on editing the code or just want to get whatever is the latest and greatest, you can clone the official Git repository with ``git clone git://github.com/rossp/django-helpdesk.git``

Copy the ``helpdesk`` folder into your ``PYTHONPATH``.

I just want a .tar.gz!
~~~~~~~~~~~~~~~~~~~~~~

You can download the latest PyPi package from http://pypi.python.org/pypi/django-helpdesk/

Download, extract, and drop ``helpdesk`` into your ``PYTHONPATH``

Adding To Your Django Project
-----------------------------

1. Edit your ``settings.py`` file and add ``helpdesk`` to the ``INSTALLED_APPS`` setting. You also need ``django.contrib.admin`` and ``django.contrib.markup`` in ``INSTALLED_APPS`` if you haven't already added it. eg::
    
    INSTALLED_APPS = (
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.sites',
        'django.contrib.admin', # Required for helpdesk admin/maintenance
        'django.contrib.markup', # Required for helpdesk text display
        'south', # Highly recommended to make database migrations simpler.
        'helpdesk', # This is new!
    )

2. Make sure django-helpdesk is accessible via ``urls.py``. Add the following line to ``urls.py``::

     (r'helpdesk/', include('helpdesk.urls')),

   Note that you can change 'helpdesk/' to anything you like, such as 'support/' or 'help/'. If you want django-helpdesk to be available at the root of your site (for example at http://support.mysite.tld/) then the line will be as follows::
     
     (r'', include('helpdesk.urls')),

   This line will have to come *after* any other lines in your urls.py such as those used by the Django admin.

3. Create the required database tables. I'd suggest using *South*, however the following will work::

     ./manage.py syncdb

   Then migrate using South

     ./manage.py migrate helpdesk

4. Include your static files in your public web path::

      python manage.py collectstatic

5. Inside your ``MEDIA_ROOT`` folder, inside the ``helpdesk`` folder, is a folder called ``attachments``. Ensure your web server software can write to this folder - something like this should do the trick::

      chown www-data:www-data attachments/
      chmod 700 attachments

   (substitute www-data for the user / group that your web server runs as, eg 'apache' or 'httpd')

   If all else fails ensure all users can write to it::

      chmod 777 attachments/

   This is NOT recommended, especially if you're on a shared server.

6. Ensure that your ``attachments`` folder has directory listings turned off, to ensure users don't download files that they are not specifically linked to from their tickets.

   If you are using Apache, put a ``.htaccess`` file in the ``attachments`` folder with the following content::

      Options -Indexes

   You will also have to make sure that ``.htaccess`` files aren't being ignored.

   Ideally, accessing http://MEDIA_URL/helpdesk/attachments/ will give you a 403 access denied error.

7. If it's not already installed, install ``python-markdown``::

      pip install Markdown

8. If you already have a view handling your logins, then great! If not, add the following to ``settings.py`` to get your Django installation to use the login view included in ``django-helpdesk``::

      LOGIN_URL = '/helpdesk/login/'

   Alter the URL to suit your installation path.
