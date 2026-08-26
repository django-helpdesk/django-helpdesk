Upgrading
=========

Your ``django-helpdesk`` installation can be upgraded to the latest version using the release notes below.

Prerequisites
-------------

Please consult the Installation instructions for general instructions and tips.
The tips below are based on modifications of the original installation instructions.


Form rendering no longer needs django-bootstrap4-form
-----------------------------------------------------

``django-bootstrap4-form`` has been removed. It emitted Bootstrap 3 markup
(``form-group``, ``control-label``, ``has-error``, ``<div class="checkbox">``),
none of which exists in the Bootstrap 5 stylesheet this project ships, so the
affected fields had lost their spacing and their checkboxes and radios were
unstyled. Forms are now rendered by a template inside django-helpdesk itself.

Remove ``'bootstrap4form'`` from your ``INSTALLED_APPS``. Nothing else is
required, and the package can be uninstalled unless something else in your
project uses it.

If you have overridden ``user_settings.html``, ``edit_ticket.html`` or
``public_create_ticket_base.html``, replace ``{{ form|bootstrap4form }}`` with::

    {% load bootstrap5_form %}
    {% bootstrap5_form form %}


Optional integrations are no longer installed by default
--------------------------------------------------------

Two packages used to be installed with every copy of django-helpdesk even though
the project itself never imports them, and neither is needed for a default
install. They are now optional extras:

.. csv-table::
   :header: "Feature", "Install with", "Needed if you"
   :align: left
   :widths: auto

   "Celery mail polling", ``pip install django-helpdesk[celery]``, "schedule ``helpdesk.tasks`` instead of running
   ``get_email`` from cron"
   "Akismet spam check", ``pip install django-helpdesk[spam]``, "set ``AKISMET_API_KEY`` or ``TYPEPAD_ANTISPAM_API_KEY``"

If you would rather not work out which apply to you, ``pip install
django-helpdesk[all]`` restores exactly what earlier releases pulled in.

The Celery extra also brings ``django-celery-beat``, which that setup has always
required but which was never declared.

Neither of these breaks a running site on its own. ``helpdesk/urls.py`` already
imports ``helpdesk.tasks`` inside a ``try/except ImportError``, and
``text_is_spam()`` already treated a missing Akismet package as "not spam", so
an upgrade without the extras means the scheduled task is not registered and
submissions stop being spam checked, rather than anything raising.

``django-cleanup`` is deliberately not on this list. It activates as soon as it
is listed in ``INSTALLED_APPS``, which is what our own installation
instructions suggest, so making it optional would stop a documented
configuration from starting at all. It stays a hard dependency.


0.2 -> 0.3
----------

- Under ``INSTALLED_APPS``, ``bootstrapform`` needs to be replaced with ``bootstrap4form``

- Unless turning off ``pinax_teams``, add the following to ``INSTALLED_APPS`` for ``pinax_teams``::

    "account",
    "pinax.invitations",
    "pinax.teams",
    "reversion",


- If using ``send_templated_mail``, then it now needs to be imported from ``helpdesk.templated_email``
