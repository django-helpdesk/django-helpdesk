Custom Templates
================

django-helpdesk supports custom HTML templates that can be styled with CSS.

In particular, users can include a file named ``helpdesk-customize.css`` in their django project directory to provide CSS overrides easily.

In general, entire HTML and CSS templates may be overridden by including a file of the same name in the project directory. Django automatically searches the project directory before searching for default templates included with django-helpdesk.

Additional ticket panels
------------------------

The staff ticket template provides an empty ``helpdesk_ticket_panels`` block
immediately after the ticket description table and before the response controls.
Use it to add a project-specific panel without copying the full ticket template.
The default block is empty and does not change the ticket view's behavior.

Create ``helpdesk/ticket.html`` in your project's template directory, configured
in ``TEMPLATES[0]['DIRS']``::

    {% extends "helpdesk/ticket.html" %}

    {% block helpdesk_ticket_panels %}
      {{ block.super }}
      <section aria-label="Internal reference">
        <p>Reference for ticket #{{ ticket.id }}</p>
      </section>
    {% endblock %}

An installed app can also provide this override when it precedes ``helpdesk``
in ``INSTALLED_APPS`` and the app-directory template loader is enabled. See
`Django's template override documentation
<https://docs.djangoproject.com/en/stable/howto/overriding-templates/>`_.

Any endpoint called by the panel must enforce its own authentication, ticket
permissions and CSRF protection.

Follow-up colors
-----------------

On the staff ticket view each follow-up is color coded by who can see it and
which way it traveled, so an internal note is distinguishable at a glance from
a reply that went out to the submitter. Every follow-up carries a
``followup-item`` class plus one of:

``followup-item-internal``
    A private follow-up: an internal note only staff can see.

``followup-item-outbound``
    A public follow-up written by staff, so the submitter can read it.

``followup-item-inbound``
    A public follow-up that came in from the submitter by e-mail. Submissions
    made through the public ticket view are not currently attributed to the
    submitter, so they are classed as ``followup-item-outbound`` instead.

Restyle these classes in ``helpdesk-customize.css`` to fit your own palette.
The colors are backed up by a text label in each follow-up header, so keep
that label if you override the template.
