Integrating django-helpdesk into your application
-------------------------------------------------

Django-helpdesk associates an email address with each submitted ticket. If you integrate django-helpdesk directly into your django application, logged in users will automatically have their email address set when they visit the `/tickets/submit/` form. If you wish to pre-fill fields in this form, you can do so simply by setting the following query parameters:

 - `queue`
 - `title`
 - `body`
 - `submitter_email`
 - `custom_<custom-field-slug>`

There is also a page under the url `/tickets/submit_iframe/` with the same behavior.

Fields may be hidden by adding them to a comma separated `_hide_fieds_` query parameter.

Here is an example url to get you started: `http://localhost:8000/desk/tickets/submit_iframe/?queue=1&custom_dpnk-user=http://lol.cz;submitter_email=foo@bar.cz&title=lol&_hide_fields_=title,queue,submitter_email`. This url sets the queue to 1, sets the custom field `dpnk-url` to `http://lol.cz` and submitter_email to `lol@baz.cz` and hides the title, queue, and submitter_email fields. Note that hidden fields should be set to a default.

Note that these fields will continue to be user-editable despite being pre-filled.
