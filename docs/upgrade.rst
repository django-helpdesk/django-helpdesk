Upgrading
=========

Your ``django-helpdesk`` installation can be upgraded to the latest version using the release notes below.


Prerequisites
-------------

Please consult the Installation instructions for general instructions and tips.
The tips below are based on modifications of the original installation instructions.


0.2 -> 0.3
----------

- Under `INSTALLED_APPS`, `bootstrapform` needs to be replaced with `bootstrap4form`

- Unless turning off `pinax_teams`, add the following to `INSTALLED_APPS` for `pinax_teams`:
  ```
  "account",
  "pinax.invitations",
  "pinax.teams",
  "reversion",
  ```
  
- If using `send_templated_mail`, then it now needs to be imported from `helpdesk.templated_email`


