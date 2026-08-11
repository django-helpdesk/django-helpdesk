Custom Templates
================

django-helpdesk supports custom HTML templates that can be styled with CSS.

In particular, users can include a file named `helpdesk-customize.css` in their django project directory to provide CSS overrides easily.

In general, entire HTML and CSS templates may be overriden by including a file of the same name in the project directory. Django automatically searches the project directory before searching for default templates included with django-helpdesk.

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
    A public follow-up that came in from the submitter, either by e-mail or
    through the public ticket view.

Restyle these classes in ``helpdesk-customize.css`` to fit your own palette.
The colors are backed up by a text label in each follow-up header, so keep
that label if you override the template.
