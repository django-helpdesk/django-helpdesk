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

If you are interested in specific features that are in the development stage and are willing to test the feature prior to release, please register your willingness against the issue and you will be notified when it reaches testing phase.
You can see a list of possible enhancements here:
https://github.com/django-helpdesk/django-helpdesk/labels/enhancement

This is an easy way to get involved that doesn't require programming.


Pull Requests
-------------

Please fork the project on GitHub, make your changes, and submit a
pull request against the `main` branch of the `django-helpdesk` repository.

The `main` branch always contains the bleeding edge code that has been reviewed and tested.
all features are developed entirely in a separate branch and are only merged to `main` once all tests and maintainer reviews
have been passed.

If for some reason you are forced to stay on an older version and need a patch that may apply to others with the same road
block preventing upgrading to the latest release,
then you can check out that versions code using the version tag and push your patch to a branch that we can then tag with a
patch release - it will not be merged to the `main` branch. 

We reserve the right to decline a pull request raised against the `main` branch if it does not contain adequate unit tests.

Ideally a PR should be as small as possible to avoid complex and time consuming code reviews.
Break up complex new features or code refactoring into manageable chunks and raise sequential PR's.
If there are small bugs encountered whilst developing a new feature and they do not have a significant code impact then
they can be included in the feature PR.
Otherwise each bugfix, feature, code refactoring or functionality change should be in its own PR.

Please provide clear commit messages per file explaining *what*, precisely, has been changed in that file - it aids in
researching behaviour issues down the line.

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

There is a CI/CD pipeline implemented using Github actions that covers code formatting, code security and unit tests.
All PR's are required to pass the full test coverage suite and a code review by one or more of the maintainers before
it can be merged to the main branch.
Currently, test coverage is very low but all new pull requests are required to have appropriate unit tests
to cover any new or changed functionality which will increase the coverage over time.


As a general policy, we will only accept new feature commits if they are
accompanied by appropriate unit/functional tests (that is, tests for the
functionality you just added). Bugfixes should also include new unit tests to
ensure the bug has been fixed and there is no later regression due to other changes.

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
