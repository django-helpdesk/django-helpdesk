Spam Filtering
==============

django-helpdesk includes a copy of ``akismet.py`` by `Michael Foord <http://www.voidspace.org.uk/>`_, which lets incoming ticket submissions be automatically checked against either the `Akismet <http://akismet.com/>`_ or `TypePad Anti-Spam <http://antispam.typepad.com/>`_ services.

To enable this functionality, sign up for an API key with one of these two services.

Akismet
~~~~~~~

* Sign up at http://akismet.com/
* Save your API key in ``settings.py`` as ``AKISMET_API_KEY``

**Note**: Akismet is only free for personal use. Paid commercial accounts are available.

TypePad AntiSpam
~~~~~~~~~~~~~~~~
* Sign up at http://antispam.typepad.com/
* Save your API key in ``settings.py`` as ``TYPEPAD_ANTISPAM_API_KEY``

This service is free to use, within their terms and conditions.

If you have either of these settings enabled, the spam filtering will be done automatically. If you have *both* settings configured, TypePad will be used instead of Akismet.


Example
~~~~~~~

A sample configuration in ``settings.py`` may be::

   TYPEPAD_ANTISPAM_API_KEY = 'abc123'

