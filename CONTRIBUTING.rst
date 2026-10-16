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

AI policy
---------

Like any tool, generative AI should be used with critical thinking and good judgement. Here are our expectations for everyone wanting to contribute to django-helpdesk.

.. caution::

   **TL;DR:**

   - We take the responsibility for this project very seriously and we expect you to take your responsibility for your contributions seriously, too.
     This used to be a given, but it changed now that a pull request is just one prompt away.

   - Every contribution has to be backed by a human who unequivocally owns the copyright for all changes.
     No LLM bots in ``Co-authored-by:`` trailers.

   - Pull requests with no human in the loop lead to a permanent ban.

   - Absolutely **no** unsupervised agentic tools.

   - Do **not** trigger bots like Copilot on this repository.
     GitHub won't let us block Copilot, but it's a great way to tell you didn't read this.


By submitting a pull request, you certify that:

- You are the author of the contribution or have the legal right to submit it.

- You either hold the copyright to the changes or have explicit legal authorization to contribute them under this project's license.

- You understand the code.

- You accept full responsibility for it.


- Review and test all AI-generated code. You are expected to understand the code, and take final accountability for it.
- Include a disclosure if you use generative AI for your code contribution.
- Always write pull request descriptions manually

In addition, we recommend to:

- Avoid all AI use in messages (GitHub issues, discussions, proposal) with other contributors, participants, mentors. Use your own words, share your own ideas.
- Avoid sharing research from AI tools as-is. AI use for research is ok. Be critical of its results and share only the information you can confirm to be correct.

When this policy isn’t followed, we may resort to a ban from the project or close your contribution without feedback.

Summary
-------

In practice, this means:

- Pull requests that have an LLM product listed as co-author can't be merged and will be closed without further discussion.
  We cannot risk the copyright status of this project.

  If you used LLM tools during development, you may still submit – but you must remove any LLM co-author tags and take full ownership of every line.

- By submitting a pull request, **you** take full **technical and legal** responsibility for the contents of the pull request and promise that **you** hold the copyright for the changes submitted.

  "An LLM wrote it" is **not** an acceptable response to questions or critique.
  **If you cannot explain and defend the changes you submit, do not submit them** and open a high-quality bug report/feature request instead.

- Accounts that exercise bot-like behavior – like automated mass pull requests – will be permanently banned, whether they belong to a human or not.

- Do **not** post LLM-generated review comments – we can prompt LLMs ourselves should we desire their wisdom.
  Do **not** post summaries unless you've fact-checked them and take responsibility for 100% of their content.
  Remember that *all* LLM output *looks* **plausible**.
  When using these tools, it's **your** responsibility to ensure that it's also **correct** and has a reasonable signal-to-noise ratio.

  Inspired from `python-attrs AI policy <https://github.com/python-attrs/attrs/blob/main/.github/AI_POLICY.md>`_


Legal
-----

There is ongoing legal uncertainty regarding the copyright status of LLM-generated works and their provenance.
Since we do not have a formal `Contributor License Agreement <https://en.wikipedia.org/wiki/Contributor_license_agreement>`_ (CLA), you retain your copyright to your changes to this project.

Therefore, allowing contributions by LLMs has unpredictable consequences for the copyright status of this project – even when leaving aside possible copyright violations due to plagiarism.


Human
-----

As the makers of software and desire for high-quality maintenance, we take our responsibility to our users very seriously.
We have to manually review every change before merging, because it's **our responsibility** to keep the project stable.

Please understand that by opening low-quality pull requests you're not helping anyone.
Worse, you're `poisoning the open source ecosystem <https://lwn.net/Articles/1058266/>`_ that was precarious even before the arrival of LLM tools.
Having to wade through plausible-looking-but-low-quality pull requests and trying to determine which ones are legit is extremely demoralizing and has already burned out many good maintainers.

Unfortunately, our volunteer maintainers are becoming overwhelmed by pull requests that misinterpret or poorly solve the presented problem. Additionally, if we wanted to make a pull request on an issue via LLM without a human in the loop we could do that more quickly ourselves since it would not require back and forth. Therefore we will not be accepting pull requests in this form.

This dynamic is especially pernicious because it poisons the well for mentoring new contributors which we are committed to.


AI-assisted Contributions
-------------------------

Here are acceptable uses of AI for code and documentation contributions:

- Generate test cases or demo implementations as part of testing a feature or a bug.
- Improve writing for documentation (grammar, style guide).
- Research a problem and explore possible solutions.
- Assistance with writing code that you fully understand and own.

Here are unacceptable uses:

- Unacceptable: create a contribution from an existing issue with no further direction.
- Unacceptable: triage issues such as reproducing bugs or discussing features based on the input of AI alone.

  Inspired from `wagtail's contribution guidelines <https://github.com/wagtail/wagtail/blob/main/.github/CONTRIBUTING.md#generative-ai>`_


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
