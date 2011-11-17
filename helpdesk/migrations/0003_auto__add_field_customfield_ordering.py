# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding field 'CustomField.ordering'
        db.add_column('helpdesk_customfield', 'ordering', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True), keep_default=False)


    def backwards(self, orm):
        
        # Deleting field 'CustomField.ordering'
        db.delete_column('helpdesk_customfield', 'ordering')


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
            'ordering': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
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
            'date': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2011, 11, 8, 17, 57, 6, 688466)'}),
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
        'helpdesk.ticketdependency': {
            'Meta': {'unique_together': "(('ticket', 'depends_on'),)", 'object_name': 'TicketDependency'},
            'depends_on': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'depends_on'", 'to': "orm['helpdesk.Ticket']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ticket': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'ticketdependency'", 'to': "orm['helpdesk.Ticket']"})
        },
        'helpdesk.usersettings': {
            'Meta': {'object_name': 'UserSettings'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'settings_pickled': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['auth.User']", 'unique': 'True'})
        }
    }

    complete_apps = ['helpdesk']
