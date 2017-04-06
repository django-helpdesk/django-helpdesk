django-helpdesk Demo Project
============================

This folder contains a demo Django project that
illustrates a simple django-helpdesk installation
with common settings.

This project is *NOT* production ready, but can be
used as a template to get started.

In particular, this should be useful for testing
purposes and for those that want to contribute
to development of django-helpdesk. For more information
on contributing, see the CONTRIBUTING.rst file
in the top level of the django-helpdesk directory.

Running the demo
----------------

By default, the demo is configured for Python 3.

While not recommended, the simplest way to get
started is to simply install django-helpdesk
to your system python package directory.
Ideally, you'd use a virtualenv instead
(see below for details).

To use your system directory, from the top-level
django-helpdesk directory, simply run:

    sudo make rundemo

Once the console gives a prompt that the HTTP
server is listening, open your web browser
and navigate to:

    localhost:8080

You should see the django-helpdesk public web portal!

If you shut down the server, you can't immediately
re-run the demo because the make commands would
encounter problems trying to re-write the database.
Instead, before running the demo, you will need
to first clean the demo:

    sudo make distclean

You may need to use sudo with other make targets too.

*NOTE ON USING VIRTUALENV*

Rather than using the system python, you probably
want to use a virtualenv.

If so, you might change the pip in the makefile
to point to your virtualenv's pip instead
before running:

    make rundemo

*NOTE ON USING PYTHON 2*

By default, the demo uses Python 3, as Python 3
will be the recommended version of python for
django-helpdesk and even Django itself in the near future.
However, if you wish to use Python 2, you can
instead run the following:

    sudo make rundemo2

Then navigate to the site in a browser as above.

*NOTE ON DJANGO VERISON*

The demo project was also created with Django 1.10
in mind. If you are using a different version of Django,
slight tweaks might be necessary to make the demo work.

*NOTE ON ATTACHMENTS*

The folder:

    demo/demodesk/media/helpdesk/attachments

comes pre-populated with a couple of attachments,
to demo how django-helpdesk deals with attachments.
You can look in this folder to see the raw data.
You can also create a different folder for this
and update settings.py, but note that this will
break the demo as some attachments may not be available
unless you migrate the existing data to the
new location.

The demodesk project
--------------------

"demodesk" is the name of our demo Django project.

You probably will want to look at demo/demodesk/config/settings.py
and read the comments, which walk you through a basic
installation with common configuration options.

The top-level Makefile also gives a list of commands so you
can see how to get the project running. Of course,
when you plan to deploy this project, it is recommended
to use a "real" HTTP server like apache or nginx,
and so further configuration will be necessary.

More information can be found in the top-level docs/ folder.
