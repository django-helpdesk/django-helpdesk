# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone
from django.conf import settings
import helpdesk.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Attachment',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('file', models.FileField(upload_to=helpdesk.models.attachment_path, max_length=1000, verbose_name='File')),
                ('filename', models.CharField(max_length=1000, verbose_name='Filename')),
                ('mime_type', models.CharField(max_length=255, verbose_name='MIME Type')),
                ('size', models.IntegerField(help_text='Size of this file in bytes', verbose_name='Size')),
            ],
            options={
                'ordering': ['filename'],
                'verbose_name': 'Attachment',
                'verbose_name_plural': 'Attachments',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='CustomField',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.SlugField(help_text='As used in the database and behind the scenes. Must be unique and consist of only lowercase letters with no punctuation.', unique=True, verbose_name='Field Name')),
                ('label', models.CharField(help_text='The display label for this field', max_length=b'30', verbose_name='Label')),
                ('help_text', models.TextField(help_text='Shown to the user when editing the ticket', null=True, verbose_name='Help Text', blank=True)),
                ('data_type', models.CharField(help_text='Allows you to restrict the data entered into this field', max_length=100, verbose_name='Data Type', choices=[(b'varchar', 'Character (single line)'), (b'text', 'Text (multi-line)'), (b'integer', 'Integer'), (b'decimal', 'Decimal'), (b'list', 'List'), (b'boolean', 'Boolean (checkbox yes/no)'), (b'date', 'Date'), (b'time', 'Time'), (b'datetime', 'Date & Time'), (b'email', 'E-Mail Address'), (b'url', 'URL'), (b'ipaddress', 'IP Address'), (b'slug', 'Slug')])),
                ('max_length', models.IntegerField(null=True, verbose_name='Maximum Length (characters)', blank=True)),
                ('decimal_places', models.IntegerField(help_text='Only used for decimal fields', null=True, verbose_name='Decimal Places', blank=True)),
                ('empty_selection_list', models.BooleanField(default=False, help_text='Only for List: adds an empty first entry to the choices list, which enforces that the user makes an active choice.', verbose_name='Add empty first choice to List?')),
                ('list_values', models.TextField(help_text='For list fields only. Enter one option per line.', null=True, verbose_name='List Values', blank=True)),
                ('ordering', models.IntegerField(help_text='Lower numbers are displayed first; higher numbers are listed later', null=True, verbose_name='Ordering', blank=True)),
                ('required', models.BooleanField(default=False, help_text='Does the user have to enter a value for this field?', verbose_name='Required?')),
                ('staff_only', models.BooleanField(default=False, help_text='If this is ticked, then the public submission form will NOT show this field', verbose_name='Staff Only?')),
            ],
            options={
                'verbose_name': 'Custom field',
                'verbose_name_plural': 'Custom fields',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='EmailTemplate',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('template_name', models.CharField(max_length=100, verbose_name='Template Name')),
                ('subject', models.CharField(help_text='This will be prefixed with "[ticket.ticket] ticket.title". We recommend something simple such as "(Updated") or "(Closed)" - the same context is available as in plain_text, below.', max_length=100, verbose_name='Subject')),
                ('heading', models.CharField(help_text='In HTML e-mails, this will be the heading at the top of the email - the same context is available as in plain_text, below.', max_length=100, verbose_name='Heading')),
                ('plain_text', models.TextField(help_text='The context available to you includes {{ ticket }}, {{ queue }}, and depending on the time of the call: {{ resolution }} or {{ comment }}.', verbose_name='Plain Text')),
                ('html', models.TextField(help_text='The same context is available here as in plain_text, above.', verbose_name='HTML')),
                ('locale', models.CharField(help_text='Locale of this template.', max_length=10, null=True, verbose_name='Locale', blank=True)),
            ],
            options={
                'ordering': ['template_name', 'locale'],
                'verbose_name': 'e-mail template',
                'verbose_name_plural': 'e-mail templates',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='EscalationExclusion',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=100, verbose_name='Name')),
                ('date', models.DateField(help_text='Date on which escalation should not happen', verbose_name='Date')),
            ],
            options={
                'verbose_name': 'Escalation exclusion',
                'verbose_name_plural': 'Escalation exclusions',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='FollowUp',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Date')),
                ('title', models.CharField(max_length=200, null=True, verbose_name='Title', blank=True)),
                ('comment', models.TextField(null=True, verbose_name='Comment', blank=True)),
                ('public', models.BooleanField(default=False, help_text='Public tickets are viewable by the submitter and all staff, but non-public tickets can only be seen by staff.', verbose_name='Public')),
                ('new_status', models.IntegerField(blank=True, help_text='If the status was changed, what was it changed to?', null=True, verbose_name='New Status', choices=[(1, 'Open'), (2, 'Reopened'), (3, 'Resolved'), (4, 'Closed'), (5, 'Duplicate')])),
            ],
            options={
                'ordering': ['date'],
                'verbose_name': 'Follow-up',
                'verbose_name_plural': 'Follow-ups',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='IgnoreEmail',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=100, verbose_name='Name')),
                ('date', models.DateField(help_text='Date on which this e-mail address was added', verbose_name='Date', editable=False, blank=True)),
                ('email_address', models.CharField(help_text='Enter a full e-mail address, or portions with wildcards, eg *@domain.com or postmaster@*.', max_length=150, verbose_name='E-Mail Address')),
                ('keep_in_mailbox', models.BooleanField(default=False, help_text='Do you want to save emails from this address in the mailbox? If this is unticked, emails from this address will be deleted.', verbose_name='Save Emails in Mailbox?')),
            ],
            options={
                'verbose_name': 'Ignored e-mail address',
                'verbose_name_plural': 'Ignored e-mail addresses',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='KBCategory',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('title', models.CharField(max_length=100, verbose_name='Title')),
                ('slug', models.SlugField(verbose_name='Slug')),
                ('description', models.TextField(verbose_name='Description')),
            ],
            options={
                'ordering': ['title'],
                'verbose_name': 'Knowledge base category',
                'verbose_name_plural': 'Knowledge base categories',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='KBItem',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('title', models.CharField(max_length=100, verbose_name='Title')),
                ('question', models.TextField(verbose_name='Question')),
                ('answer', models.TextField(verbose_name='Answer')),
                ('votes', models.IntegerField(default=0, help_text='Total number of votes cast for this item', verbose_name='Votes')),
                ('recommendations', models.IntegerField(default=0, help_text='Number of votes for this item which were POSITIVE.', verbose_name='Positive Votes')),
                ('last_updated', models.DateTimeField(help_text='The date on which this question was most recently changed.', verbose_name='Last Updated', blank=True)),
                ('category', models.ForeignKey(verbose_name='Category', to='helpdesk.KBCategory')),
            ],
            options={
                'ordering': ['title'],
                'verbose_name': 'Knowledge base item',
                'verbose_name_plural': 'Knowledge base items',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='PreSetReply',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(help_text='Only used to assist users with selecting a reply - not shown to the user.', max_length=100, verbose_name='Name')),
                ('body', models.TextField(help_text='Context available: {{ ticket }} - ticket object (eg {{ ticket.title }}); {{ queue }} - The queue; and {{ user }} - the current user.', verbose_name='Body')),
            ],
            options={
                'ordering': ['name'],
                'verbose_name': 'Pre-set reply',
                'verbose_name_plural': 'Pre-set replies',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Queue',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('title', models.CharField(max_length=100, verbose_name='Title')),
                ('slug', models.SlugField(help_text="This slug is used when building ticket ID's. Once set, try not to change it or e-mailing may get messy.", verbose_name='Slug')),
                ('email_address', models.EmailField(help_text='All outgoing e-mails for this queue will use this e-mail address. If you use IMAP or POP3, this should be the e-mail address for that mailbox.', max_length=75, null=True, verbose_name='E-Mail Address', blank=True)),
                ('locale', models.CharField(help_text='Locale of this queue. All correspondence in this queue will be in this language.', max_length=10, null=True, verbose_name='Locale', blank=True)),
                ('allow_public_submission', models.BooleanField(default=False, help_text='Should this queue be listed on the public submission form?', verbose_name='Allow Public Submission?')),
                ('allow_email_submission', models.BooleanField(default=False, help_text='Do you want to poll the e-mail box below for new tickets?', verbose_name='Allow E-Mail Submission?')),
                ('escalate_days', models.IntegerField(help_text='For tickets which are not held, how often do you wish to increase their priority? Set to 0 for no escalation.', null=True, verbose_name='Escalation Days', blank=True)),
                ('new_ticket_cc', models.CharField(help_text='If an e-mail address is entered here, then it will receive notification of all new tickets created for this queue. Enter a comma between multiple e-mail addresses.', max_length=200, null=True, verbose_name='New Ticket CC Address', blank=True)),
                ('updated_ticket_cc', models.CharField(help_text='If an e-mail address is entered here, then it will receive notification of all activity (new tickets, closed tickets, updates, reassignments, etc) for this queue. Separate multiple addresses with a comma.', max_length=200, null=True, verbose_name='Updated Ticket CC Address', blank=True)),
                ('email_box_type', models.CharField(choices=[(b'pop3', 'POP 3'), (b'imap', 'IMAP')], max_length=5, blank=True, help_text='E-Mail server type for creating tickets automatically from a mailbox - both POP3 and IMAP are supported.', null=True, verbose_name='E-Mail Box Type')),
                ('email_box_host', models.CharField(help_text='Your e-mail server address - either the domain name or IP address. May be "localhost".', max_length=200, null=True, verbose_name='E-Mail Hostname', blank=True)),
                ('email_box_port', models.IntegerField(help_text='Port number to use for accessing e-mail. Default for POP3 is "110", and for IMAP is "143". This may differ on some servers. Leave it blank to use the defaults.', null=True, verbose_name='E-Mail Port', blank=True)),
                ('email_box_ssl', models.BooleanField(default=False, help_text='Whether to use SSL for IMAP or POP3 - the default ports when using SSL are 993 for IMAP and 995 for POP3.', verbose_name='Use SSL for E-Mail?')),
                ('email_box_user', models.CharField(help_text='Username for accessing this mailbox.', max_length=200, null=True, verbose_name='E-Mail Username', blank=True)),
                ('email_box_pass', models.CharField(help_text='Password for the above username', max_length=200, null=True, verbose_name='E-Mail Password', blank=True)),
                ('email_box_imap_folder', models.CharField(help_text='If using IMAP, what folder do you wish to fetch messages from? This allows you to use one IMAP account for multiple queues, by filtering messages on your IMAP server into separate folders. Default: INBOX.', max_length=100, null=True, verbose_name='IMAP Folder', blank=True)),
                ('email_box_interval', models.IntegerField(default=b'5', help_text='How often do you wish to check this mailbox? (in Minutes)', null=True, verbose_name='E-Mail Check Interval', blank=True)),
                ('email_box_last_check', models.DateTimeField(null=True, editable=False, blank=True)),
            ],
            options={
                'ordering': ('title',),
                'verbose_name': 'Queue',
                'verbose_name_plural': 'Queues',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SavedSearch',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('title', models.CharField(help_text='User-provided name for this query', max_length=100, verbose_name='Query Name')),
                ('shared', models.BooleanField(default=False, help_text='Should other users see this query?', verbose_name='Shared With Other Users?')),
                ('query', models.TextField(help_text='Pickled query object. Be wary changing this.', verbose_name='Search Query')),
                ('user', models.ForeignKey(verbose_name='User', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Saved search',
                'verbose_name_plural': 'Saved searches',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Ticket',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('title', models.CharField(max_length=200, verbose_name='Title')),
                ('created', models.DateTimeField(help_text='Date this ticket was first created', verbose_name='Created', blank=True)),
                ('modified', models.DateTimeField(help_text='Date this ticket was most recently changed.', verbose_name='Modified', blank=True)),
                ('submitter_email', models.EmailField(help_text='The submitter will receive an email for all public follow-ups left for this task.', max_length=75, null=True, verbose_name='Submitter E-Mail', blank=True)),
                ('status', models.IntegerField(default=1, verbose_name='Status', choices=[(1, 'Open'), (2, 'Reopened'), (3, 'Resolved'), (4, 'Closed'), (5, 'Duplicate')])),
                ('on_hold', models.BooleanField(default=False, help_text='If a ticket is on hold, it will not automatically be escalated.', verbose_name='On Hold')),
                ('description', models.TextField(help_text='The content of the customers query.', null=True, verbose_name='Description', blank=True)),
                ('resolution', models.TextField(help_text='The resolution provided to the customer by our staff.', null=True, verbose_name='Resolution', blank=True)),
                ('priority', models.IntegerField(default=3, help_text='1 = Highest Priority, 5 = Low Priority', blank=3, verbose_name='Priority', choices=[(1, '1. Critical'), (2, '2. High'), (3, '3. Normal'), (4, '4. Low'), (5, '5. Very Low')])),
                ('due_date', models.DateTimeField(null=True, verbose_name='Due on', blank=True)),
                ('last_escalation', models.DateTimeField(help_text='The date this ticket was last escalated - updated automatically by management/commands/escalate_tickets.py.', null=True, editable=False, blank=True)),
                ('assigned_to', models.ForeignKey(related_name=b'assigned_to', verbose_name='Assigned to', blank=True, to=settings.AUTH_USER_MODEL, null=True)),
                ('queue', models.ForeignKey(verbose_name='Queue', to='helpdesk.Queue')),
            ],
            options={
                'ordering': ('id',),
                'get_latest_by': 'created',
                'verbose_name': 'Ticket',
                'verbose_name_plural': 'Tickets',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TicketCC',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('email', models.EmailField(help_text='For non-user followers, enter their e-mail address', max_length=75, null=True, verbose_name='E-Mail Address', blank=True)),
                ('can_view', models.BooleanField(default=False, help_text='Can this CC login to view the ticket details?', verbose_name='Can View Ticket?')),
                ('can_update', models.BooleanField(default=False, help_text='Can this CC login and update the ticket?', verbose_name='Can Update Ticket?')),
                ('ticket', models.ForeignKey(verbose_name='Ticket', to='helpdesk.Ticket')),
                ('user', models.ForeignKey(blank=True, to=settings.AUTH_USER_MODEL, help_text='User who wishes to receive updates for this ticket.', null=True, verbose_name='User')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TicketChange',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('field', models.CharField(max_length=100, verbose_name='Field')),
                ('old_value', models.TextField(null=True, verbose_name='Old Value', blank=True)),
                ('new_value', models.TextField(null=True, verbose_name='New Value', blank=True)),
                ('followup', models.ForeignKey(verbose_name='Follow-up', to='helpdesk.FollowUp')),
            ],
            options={
                'verbose_name': 'Ticket change',
                'verbose_name_plural': 'Ticket changes',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TicketCustomFieldValue',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('value', models.TextField(null=True, blank=True)),
                ('field', models.ForeignKey(verbose_name='Field', to='helpdesk.CustomField')),
                ('ticket', models.ForeignKey(verbose_name='Ticket', to='helpdesk.Ticket')),
            ],
            options={
                'verbose_name': 'Ticket custom field value',
                'verbose_name_plural': 'Ticket custom field values',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TicketDependency',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('depends_on', models.ForeignKey(related_name=b'depends_on', verbose_name='Depends On Ticket', to='helpdesk.Ticket')),
                ('ticket', models.ForeignKey(related_name=b'ticketdependency', verbose_name='Ticket', to='helpdesk.Ticket')),
            ],
            options={
                'verbose_name': 'Ticket dependency',
                'verbose_name_plural': 'Ticket dependencies',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='UserSettings',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('settings_pickled', models.TextField(help_text='This is a base64-encoded representation of a pickled Python dictionary. Do not change this field via the admin.', null=True, verbose_name='Settings Dictionary', blank=True)),
                ('user', models.OneToOneField(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'User Setting',
                'verbose_name_plural': 'User Settings',
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='ticketdependency',
            unique_together=set([('ticket', 'depends_on')]),
        ),
        migrations.AddField(
            model_name='presetreply',
            name='queues',
            field=models.ManyToManyField(help_text='Leave blank to allow this reply to be used for all queues, or select those queues you wish to limit this reply to.', to='helpdesk.Queue', null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='ignoreemail',
            name='queues',
            field=models.ManyToManyField(help_text='Leave blank for this e-mail to be ignored on all queues, or select those queues you wish to ignore this e-mail for.', to='helpdesk.Queue', null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='followup',
            name='ticket',
            field=models.ForeignKey(verbose_name='Ticket', to='helpdesk.Ticket'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='followup',
            name='user',
            field=models.ForeignKey(verbose_name='User', blank=True, to=settings.AUTH_USER_MODEL, null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='escalationexclusion',
            name='queues',
            field=models.ManyToManyField(help_text='Leave blank for this exclusion to be applied to all queues, or select those queues you wish to exclude with this entry.', to='helpdesk.Queue', null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='attachment',
            name='followup',
            field=models.ForeignKey(verbose_name='Follow-up', to='helpdesk.FollowUp'),
            preserve_default=True,
        ),
    ]
