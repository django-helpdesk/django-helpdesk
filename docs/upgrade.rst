Upgrading
=========

Your ``django-helpdesk`` installation can be upgraded to the latest version using the release notes below.

Prerequisites
-------------

Please consult the Installation instructions for general instructions and tips.
The tips below are based on modifications of the original installation instructions.


Optional integrations are no longer installed by default
--------------------------------------------------------

Three packages used to be installed with every copy of django-helpdesk even
though the project itself never imports them, and none of them are needed for a
default install. They are now optional extras:

===================  ========================================  ==================================
Feature              Install with                              Needed if you
===================  ========================================  ==================================
Celery mail polling  ``pip install django-helpdesk[celery]``   schedule ``helpdesk.tasks``
                                                               instead of running ``get_email``
                                                               from cron
Akismet spam check   ``pip install django-helpdesk[spam]``     set ``AKISMET_API_KEY`` or
                                                               ``TYPEPAD_ANTISPAM_API_KEY``
File cleanup         ``pip install django-helpdesk[cleanup]``  list
                                                               ``django_cleanup.apps.CleanupConfig``
                                                               in ``INSTALLED_APPS``
===================  ========================================  ==================================

If you would rather not work out which apply to you, ``pip install
django-helpdesk[all]`` restores exactly what earlier releases pulled in.

The Celery extra also brings ``django-celery-beat``, which that setup has always
required but which was never declared.

Nothing breaks silently except the Akismet case: ``text_is_spam()`` already
treated a missing Akismet package as "not spam", so an upgrade without the extra
means submissions stop being checked rather than raising an error. The other two
fail loudly, at import or at startup.


0.2 -> 0.3
----------

- Under `INSTALLED_APPS`, `bootstrapform` needs to be replaced with `bootstrap4form`

- Unless turning off `pinax_teams`, add the following to `INSTALLED_APPS` for `pinax_teams`::

    "account",
    "pinax.invitations",
    "pinax.teams",
    "reversion",

  
- If using `send_templated_mail`, then it now needs to be imported from `helpdesk.templated_email`
