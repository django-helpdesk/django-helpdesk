Contributing
============

django-helpdesk is an open-source project and as such contributions from the community are welcomed and encouraged.

Licensing
---------

All contributions to django-helpdesk must be under the BSD license documented in our :doc:`license` page. All code submitted (in any way: via e-mail, via GitHub forks, attachments, etc) are assumed to be open-source and licensed under the BSD license.

If you or your organisation does not accept these license terms then we cannot accept your contribution. Please reconsider!

Translations
------------

Although django-helpdesk has originally been written for the English language, there are already multiple translations to Spanish, Polish, and German and more translations are welcomed.

Translations are handled using the excellent Transifex service which is much easier for most users than manually editing .po files. It also allows collaborative translation. If you want to help translate django-helpdesk into languages other than English, we encourage you to make use of our Transifex project:

http://www.transifex.net/projects/p/django-helpdesk/resource/core/

Code changes
------------

Please fork the project on GitHub, make your changes, and log a pull request to get the changes pulled back into my repository.

Wherever possible please break git commits up into small chunks that are specific to a single bit of functionality. For example, a commit should not contain both new functionality *and* a bugfix; the new function and the bugfix should be separate commits wherever possible.

Commit messages should also explain *what*, precisely, has been changed.

If you have any questions, please contact the project co-ordinator, Ross Poulton, at ross@rossp.org.

Database schema changes
-----------------------

As well as making your normal code changes to ``models.py``, please generate a South migration file and commit it with your code. You will want to use a command similar to the following::

    ./manage.py migrate helpdesk --auto [migration_name]

Make sure that ``migration_name`` is a sensible single-string explanation of what this migration does, such as *add_priority_options* or *add_basket_table*

This will add a file to the ``migrations/`` folder, which must be committed to git with your other code changes.
