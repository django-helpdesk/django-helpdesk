.. _teams:

Working with teams and larger organizations
===========================================

Helpdesk supports team based assignment of tickets. By default, the teams functionality is enabled and the default implementation uses the Pinax teams app.

If you only have one or two people working on tickets, basic Queue setup is enough to get you going. You can now assign tickets to teams for better ticket filtering, reducing noise and improving organization efficiency.

If you are embedding the helpdesk app into your own apps, it is possible that the pinax-teams  app used to support the default team based functionality will interfere with other packages that you already use in your project and you will need to disable it.


How It Works
------------

Rather than assigning tickets to teams directly, django-helpdesk allows you assign tickets to knowledge-base items and then assign knowledge base items to teams.

Knowledge-base items can be in either public or private knowledge-base categories, so this organizational structure need not have any influence on the external appearance of your public helpdesk web portal.

If using the default teams implementation, you can visit the 'Pinax Teams' page in your django admin in order to create a team and add team members.

You can assign a knowledge-base item to a team on the Helpdesk admin page.

Once you have set up teams. Unassigned tickets which are associated with a knowledge-base item will only be shown on the dashboard to those users who are members of the team which is associated with that knowledge-base item.


Implementing Custom Teams Functionality
---------------------------------------

If you want to use a different team app or implement your own team based app, you can hook it into Helpdesk using the following 3 settings:

``HELPDESK_TEAMS_MODEL``: point this to the model that defines a team in your custom implementation
``HELPDESK_TEAMS_MIGRATION_DEPENDENCIES``: set this to an array of migration(s) that are required to have run that will ensure the link that will be added as defined in the HELPDESK_TEAMS_MODEL will be available as a model to Helpdesk
``HELPDESK_KBITEM_TEAM_GETTER``: the method that will be called that must return a list of users who belong to a given team


Configuring Teams Functionality
-------------------------------

Teams functionality is enabled by default but can be disabled using this entry in your ``settings.py``::

    HELPDESK_TEAMS_MODE_ENABLED=False 

If you do not disable teams functionality then you must add additional apps into the ``INSTALLED_APPS`` in your ``settings.py``.
The following can be pasted into your settings.py BELOW the ``INSTALLED_APPS`` definition::

    INSTALLED_APPS.extend([
        'account',  # Required by pinax-teams
        'pinax.invitations',  # required by pinax-teams
        'pinax.teams',  # team support
        'reversion',  # required by pinax-teams
    ])

Alternatively just add the 4 apps listed above into the ``INSTALLED_APPS``.


Disabling Teams Functionality
-----------------------------

Teams functionality is enabled by default but can be disabled using this entry in your ``settings.py``::

    HELPDESK_TEAMS_MODE_ENABLED=False 
