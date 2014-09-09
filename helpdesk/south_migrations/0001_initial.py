# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'Queue'
        db.create_table('helpdesk_queue', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('title', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('slug', self.gf('django.db.models.fields.SlugField')(max_length=50, db_index=True)),
            ('email_address', self.gf('django.db.models.fields.EmailField')(max_length=75, null=True, blank=True)),
            ('locale', self.gf('django.db.models.fields.CharField')(max_length=10, null=True, blank=True)),
            ('allow_public_submission', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('allow_email_submission', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('escalate_days', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            ('new_ticket_cc', self.gf('django.db.models.fields.CharField')(max_length=200, null=True, blank=True)),
            ('updated_ticket_cc', self.gf('django.db.models.fields.CharField')(max_length=200, null=True, blank=True)),
            ('email_box_type', self.gf('django.db.models.fields.CharField')(max_length=5, null=True, blank=True)),
            ('email_box_host', self.gf('django.db.models.fields.CharField')(max_length=200, null=True, blank=True)),
            ('email_box_port', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            ('email_box_ssl', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('email_box_user', self.gf('django.db.models.fields.CharField')(max_length=200, null=True, blank=True)),
            ('email_box_pass', self.gf('django.db.models.fields.CharField')(max_length=200, null=True, blank=True)),
            ('email_box_imap_folder', self.gf('django.db.models.fields.CharField')(max_length=100, null=True, blank=True)),
            ('email_box_interval', self.gf('django.db.models.fields.IntegerField')(default='5', null=True, blank=True)),
            ('email_box_last_check', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
        ))
        db.send_create_signal('helpdesk', ['Queue'])

        # Adding model 'Ticket'
        db.create_table('helpdesk_ticket', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('title', self.gf('django.db.models.fields.CharField')(max_length=200)),
            ('queue', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['helpdesk.Queue'])),
            ('created', self.gf('django.db.models.fields.DateTimeField')(blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(blank=True)),
            ('submitter_email', self.gf('django.db.models.fields.EmailField')(max_length=75, null=True, blank=True)),
            ('assigned_to', self.gf('django.db.models.fields.related.ForeignKey')(related_name='assigned_to', blank=True, null=True, to=orm['auth.User'])),
            ('status', self.gf('django.db.models.fields.IntegerField')(default=1)),
            ('on_hold', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('description', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('resolution', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('priority', self.gf('django.db.models.fields.IntegerField')(default=3, blank=3)),
            ('last_escalation', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
        ))
        db.send_create_signal('helpdesk', ['Ticket'])

        # Adding model 'FollowUp'
        db.create_table('helpdesk_followup', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('ticket', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['helpdesk.Ticket'])),
            ('date', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime(2011, 4, 27, 15, 17, 4, 272904))),
            ('title', self.gf('django.db.models.fields.CharField')(max_length=200, null=True, blank=True)),
            ('comment', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('public', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'], null=True, blank=True)),
            ('new_status', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
        ))
        db.send_create_signal('helpdesk', ['FollowUp'])

        # Adding model 'TicketChange'
        db.create_table('helpdesk_ticketchange', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('followup', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['helpdesk.FollowUp'])),
            ('field', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('old_value', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('new_value', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
        ))
        db.send_create_signal('helpdesk', ['TicketChange'])

        # Adding model 'Attachment'
        db.create_table('helpdesk_attachment', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('followup', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['helpdesk.FollowUp'])),
            ('file', self.gf('django.db.models.fields.files.FileField')(max_length=100)),
            ('filename', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('mime_type', self.gf('django.db.models.fields.CharField')(max_length=30)),
            ('size', self.gf('django.db.models.fields.IntegerField')()),
        ))
        db.send_create_signal('helpdesk', ['Attachment'])

        # Adding model 'PreSetReply'
        db.create_table('helpdesk_presetreply', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('body', self.gf('django.db.models.fields.TextField')()),
        ))
        db.send_create_signal('helpdesk', ['PreSetReply'])

        # Adding M2M table for field queues on 'PreSetReply'
        db.create_table('helpdesk_presetreply_queues', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('presetreply', models.ForeignKey(orm['helpdesk.presetreply'], null=False)),
            ('queue', models.ForeignKey(orm['helpdesk.queue'], null=False))
        ))
        db.create_unique('helpdesk_presetreply_queues', ['presetreply_id', 'queue_id'])

        # Adding model 'EscalationExclusion'
        db.create_table('helpdesk_escalationexclusion', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('date', self.gf('django.db.models.fields.DateField')()),
        ))
        db.send_create_signal('helpdesk', ['EscalationExclusion'])

        # Adding M2M table for field queues on 'EscalationExclusion'
        db.create_table('helpdesk_escalationexclusion_queues', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('escalationexclusion', models.ForeignKey(orm['helpdesk.escalationexclusion'], null=False)),
            ('queue', models.ForeignKey(orm['helpdesk.queue'], null=False))
        ))
        db.create_unique('helpdesk_escalationexclusion_queues', ['escalationexclusion_id', 'queue_id'])

        # Adding model 'EmailTemplate'
        db.create_table('helpdesk_emailtemplate', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('template_name', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('subject', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('heading', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('plain_text', self.gf('django.db.models.fields.TextField')()),
            ('html', self.gf('django.db.models.fields.TextField')()),
            ('locale', self.gf('django.db.models.fields.CharField')(max_length=10, null=True, blank=True)),
        ))
        db.send_create_signal('helpdesk', ['EmailTemplate'])

        # Adding model 'KBCategory'
        db.create_table('helpdesk_kbcategory', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('title', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('slug', self.gf('django.db.models.fields.SlugField')(max_length=50, db_index=True)),
            ('description', self.gf('django.db.models.fields.TextField')()),
        ))
        db.send_create_signal('helpdesk', ['KBCategory'])

        # Adding model 'KBItem'
        db.create_table('helpdesk_kbitem', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('category', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['helpdesk.KBCategory'])),
            ('title', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('question', self.gf('django.db.models.fields.TextField')()),
            ('answer', self.gf('django.db.models.fields.TextField')()),
            ('votes', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('recommendations', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('last_updated', self.gf('django.db.models.fields.DateTimeField')(blank=True)),
        ))
        db.send_create_signal('helpdesk', ['KBItem'])

        # Adding model 'SavedSearch'
        db.create_table('helpdesk_savedsearch', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'])),
            ('title', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('shared', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('query', self.gf('django.db.models.fields.TextField')()),
        ))
        db.send_create_signal('helpdesk', ['SavedSearch'])

        # Adding model 'UserSettings'
        db.create_table('helpdesk_usersettings', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['auth.User'], unique=True)),
            ('settings_pickled', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
        ))
        db.send_create_signal('helpdesk', ['UserSettings'])

        # Adding model 'IgnoreEmail'
        db.create_table('helpdesk_ignoreemail', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('date', self.gf('django.db.models.fields.DateField')(blank=True)),
            ('email_address', self.gf('django.db.models.fields.CharField')(max_length=150)),
            ('keep_in_mailbox', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('helpdesk', ['IgnoreEmail'])

        # Adding M2M table for field queues on 'IgnoreEmail'
        db.create_table('helpdesk_ignoreemail_queues', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('ignoreemail', models.ForeignKey(orm['helpdesk.ignoreemail'], null=False)),
            ('queue', models.ForeignKey(orm['helpdesk.queue'], null=False))
        ))
        db.create_unique('helpdesk_ignoreemail_queues', ['ignoreemail_id', 'queue_id'])

        # Adding model 'TicketCC'
        db.create_table('helpdesk_ticketcc', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('ticket', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['helpdesk.Ticket'])),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'], null=True, blank=True)),
            ('email', self.gf('django.db.models.fields.EmailField')(max_length=75, null=True, blank=True)),
            ('can_view', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('can_update', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('helpdesk', ['TicketCC'])

        # Adding model 'CustomField'
        db.create_table('helpdesk_customfield', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.SlugField')(max_length=50, unique=True, db_index=True)),
            ('label', self.gf('django.db.models.fields.CharField')(max_length='30')),
            ('help_text', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('data_type', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('max_length', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            ('decimal_places', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            ('list_values', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('required', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('staff_only', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('helpdesk', ['CustomField'])

        # Adding model 'TicketCustomFieldValue'
        db.create_table('helpdesk_ticketcustomfieldvalue', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('ticket', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['helpdesk.Ticket'])),
            ('field', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['helpdesk.CustomField'])),
            ('value', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
        ))
        db.send_create_signal('helpdesk', ['TicketCustomFieldValue'])

        # Adding unique constraint on 'TicketCustomFieldValue', fields ['ticket', 'field']
        db.create_unique('helpdesk_ticketcustomfieldvalue', ['ticket_id', 'field_id'])


    def backwards(self, orm):
        
        # Removing unique constraint on 'TicketCustomFieldValue', fields ['ticket', 'field']
        db.delete_unique('helpdesk_ticketcustomfieldvalue', ['ticket_id', 'field_id'])

        # Deleting model 'Queue'
        db.delete_table('helpdesk_queue')

        # Deleting model 'Ticket'
        db.delete_table('helpdesk_ticket')

        # Deleting model 'FollowUp'
        db.delete_table('helpdesk_followup')

        # Deleting model 'TicketChange'
        db.delete_table('helpdesk_ticketchange')

        # Deleting model 'Attachment'
        db.delete_table('helpdesk_attachment')

        # Deleting model 'PreSetReply'
        db.delete_table('helpdesk_presetreply')

        # Removing M2M table for field queues on 'PreSetReply'
        db.delete_table('helpdesk_presetreply_queues')

        # Deleting model 'EscalationExclusion'
        db.delete_table('helpdesk_escalationexclusion')

        # Removing M2M table for field queues on 'EscalationExclusion'
        db.delete_table('helpdesk_escalationexclusion_queues')

        # Deleting model 'EmailTemplate'
        db.delete_table('helpdesk_emailtemplate')

        # Deleting model 'KBCategory'
        db.delete_table('helpdesk_kbcategory')

        # Deleting model 'KBItem'
        db.delete_table('helpdesk_kbitem')

        # Deleting model 'SavedSearch'
        db.delete_table('helpdesk_savedsearch')

        # Deleting model 'UserSettings'
        db.delete_table('helpdesk_usersettings')

        # Deleting model 'IgnoreEmail'
        db.delete_table('helpdesk_ignoreemail')

        # Removing M2M table for field queues on 'IgnoreEmail'
        db.delete_table('helpdesk_ignoreemail_queues')

        # Deleting model 'TicketCC'
        db.delete_table('helpdesk_ticketcc')

        # Deleting model 'CustomField'
        db.delete_table('helpdesk_customfield')

        # Deleting model 'TicketCustomFieldValue'
        db.delete_table('helpdesk_ticketcustomfieldvalue')


    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '80', 'unique': 'True'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        'auth.permission': {
            'Meta': {'ordering': "('content_type__app_label', 'content_type__model', 'codename')", 'unique_together': "(('content_type', 'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '30', 'unique': 'True'})
        },
        'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'helpdesk.attachment': {
            'Meta': {'ordering': "['filename']", 'object_name': 'Attachment'},
            'file': ('django.db.models.fields.files.FileField', [], {'max_length': '100'}),
            'filename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'followup': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['helpdesk.FollowUp']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'mime_type': ('django.db.models.fields.CharField', [], {'max_length': '30'}),
            'size': ('django.db.models.fields.IntegerField', [], {})
        },
        'helpdesk.customfield': {
            'Meta': {'object_name': 'CustomField'},
            'data_type': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'decimal_places': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'help_text': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'label': ('django.db.models.fields.CharField', [], {'max_length': "'30'"}),
            'list_values': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'max_length': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.SlugField', [], {'max_length': '50', 'unique': 'True', 'db_index': 'True'}),
            'required': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'staff_only': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'helpdesk.emailtemplate': {
            'Meta': {'ordering': "['template_name', 'locale']", 'object_name': 'EmailTemplate'},
            'heading': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'html': ('django.db.models.fields.TextField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'locale': ('django.db.models.fields.CharField', [], {'max_length': '10', 'null': 'True', 'blank': 'True'}),
            'plain_text': ('django.db.models.fields.TextField', [], {}),
            'subject': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'template_name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'helpdesk.escalationexclusion': {
            'Meta': {'object_name': 'EscalationExclusion'},
            'date': ('django.db.models.fields.DateField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'queues': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['helpdesk.Queue']", 'symmetrical': 'False', 'null': 'True', 'blank': 'True'})
        },
        'helpdesk.followup': {
            'Meta': {'ordering': "['date']", 'object_name': 'FollowUp'},
            'comment': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'date': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2011, 4, 27, 15, 17, 4, 272904)'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'new_status': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'public': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ticket': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['helpdesk.Ticket']"}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'})
        },
        'helpdesk.ignoreemail': {
            'Meta': {'object_name': 'IgnoreEmail'},
            'date': ('django.db.models.fields.DateField', [], {'blank': 'True'}),
            'email_address': ('django.db.models.fields.CharField', [], {'max_length': '150'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'keep_in_mailbox': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'queues': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['helpdesk.Queue']", 'symmetrical': 'False', 'null': 'True', 'blank': 'True'})
        },
        'helpdesk.kbcategory': {
            'Meta': {'ordering': "['title']", 'object_name': 'KBCategory'},
            'description': ('django.db.models.fields.TextField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'slug': ('django.db.models.fields.SlugField', [], {'max_length': '50', 'db_index': 'True'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'helpdesk.kbitem': {
            'Meta': {'ordering': "['title']", 'object_name': 'KBItem'},
            'answer': ('django.db.models.fields.TextField', [], {}),
            'category': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['helpdesk.KBCategory']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_updated': ('django.db.models.fields.DateTimeField', [], {'blank': 'True'}),
            'question': ('django.db.models.fields.TextField', [], {}),
            'recommendations': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'votes': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        },
        'helpdesk.presetreply': {
            'Meta': {'ordering': "['name']", 'object_name': 'PreSetReply'},
            'body': ('django.db.models.fields.TextField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'queues': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['helpdesk.Queue']", 'symmetrical': 'False', 'null': 'True', 'blank': 'True'})
        },
        'helpdesk.queue': {
            'Meta': {'ordering': "('title',)", 'object_name': 'Queue'},
            'allow_email_submission': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'allow_public_submission': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'email_address': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'null': 'True', 'blank': 'True'}),
            'email_box_host': ('django.db.models.fields.CharField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'email_box_imap_folder': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'email_box_interval': ('django.db.models.fields.IntegerField', [], {'default': "'5'", 'null': 'True', 'blank': 'True'}),
            'email_box_last_check': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'email_box_pass': ('django.db.models.fields.CharField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'email_box_port': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'email_box_ssl': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'email_box_type': ('django.db.models.fields.CharField', [], {'max_length': '5', 'null': 'True', 'blank': 'True'}),
            'email_box_user': ('django.db.models.fields.CharField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'escalate_days': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'locale': ('django.db.models.fields.CharField', [], {'max_length': '10', 'null': 'True', 'blank': 'True'}),
            'new_ticket_cc': ('django.db.models.fields.CharField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'slug': ('django.db.models.fields.SlugField', [], {'max_length': '50', 'db_index': 'True'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'updated_ticket_cc': ('django.db.models.fields.CharField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'})
        },
        'helpdesk.savedsearch': {
            'Meta': {'object_name': 'SavedSearch'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'query': ('django.db.models.fields.TextField', [], {}),
            'shared': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        },
        'helpdesk.ticket': {
            'Meta': {'object_name': 'Ticket'},
            'assigned_to': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'assigned_to'", 'blank': 'True', 'null': 'True', 'to': "orm['auth.User']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_escalation': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'blank': 'True'}),
            'on_hold': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'priority': ('django.db.models.fields.IntegerField', [], {'default': '3', 'blank': '3'}),
            'queue': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['helpdesk.Queue']"}),
            'resolution': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'submitter_email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'null': 'True', 'blank': 'True'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '200'})
        },
        'helpdesk.ticketcc': {
            'Meta': {'object_name': 'TicketCC'},
            'can_update': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'can_view': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ticket': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['helpdesk.Ticket']"}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'})
        },
        'helpdesk.ticketchange': {
            'Meta': {'object_name': 'TicketChange'},
            'field': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'followup': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['helpdesk.FollowUp']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'new_value': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'old_value': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'})
        },
        'helpdesk.ticketcustomfieldvalue': {
            'Meta': {'unique_together': "(('ticket', 'field'),)", 'object_name': 'TicketCustomFieldValue'},
            'field': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['helpdesk.CustomField']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ticket': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['helpdesk.Ticket']"}),
            'value': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'})
        },
        'helpdesk.usersettings': {
            'Meta': {'object_name': 'UserSettings'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'settings_pickled': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['auth.User']", 'unique': 'True'})
        }
    }

    complete_apps = ['helpdesk']
