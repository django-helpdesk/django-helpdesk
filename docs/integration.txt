Integrating django-helpdesk into your application
-------------------------------------------------

Django-helpdesk associates an email address with each submitted ticket. If you integrate django-helpdesk directly into your django application, logged in users will automatically have their email address set when they visit the `/tickets/submit/` form. If you wish to pre-fill fields in this form, you can do so simply by setting the following query parameters:

 - `queue`
 - `title`
 - `body`
 - `submitter_email`

Note that these fields will continue to be user-editable despite being pre-filled.
