#!/usr/bin/python
"""
Update the logged in user's calendar on task due-date changes.

Currently depends on authentication via the django-social-auth app.
"""

from datetime import datetime

import gdata.calendar.data
import gdata.calendar.client
import gdata.acl.data
import atom.data
import gdata.gauth
import cgi

import settings


def update_calendar(request, search_date=None):
    # TODO: abstract this so different oauth mechanisms can be used?
    authorized_user = request.user.social_auth.get(provider='google-oauth')
    oauth_values = cgi.parse_qs(authorized_user.extra_data['access_token'])

    # perform auth and insert/ update event
    calendar_client = gdata.calendar.client.CalendarClient()
    calendar_client.auth_token = gdata.gauth.OAuthHmacToken(
            settings.GOOGLE_CONSUMER_KEY,
            settings.GOOGLE_CONSUMER_SECRET,
            oauth_values['oauth_token'][0],
            oauth_values['oauth_token_secret'][0],
            gdata.gauth.ACCESS_TOKEN)


    year = int(request.POST['due_date_year'])
    month = int(request.POST['due_date_month'])
    day = int(request.POST['due_date_day'])
    date = datetime(year, month, day)
    when = gdata.calendar.data.When(start=date.strftime('%Y-%m-%d'), end=date.replace(day=date.day + 1).strftime('%Y-%m-%d'))
   
    if search_date:
        # update
        # TODO: what if user wants to change the title?  may need to store event id...
        query = gdata.calendar.client.CalendarEventQuery(text_query=request.POST['title'])
        query.start_min = search_date.strftime('%Y-%m-%d') 
        query.start_max = search_date.replace(day=search_date.day + 1).strftime('%Y-%m-%d') 
        #import ipdb; ipdb.set_trace()
        feed = calendar_client.GetCalendarEventFeed(q=query)
        try:
            event = feed.entry[0]
        except Exception, e:
            raise ValueError("Didn't get the right number of events to update: %s" % e)
        event.when[0] = when 
        updated_event = calendar_client.Update(event)
    else:
        # insert
        event = gdata.calendar.data.CalendarEventEntry()
        event.title = atom.data.Title(text=request.POST['title'])
        event.content = atom.data.Content(text=request.POST['body'])
        # make ticket events all day events
        event.when.append(when)
        new_event = calendar_client.InsertEvent(event)

    



