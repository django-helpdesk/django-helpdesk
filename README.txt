django-helpdesk - A Django powered ticket tracker for small enterprise.
=======================================================================

(c) Copyright 2009-11 Jutda. All Rights Reserved. See LICENSE for details.

django-helpdesk was formerly known as Jutda Helpdesk, named after the 
company who originally created it. As of January 2011 the name has been 
changed to reflect what it really is: a Django-powered ticket tracker with
contributors reaching far beyond Jutda.

Complete documentation is available in the docs/ directory, or online at http://django-helpdesk.readthedocs.org/.

#########################
0. Table of Contents
#########################

1. Licensing
2. Dependencies (pre-flight checklist)
3. Upgrading from previous versions
4. Installation

1. Licensing
------------

See the file 'LICENSE' for licensing terms. Note that django-helpdesk is 
distributed with 3rd party products which have their own licenses. See 
LICENSE.3RDPARTY for license terms for included packages.

2. Dependencies (pre-flight checklist)
--------------------------------------

1. Python 2.4+ 
2. Django (1.2 or newer)
3. An existing WORKING Django project with database etc. If you
   cannot log into the Admin, you won't get this product working.

**NOTE REGARDING SQLITE AND SEARCHING:**
If you use sqlite as your database, the search function will not work as
effectively as it will with other databases due to its inability to do
case-insensitive searches. It's recommended that you use PostgreSQL or MySQL
if possible. For more information, see this note in the Django documentation:
http://docs.djangoproject.com/en/dev/ref/databases/#sqlite-string-matching

When you try to do a keyword search using sqlite, a message will be displayed
to alert you to this shortcoming. There is no way around it, sorry.

3. Upgrading from previous versions
-----------------------------------

If you are upgrading from a previous version of django-helpdesk, you should 
read the UPGRADING file to learn what changes you will need to make to get 
the current version of django-helpdesk working.

1. Find out your current version of django-helpdesk. In the 'helpdesk' folder,
   use the 'svn' command to find the current revision::

      svn info .

   Look for the 'Revision' line, eg::

      Revision: 92

2. Read through the UPGRADE file, looking for any changse made _after_ that 
   revision. Apply the commands provided in order from oldest to most recent.

3. Restart your web server software (eg Apache) or FastCGI instance, to ensure
   the latest changes are in use.

4. Continue to the 'Initial Configuration' area, if needed.

4. Installation
---------------

``pip install django-helpdesk``

For further installation information see docs/install.html and docs/configuration.html

