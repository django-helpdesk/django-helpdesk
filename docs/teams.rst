Working with teams and larger organizations
===========================================

If you only have one or two people working on tickets, basic Queue setup is enough to get you going. You can now assign tickets to teams for better ticket filtering, reducing noise and improving organization efficiency.

Rather than assigning tickets to teams directly, django-helpdesk allows you assign tickets to knowledge-base items and then assign knowledge base items to teams.

Knowledge-base items can be in either public or private knowledge-base categories, so this organizational structure need not have any influence on the external appearance of your public helpdesk web portal.

You can visit the 'Pinax Teams' page in your django admin in order to create a team and add team members.

You can assign a knowledge-base item to a team on the Helpdesk admin page.

Once you have set up teams. Unassigned tickets which are associated with a knowledge-base item will only be shown on the dashboard to those users who are members of the team which is associated with that knowledge-base item.

Note: It is possible that pinax-teams will interfere with other packages that you already use in your project. If you do not wish to use team functionality, you can dissable teams by setting the following settings: ``HELPDESK_TEAMS_MODEL`` to any random model, ``HELPDESK_TEAMS_MIGRATION_DEPENDENCIES`` to ``[]``, and ``HELPDESK_KBITEM_TEAM_GETTER`` to ``lambda _: None``. You can also use a different library in place of pinax teams by setting those settings appropriately. ``HELPDESK_KBITEM_TEAM_GETTER`` should take a ``kbitem`` and return a team object with a ``name`` property and a method ``is_member(self, user)`` which returns true if user is a member of the team.
