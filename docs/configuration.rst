Configuration
=============

   **IMPORTANT NOTE**: Any tickets created via POP3 or IMAP mailboxes will DELETE the original e-mail from the mail server.

Before django-helpdesk will be much use, you need to do some basic configuration. Most of this is done via the Django admin screens.

1. Visit ``http://yoursite/admin/`` and add a Helpdesk Queue. If you wish, enter your POP3 or IMAP server details. 

2. Visit ``http://yoursite/helpdesk/`` (or whatever path as defined in your ``urls.py``) 

3. If you wish to automatically create tickets from the contents of an e-mail inbox, set up a cronjob to run the management command on a regular basis. 

   Don't forget to set the relevant Django environment variables in your crontab::

       */5 * * * * /path/to/helpdesksite/manage.py get_email

   This will run the e-mail import every 5 minutes

   You will need to create a support queue, and associated login/host values, in the Django admin interface, in order for mail to be picked-up from the mail server and placed in the tickets table of your database. The values in the settings file alone, will not create the necessary values to trigger the get_email function.

4. If you wish to automatically escalate tickets based on their age, set up a cronjob to run the escalation command on a regular basis::
   
       0 * * * * /path/to/helpdesksite/manage.py escalate_tickets
   
   This will run the escalation process hourly, using the 'Escalation Days' setting for each queue to determine which tickets to escalate.

5. If you wish to exclude some days (eg, weekends) from escalation calculations, enter the dates manually via the Admin, or setup a cronjob to run a management command on a regular basis::

       0 0 * * 0 /path/to/helpdesksite/manage.py create_escalation_exclusions --days saturday,sunday --escalate-verbosely

   This will, on a weekly basis, create exclusions for the coming weekend.

6. Log in to your Django admin screen, and go to the 'Sites' module. If the site ``example.com`` is listed, click it and update the details so they are relevant for your website.

7. If you do not send mail directly from your web server (eg, you need to use an SMTP server) then edit your ``settings.py`` file so it contains your mail server details::

       EMAIL_HOST = 'XXXXX'
       EMAIL_HOST_USER = 'YYYYYY@ZZZZ.PPP'
       EMAIL_HOST_PASSWORD = '123456'

8. If you wish to use SOCKS4/5 proxy with Helpdesk Queue email operations, install PySocks manually. Please note that mixing both SOCKS and non-SOCKS email sources for different queues is only supported under Python 2; on Python 3, SOCKS proxy support is all-or-nothing: either all queue email sources must use SOCKS or none may use it. If you need this functionality on Python 3 please `let us know <https://github.com/django-helpdesk/django-helpdesk/issues/new>`_.

You're now up and running! Happy ticketing.

Queue settings via admin interface
----------------------------------
E-Mail Check Interval
^^^^^^^^^^^^^^^^^^^^^
This setting does not trigger e-mail collection, it merely throttles it. In order to trigger e-mail collection you must run a crontab to trigger ``manage.py get_email``. The setting in *E-Mail Check Interval* prevents your crontab from running the e-mail trigger more often than the interval set.

For example, setting *E-Mail Check Interval* to ``5`` will limit the collection of e-mail to once every five minutes, even if your crontab is firing every five seconds. If your cron job is set to fire once every hour, then e-mail will only be collected once every hour.

The cron job triggers the collection of e-mail, *E-Mail Check Interval* restricts how often the trigger is effective.

To remove this limit, set *E-Mail Check Interval* to ``0``.
