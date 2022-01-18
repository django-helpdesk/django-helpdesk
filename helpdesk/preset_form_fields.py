import datetime
# Contains the SQL command used to initialze the databse.
'''
// Preset Fields:
//    Queue           Submitter Email     Primary Contact Name        Subject/Title           Description
//    Building Name   Building Address    Building ID                 Portfolio ManagerID     Attachments
//    Due Date        Priority            Email

// Replace # with a FormType id/pk
PSQL Command
INSERT INTO helpdesk_customfield(
field_name, label, help_text,
data_type, max_length, decimal_places, list_values, empty_selection_list, notifications,
form_ordering, view_ordering,
required, staff_only, editable, unlisted, is_extra_data,
created, modified, ticket_form_id)
VALUES

('queue', 'Queue', '',
null,null,null,null, False, False,
1,1,
True, True, True, True, False,
NOW(), NOW(), #),

('submitter_email', 'Submitter Email', 'This e-mail address will receive copies of all public updates to this ticket.',
'email',200,null,null, False, True,
2,2,
True, False, True, True, False,
NOW(), NOW(), #),

('contact_name', 'Primary Contact Name', '',
'varchar',200,null,null, False, False,
3,3,
True, False, True, False, False,
NOW(), NOW(), #),

('contact_email', 'Primary Contact Email', 'This e-mail address will receive copies of all public updates to this ticket.',
'email',200,null,null, False, True,
4,4,
True, False, True, False, False,
NOW(), NOW(), #),

('title', 'Subject', '',
'varchar',200,null,null, False, False,
5,5,
False, False, True, True, False,
NOW(), NOW(), #),

('description', 'Description', '',
'text',null,null,null, False, False,
6,6,
False, False, True, True, False,
NOW(), NOW(), #),

('building_name', 'Building Name', '',
'varchar',200,null,null, False, False,
7,7,
False, False, True, False, False,
NOW(), NOW(), #),

('building_address', 'Building Address', '',
'text',null,null,null, False, False,
8,8,
False, False, True, False, False,
NOW(), NOW(), #),

('building_id', 'Building ID', '',
'varchar',200,null,null, False, False,
9,9,
False, False, True, False, False,
NOW(), NOW(), #),

('pm_id', 'Portfolio Manager ID', '',
'varchar',200,null,null, False, False,
10,10,
False, False, True, False, False,
NOW(), NOW(), #),

('attachment', 'Attachments', '',
null,null,null,null, False, False,
11,11,
False, False, False, True, False,
NOW(), NOW(), #),

('due_date', 'Due Date', '',
null,null,null,null, False, False,
12,12,
False, False, True, True, False,
NOW(), NOW(), #),

('priority', 'Priority', E'Please select a priority carefully. If unsure, leave it as \'3\'.',
null,null,null,null, False, False,
13,13,
False, False, True, True, False,
NOW(), NOW(), #),

('cc_emails', 'Email Addresses to CC', 'List email addresses to add to a ticket's CC list when it is created.',
'text',null,null,null,False,True,
14,14,
False,False,False,True,False,
NOW(), NOW(), #);

'''

def get_preset_fields(ticket_form):
    to_insert = [
            ('queue', 'Queue', '',
            None, None, None, None, False, False,
            1, 1,
            True, False, True, True, False,
            datetime.datetime.now(), datetime.datetime.now(), ticket_form),

            ('submitter_email', 'Submitter Email', 'This e-mail address will receive copies of all public updates to this ticket.',
            'email', 200, None, None, False, True,
            2, 2,
            True, False, True, True, False,
            datetime.datetime.now(), datetime.datetime.now(), ticket_form),

            ('contact_name', 'Primary Contact Name', '',
            'varchar', 200, None, None, False, False,
            3, 3,
            True, False, True, False, False,
            datetime.datetime.now(), datetime.datetime.now(), ticket_form),

            ('contact_email', 'Primary Contact Email', 'This e-mail address will receive copies of all public updates to this ticket.',
            'email', 200, None, None, False, True,
            4, 4,
            True, False, True, False, False,
            datetime.datetime.now(), datetime.datetime.now(), ticket_form),

            ('title', 'Subject', '',
            'varchar', 200, None, None, False, False,
            5, 5,
            False, False, True, True, False,
            datetime.datetime.now(), datetime.datetime.now(), ticket_form),

            ('description', 'Description', '',
            'text', None, None, None, False, False,
            6, 6,
            False, False, True, True, False,
            datetime.datetime.now(), datetime.datetime.now(), ticket_form),

            ('building_name', 'Building Name', '',
            'varchar', 200, None, None, False, False,
            7, 7,
            False, False, True, False, False,
            datetime.datetime.now(), datetime.datetime.now(), ticket_form),

            ('building_address', 'Building Address', '',
            'text', None, None, None, False, False,
            8, 8,
            False, False, True, False, False,
            datetime.datetime.now(), datetime.datetime.now(), ticket_form),

            ('building_id', 'Building ID', '',
            'varchar', 200, None, None, False, False,
            9, 9,
            False, False, True, False, False,
            datetime.datetime.now(), datetime.datetime.now(), ticket_form),

            ('pm_id', 'Portfolio Manager ID', '',
            'varchar', 200, None, None, False, False,
            10, 10,
            False, False, True, False, False,
            datetime.datetime.now(), datetime.datetime.now(), ticket_form),

            ('attachment', 'Attachments', '',
            None, None, None, None, False, False,
            11, 11,
            False, False, False, True, False,
            datetime.datetime.now(), datetime.datetime.now(), ticket_form),

            ('due_date', 'Due Date', '',
            None, None, None, None, False, False,
            12, 12,
            False, False, True, True, False,
            datetime.datetime.now(), datetime.datetime.now(), ticket_form),

            ('priority', 'Priority', 'Please select a priority carefully. If unsure, leave it as \'3\'.',
            None, None, None, None, False, False,
            13, 13,
            False, False, True, True, False,
            datetime.datetime.now(), datetime.datetime.now(), ticket_form),

            ('cc_emails', 'Email Addresses to CC', "List emails to add to a ticket's CC list when it is created.",
            'text', None, None, None, False, False,
            14, 14,
            False, True, False, True, False,
            datetime.datetime.now(), datetime.datetime.now(), ticket_form),
            ]
    to_return = []
    for field in to_insert:
        to_return.append({
                "field_name": field[0],
                "label": field[1],
                "help_text": field[2],
                "data_type": field[3],
                "max_length": field[4],
                "decimal_places": field[5],
                "list_values": field[6],
                "empty_selection_list": field[7],
                "notifications": field[8],
                "form_ordering": field[9],
                "view_ordering": field[10],
                "required": field[11],
                "staff_only": field[12],
                "editable": field[13],
                "unlisted": field[14],
                "is_extra_data": field[15],
                "created": field[16],
                "modified": field[17],
                "ticket_form_id": field[18]
            })
    return to_return
