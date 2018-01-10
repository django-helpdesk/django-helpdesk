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
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('file', models.FileField(upload_to=helpdesk.models.attachment_path, verbose_name='File', max_length=1000)),
                ('filename', models.CharField(verbose_name='Filename', max_length=1000)),
                ('mime_type', models.CharField(verbose_name='MIME Type', max_length=255)),
                ('size', models.IntegerField(verbose_name='Size', help_text='Size of this file in bytes')),
            ],
            options={
                'verbose_name_plural': 'Attachments',
                'verbose_name': 'Attachment',
                'ordering': ['filename'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='CustomField',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('name', models.SlugField(help_text='As used in the database and behind the scenes. Must be unique and consist of only lowercase letters with no punctuation.', verbose_name='Field Name', unique=True)),
                ('label', models.CharField(verbose_name='Label', help_text='The display label for this field', max_length='30')),
                ('help_text', models.TextField(null=True, verbose_name='Help Text', blank=True, help_text='Shown to the user when editing the ticket')),
                ('data_type', models.CharField(choices=[('varchar', 'Character (single line)'), ('text', 'Text (multi-line)'), ('integer', 'Integer'), ('decimal', 'Decimal'), ('list', 'List'), ('boolean', 'Boolean (checkbox yes/no)'), ('date', 'Date'), ('time', 'Time'), ('datetime', 'Date & Time'), ('email', 'E-Mail Address'), ('url', 'URL'), ('ipaddress', 'IP Address'), ('slug', 'Slug')], verbose_name='Data Type', help_text='Allows you to restrict the data entered into this field', max_length=100)),
                ('max_length', models.IntegerField(null=True, verbose_name='Maximum Length (characters)', blank=True)),
                ('decimal_places', models.IntegerField(null=True, verbose_name='Decimal Places', blank=True, help_text='Only used for decimal fields')),
                ('empty_selection_list', models.BooleanField(verbose_name='Add empty first choice to List?', default=False, help_text='Only for List: adds an empty first entry to the choices list, which enforces that the user makes an active choice.')),
                ('list_values', models.TextField(null=True, verbose_name='List Values', blank=True, help_text='For list fields only. Enter one option per line.')),
                ('ordering', models.IntegerField(null=True, verbose_name='Ordering', blank=True, help_text='Lower numbers are displayed first; higher numbers are listed later')),
                ('required', models.BooleanField(verbose_name='Required?', default=False, help_text='Does the user have to enter a value for this field?')),
                ('staff_only', models.BooleanField(verbose_name='Staff Only?', default=False, help_text='If this is ticked, then the public submission form will NOT show this field')),
            ],
            options={
                'verbose_name_plural': 'Custom fields',
                'verbose_name': 'Custom field',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='EmailTemplate',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('template_name', models.CharField(verbose_name='Template Name', max_length=100)),
                ('subject', models.CharField(verbose_name='Subject', help_text='This will be prefixed with "[ticket.ticket] ticket.title". We recommend something simple such as "(Updated") or "(Closed)" - the same context is available as in plain_text, below.', max_length=100)),
                ('heading', models.CharField(verbose_name='Heading', help_text='In HTML e-mails, this will be the heading at the top of the email - the same context is available as in plain_text, below.', max_length=100)),
                ('plain_text', models.TextField(verbose_name='Plain Text', help_text='The context available to you includes {{ ticket }}, {{ queue }}, and depending on the time of the call: {{ resolution }} or {{ comment }}.')),
                ('html', models.TextField(verbose_name='HTML', help_text='The same context is available here as in plain_text, above.')),
                ('locale', models.CharField(null=True, verbose_name='Locale', help_text='Locale of this template.', blank=True, max_length=10)),
            ],
            options={
                'verbose_name_plural': 'e-mail templates',
                'verbose_name': 'e-mail template',
                'ordering': ['template_name', 'locale'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='EscalationExclusion',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('name', models.CharField(verbose_name='Name', max_length=100)),
                ('date', models.DateField(verbose_name='Date', help_text='Date on which escalation should not happen')),
            ],
            options={
                'verbose_name_plural': 'Escalation exclusions',
                'verbose_name': 'Escalation exclusion',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='FollowUp',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('date', models.DateTimeField(verbose_name='Date', default=django.utils.timezone.now)),
                ('title', models.CharField(null=True, verbose_name='Title', blank=True, max_length=200)),
                ('comment', models.TextField(null=True, verbose_name='Comment', blank=True)),
                ('public', models.BooleanField(verbose_name='Public', default=False, help_text='Public tickets are viewable by the submitter and all staff, but non-public tickets can only be seen by staff.')),
                ('new_status', models.IntegerField(null=True, verbose_name='New Status', help_text='If the status was changed, what was it changed to?', blank=True, choices=[(1, 'Open'), (2, 'Reopened'), (3, 'Resolved'), (4, 'Closed'), (5, 'Duplicate')])),
            ],
            options={
                'verbose_name_plural': 'Follow-ups',
                'verbose_name': 'Follow-up',
                'ordering': ['date'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='IgnoreEmail',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('name', models.CharField(verbose_name='Name', max_length=100)),
                ('date', models.DateField(editable=False, verbose_name='Date', blank=True, help_text='Date on which this e-mail address was added')),
                ('email_address', models.CharField(verbose_name='E-Mail Address', help_text='Enter a full e-mail address, or portions with wildcards, eg *@domain.com or postmaster@*.', max_length=150)),
                ('keep_in_mailbox', models.BooleanField(verbose_name='Save Emails in Mailbox?', default=False, help_text='Do you want to save emails from this address in the mailbox? If this is unticked, emails from this address will be deleted.')),
            ],
            options={
                'verbose_name_plural': 'Ignored e-mail addresses',
                'verbose_name': 'Ignored e-mail address',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='KBCategory',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('title', models.CharField(verbose_name='Title', max_length=100)),
                ('slug', models.SlugField(verbose_name='Slug')),
                ('description', models.TextField(verbose_name='Description')),
            ],
            options={
                'verbose_name_plural': 'Knowledge base categories',
                'verbose_name': 'Knowledge base category',
                'ordering': ['title'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='KBItem',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('title', models.CharField(verbose_name='Title', max_length=100)),
                ('question', models.TextField(verbose_name='Question')),
                ('answer', models.TextField(verbose_name='Answer')),
                ('votes', models.IntegerField(verbose_name='Votes', default=0, help_text='Total number of votes cast for this item')),
                ('recommendations', models.IntegerField(verbose_name='Positive Votes', default=0, help_text='Number of votes for this item which were POSITIVE.')),
                ('last_updated', models.DateTimeField(verbose_name='Last Updated', blank=True, help_text='The date on which this question was most recently changed.')),
                ('category', models.ForeignKey(verbose_name='Category', to='helpdesk.KBCategory', on_delete=models.CASCADE)),
            ],
            options={
                'verbose_name_plural': 'Knowledge base items',
                'verbose_name': 'Knowledge base item',
                'ordering': ['title'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='PreSetReply',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('name', models.CharField(verbose_name='Name', help_text='Only used to assist users with selecting a reply - not shown to the user.', max_length=100)),
                ('body', models.TextField(verbose_name='Body', help_text='Context available: {{ ticket }} - ticket object (eg {{ ticket.title }}); {{ queue }} - The queue; and {{ user }} - the current user.')),
            ],
            options={
                'verbose_name_plural': 'Pre-set replies',
                'verbose_name': 'Pre-set reply',
                'ordering': ['name'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Queue',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('title', models.CharField(verbose_name='Title', max_length=100)),
                ('slug', models.SlugField(verbose_name='Slug', help_text="This slug is used when building ticket ID's. Once set, try not to change it or e-mailing may get messy.")),
                ('email_address', models.EmailField(null=True, verbose_name='E-Mail Address', help_text='All outgoing e-mails for this queue will use this e-mail address. If you use IMAP or POP3, this should be the e-mail address for that mailbox.', blank=True, max_length=75)),
                ('locale', models.CharField(null=True, verbose_name='Locale', help_text='Locale of this queue. All correspondence in this queue will be in this language.', blank=True, max_length=10)),
                ('allow_public_submission', models.BooleanField(verbose_name='Allow Public Submission?', default=False, help_text='Should this queue be listed on the public submission form?')),
                ('allow_email_submission', models.BooleanField(verbose_name='Allow E-Mail Submission?', default=False, help_text='Do you want to poll the e-mail box below for new tickets?')),
                ('escalate_days', models.IntegerField(null=True, verbose_name='Escalation Days', blank=True, help_text='For tickets which are not held, how often do you wish to increase their priority? Set to 0 for no escalation.')),
                ('new_ticket_cc', models.CharField(null=True, verbose_name='New Ticket CC Address', help_text='If an e-mail address is entered here, then it will receive notification of all new tickets created for this queue. Enter a comma between multiple e-mail addresses.', blank=True, max_length=200)),
                ('updated_ticket_cc', models.CharField(null=True, verbose_name='Updated Ticket CC Address', help_text='If an e-mail address is entered here, then it will receive notification of all activity (new tickets, closed tickets, updates, reassignments, etc) for this queue. Separate multiple addresses with a comma.', blank=True, max_length=200)),
                ('email_box_type', models.CharField(null=True, verbose_name='E-Mail Box Type', help_text='E-Mail server type for creating tickets automatically from a mailbox - both POP3 and IMAP are supported.', blank=True, max_length=5, choices=[('pop3', 'POP 3'), ('imap', 'IMAP')])),
                ('email_box_host', models.CharField(null=True, verbose_name='E-Mail Hostname', help_text='Your e-mail server address - either the domain name or IP address. May be "localhost".', blank=True, max_length=200)),
                ('email_box_port', models.IntegerField(null=True, verbose_name='E-Mail Port', blank=True, help_text='Port number to use for accessing e-mail. Default for POP3 is "110", and for IMAP is "143". This may differ on some servers. Leave it blank to use the defaults.')),
                ('email_box_ssl', models.BooleanField(verbose_name='Use SSL for E-Mail?', default=False, help_text='Whether to use SSL for IMAP or POP3 - the default ports when using SSL are 993 for IMAP and 995 for POP3.')),
                ('email_box_user', models.CharField(null=True, verbose_name='E-Mail Username', help_text='Username for accessing this mailbox.', blank=True, max_length=200)),
                ('email_box_pass', models.CharField(null=True, verbose_name='E-Mail Password', help_text='Password for the above username', blank=True, max_length=200)),
                ('email_box_imap_folder', models.CharField(null=True, verbose_name='IMAP Folder', help_text='If using IMAP, what folder do you wish to fetch messages from? This allows you to use one IMAP account for multiple queues, by filtering messages on your IMAP server into separate folders. Default: INBOX.', blank=True, max_length=100)),
                ('email_box_interval', models.IntegerField(null=True, verbose_name='E-Mail Check Interval', blank=True, default='5', help_text='How often do you wish to check this mailbox? (in Minutes)')),
                ('email_box_last_check', models.DateTimeField(editable=False, null=True, blank=True)),
                ('socks_proxy_type', models.CharField(null=True, verbose_name='Socks Proxy Type', help_text='SOCKS4 or SOCKS5 allows you to proxy your connections through a SOCKS server.', blank=True, max_length=8, choices=[('socks4', 'SOCKS4'), ('socks5', 'SOCKS5')])),
                ('socks_proxy_host', models.GenericIPAddressField(null=True, verbose_name='Socks Proxy Host', help_text='Socks proxy IP address. Default: 127.0.0.1', blank=True)),
                ('socks_proxy_port', models.IntegerField(null=True, verbose_name='Socks Proxy Port', blank=True, help_text='Socks proxy port number. Default: 9150 (default TOR port)')),
            ],
            options={
                'verbose_name_plural': 'Queues',
                'verbose_name': 'Queue',
                'ordering': ('title',),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SavedSearch',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('title', models.CharField(verbose_name='Query Name', help_text='User-provided name for this query', max_length=100)),
                ('shared', models.BooleanField(verbose_name='Shared With Other Users?', default=False, help_text='Should other users see this query?')),
                ('query', models.TextField(verbose_name='Search Query', help_text='Pickled query object. Be wary changing this.')),
                ('user', models.ForeignKey(verbose_name='User', to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE)),
            ],
            options={
                'verbose_name_plural': 'Saved searches',
                'verbose_name': 'Saved search',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Ticket',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('title', models.CharField(verbose_name='Title', max_length=200)),
                ('created', models.DateTimeField(verbose_name='Created', blank=True, help_text='Date this ticket was first created')),
                ('modified', models.DateTimeField(verbose_name='Modified', blank=True, help_text='Date this ticket was most recently changed.')),
                ('submitter_email', models.EmailField(null=True, verbose_name='Submitter E-Mail', help_text='The submitter will receive an email for all public follow-ups left for this task.', blank=True, max_length=75)),
                ('status', models.IntegerField(verbose_name='Status', default=1, choices=[(1, 'Open'), (2, 'Reopened'), (3, 'Resolved'), (4, 'Closed'), (5, 'Duplicate')])),
                ('on_hold', models.BooleanField(verbose_name='On Hold', default=False, help_text='If a ticket is on hold, it will not automatically be escalated.')),
                ('description', models.TextField(null=True, verbose_name='Description', blank=True, help_text='The content of the customers query.')),
                ('resolution', models.TextField(null=True, verbose_name='Resolution', blank=True, help_text='The resolution provided to the customer by our staff.')),
                ('priority', models.IntegerField(verbose_name='Priority', help_text='1 = Highest Priority, 5 = Low Priority', blank=3, default=3, choices=[(1, '1. Critical'), (2, '2. High'), (3, '3. Normal'), (4, '4. Low'), (5, '5. Very Low')])),
                ('due_date', models.DateTimeField(null=True, verbose_name='Due on', blank=True)),
                ('last_escalation', models.DateTimeField(editable=False, null=True, blank=True, help_text='The date this ticket was last escalated - updated automatically by management/commands/escalate_tickets.py.')),
                ('assigned_to', models.ForeignKey(null=True, verbose_name='Assigned to', blank=True, related_name='assigned_to', to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE)),
                ('queue', models.ForeignKey(verbose_name='Queue', to='helpdesk.Queue', on_delete=models.CASCADE)),
            ],
            options={
                'verbose_name_plural': 'Tickets',
                'verbose_name': 'Ticket',
                'ordering': ('id',),
                'get_latest_by': 'created',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TicketCC',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('email', models.EmailField(null=True, verbose_name='E-Mail Address', help_text='For non-user followers, enter their e-mail address', blank=True, max_length=75)),
                ('can_view', models.BooleanField(verbose_name='Can View Ticket?', default=False, help_text='Can this CC login to view the ticket details?')),
                ('can_update', models.BooleanField(verbose_name='Can Update Ticket?', default=False, help_text='Can this CC login and update the ticket?')),
                ('ticket', models.ForeignKey(verbose_name='Ticket', to='helpdesk.Ticket', on_delete=models.CASCADE)),
                ('user', models.ForeignKey(null=True, verbose_name='User', blank=True, to=settings.AUTH_USER_MODEL, help_text='User who wishes to receive updates for this ticket.', on_delete=models.CASCADE)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TicketChange',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('field', models.CharField(verbose_name='Field', max_length=100)),
                ('old_value', models.TextField(null=True, verbose_name='Old Value', blank=True)),
                ('new_value', models.TextField(null=True, verbose_name='New Value', blank=True)),
                ('followup', models.ForeignKey(verbose_name='Follow-up', to='helpdesk.FollowUp', on_delete=models.CASCADE)),
            ],
            options={
                'verbose_name_plural': 'Ticket changes',
                'verbose_name': 'Ticket change',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TicketCustomFieldValue',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('value', models.TextField(null=True, blank=True)),
                ('field', models.ForeignKey(verbose_name='Field', to='helpdesk.CustomField', on_delete=models.CASCADE)),
                ('ticket', models.ForeignKey(verbose_name='Ticket', to='helpdesk.Ticket', on_delete=models.CASCADE)),
            ],
            options={
                'verbose_name_plural': 'Ticket custom field values',
                'verbose_name': 'Ticket custom field value',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TicketDependency',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('depends_on', models.ForeignKey(related_name='depends_on', verbose_name='Depends On Ticket', to='helpdesk.Ticket', on_delete=models.CASCADE)),
                ('ticket', models.ForeignKey(related_name='ticketdependency', verbose_name='Ticket', to='helpdesk.Ticket', on_delete=models.CASCADE)),
            ],
            options={
                'verbose_name_plural': 'Ticket dependencies',
                'verbose_name': 'Ticket dependency',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='UserSettings',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('settings_pickled', models.TextField(null=True, verbose_name='Settings Dictionary', blank=True, help_text='This is a base64-encoded representation of a pickled Python dictionary. Do not change this field via the admin.')),
                ('user', models.OneToOneField(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE)),
            ],
            options={
                'verbose_name_plural': 'User Settings',
                'verbose_name': 'User Setting',
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
            field=models.ManyToManyField(null=True, to='helpdesk.Queue', blank=True, help_text='Leave blank to allow this reply to be used for all queues, or select those queues you wish to limit this reply to.'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='ignoreemail',
            name='queues',
            field=models.ManyToManyField(null=True, to='helpdesk.Queue', blank=True, help_text='Leave blank for this e-mail to be ignored on all queues, or select those queues you wish to ignore this e-mail for.'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='followup',
            name='ticket',
            field=models.ForeignKey(verbose_name='Ticket', to='helpdesk.Ticket', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='followup',
            name='user',
            field=models.ForeignKey(null=True, verbose_name='User', blank=True, to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='escalationexclusion',
            name='queues',
            field=models.ManyToManyField(null=True, to='helpdesk.Queue', blank=True, help_text='Leave blank for this exclusion to be applied to all queues, or select those queues you wish to exclude with this entry.'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='attachment',
            name='followup',
            field=models.ForeignKey(verbose_name='Follow-up', to='helpdesk.FollowUp', on_delete=models.CASCADE),
            preserve_default=True,
        ),
    ]
