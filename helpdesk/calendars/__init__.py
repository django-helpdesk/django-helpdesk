#!/usr/bin/python

from helpdesk import settings

calendar = __import__('helpdesk.calendars.%s' % settings.HELPDESK_CALENDAR, fromlist=['submod'])  
update_calendar = calendar.update_calendar

