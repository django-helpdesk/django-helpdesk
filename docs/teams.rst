Working with teams and larger organizations
===========================================

If you only have one or two people working on tickets, basic Queue setup is enough to get you going. You can now assign tickets to teams for better ticket filtering, reducing noise and improving organization efficiency.

Rather than assigning tickets to teams directly, django-helpdesk allows you assign tickets to knowledge-base items and then assign knowledge base items to teams.

Knowledge-base items can be in either public or private knowledge-base categories, so this organizational structure need not have any influence on the external appearance of your public helpdesk web portal.

You can visit the 'Pinax Teams' page in your django admin in order to create a team and add team members.

You can assign a knowledge-base item to a team on the Helpdesk admin page.

Once you have set up teams. Unassigned tickets which are associated with a knowledge-base item will only be shown on the dashboard to those users who are members of the team which is associated with that knowledge-base item.
