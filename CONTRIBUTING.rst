Contributing
============

We're really glad you're reading this and considering contributing to
`django-helpdesk`! As an open source project, we rely on volunteers
to improve and grow the project. Welcome!

`django-helpdesk` is an open-source project and as such contributions from the
community are welcomed and encouraged!

Please read these guidelines to get up to speed quickly. If you have any
questions, please file an issue ticket on GitHub. Our main project
repository is available at:

https://github.com/django-helpdesk/django-helpdesk


Testing
-------

If you don't mind testing pre-releases (don't use in production!), we appreciate
continuous feedback on the `master` branch, which is our work toward the next
major release. Please file bug reports, and tag the report with the "pre-release"
tag.

This is an easy way to get involved that doesn't require programming.


Pull Requests
-------------

Please fork the project on GitHub, make your changes, and submit a
pull request back into the appropriate branch of the
`django-helpdesk` repository.

Short story:

* pull requests for `master` are for the next major release
* pull requests for a current release should go to appropriate release branch
  (for example, bugfixes for 0.2 should go to the `0.2.x` branch.)

Longer story:

In general, our git branching scheme looks like the following.

* `master` always points to development for the next major release,
  major new features should go here
* current and past major releases are found in their own branches:

  * `0.2.x` is the branch for the 0.2 release and any bugfix releases
  * `0.1` is the branch for the legacy code; it is no longer supported

We reserve the right to decline a pull request if it is not for
the appropriate branch.

Wherever possible please break git commits up into small chunks that are
specific to a single bit of functionality. For example, a commit should *not*
contain both new functionality *and* a bugfix; the new function and the bugfix
should be separate commits wherever possible.

Commit messages should also explain *what*, precisely, has been changed.

All commits should include appropriate new or updated tests; see the Tests
section below for more details.

If your changes affect the Django models for `django-helpdesk`, be aware
that your commits should include database schema python scripts; see the
Database Schema Changes section below for more details.


Coding Conventions
------------------

Be sure all Python code follows PEP8 conventions.

Ideally, add comments and documentation whenever you touch code.

HTML and Javascript templates should be appropriately indented.


Database schema changes
-----------------------

As well as making your normal code changes to ``models.py``, please generate a
Django migration file and commit it with your code. You will want to use a
command similar to the following::

    ./manage.py migrate helpdesk --auto [migration_name]

Make sure that ``migration_name`` is a sensible single-string explanation of
what this migration does, such as *add_priority_options* or *add_basket_table*.

This will add a file to the ``migrations/`` folder, which must be committed to
git with your other code changes.


Tests
-----

Currently, test coverage is very low. We're working on increasing this, and to
make life easier we are using Travis CI (http://travis-ci.org/) for continuous
integration. This means that the test suite is run every time a code change is
made, so we can try and make sure we avoid basic bugs and other regressions.

As a general policy, we will only accept new feature commits if they are
accompanied by appropriate unit/functional tests (that is, tests for the
functionality you just added). Bugfixes should also include new unit tests to
ensure the bug has been fixed.

More significant code refactoring must also include proper integration or
validation tests, to be committed *BEFORE* the refactoring patches. This is to
ensure that the refactored code produces the same results as the previous code
base.

Any further integration or validation tests (tests for the entire
django-helpdesk application) are not required but greatly appreciated until we
can improve our overall test coverage.

Please include tests in the ``tests/`` folder when committing code changes.

If you have any questions about creating or maintaining proper tests, please
start a discussion on the GitHub issue tracker at

https://github.com/django-helpdesk/django-helpdesk/issues


Ways to Contribute
------------------

We're happy to include any type of contribution! This can be:

* back-end python/django code development
* front-end web development (HTML/Javascript, especially jQuery)
* language translations
* writing improved documentation and demos

More details on each of theses tasks is below.

If you have any questions on contributing, please start a discussion on
the GitHub issue tracker at

https://github.com/django-helpdesk/django-helpdesk/issues


Translations
------------

Although `django-helpdesk` has originally been written for the English language,
there are already multiple community translations, including Spanish, Polish,
German, and Russian. More translations are welcomed!

Translations are handled using the excellent Transifex service which is much
easier for most users than manually editing .po files. It also allows
collaborative translation. If you want to help translate django-helpdesk into
languages other than English, we encourage you to make use of our Transifex
project:

http://www.transifex.com/projects/p/django-helpdesk/resource/core/

Once you have translated content via Transifex, please raise an issue on the
project Github page and tag it as "translations" to let us know it's ready to
import.


Licensing
---------

All contributions to django-helpdesk *must* be under the BSD license documented
in the LICENSE file in the top-level directory of this project.

By submitting a contribution to this project (in any way: via e-mail,
via GitHub pull requests, ticket attachments, etc), you acknowledge that your
contribution is open-source and licensed under the BSD license.

If you or your organization does not accept these license terms then we cannot
accept your contribution. Please reconsider!
