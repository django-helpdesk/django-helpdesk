#!/usr/bin/python
#
# Copyright 2012 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Code obtained & modified from https://raw.githubusercontent.com/google/gmail-oauth2-tools/master/python/oauth2.py
# https://github.com/google/gmail-oauth2-tools/wiki/OAuth2DotPyRunThrough

# BEAM - removed unused imports
import base64
import json
from urllib.request import urlopen
from urllib.parse import urlencode
from django.conf import settings
import msal

# The URL root for accessing Google Accounts.
GOOGLE_ACCOUNTS_BASE_URL = 'https://accounts.google.com'


def accounts_url(command):
    """Generates the Google Accounts URL.

  Args:
    command: The command to execute.

  Returns:
    A URL for the given command.
  """
    return '%s/%s' % (GOOGLE_ACCOUNTS_BASE_URL, command)


def refresh_gmail_tokens(refresh_token):  # BEAM - removed client_id and client_secret args
    # Copyright 2012 Google Inc.
    #
    # Licensed under the Apache License, Version 2.0 (the "License");
    # you may not use this file except in compliance with the License.
    # You may obtain a copy of the License at
    #
    # http://www.apache.org/licenses/LICENSE-2.0
    #
    # Unless required by applicable law or agreed to in writing, software
    # distributed under the License is distributed on an "AS IS" BASIS,
    # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    # See the License for the specific language governing permissions and
    # limitations under the License.

    """Obtains a new token given a refresh token.

      See https://developers.google.com/accounts/docs/OAuth2InstalledApp#refresh

      Args:
        client_id: Client ID obtained by registering your app.
        client_secret: Client secret obtained by registering your app.
        refresh_token: A previously-obtained refresh token.
      Returns:
        The decoded response from the Google Accounts server, as a dict. Expected
        fields include 'access_token', 'expires_in', and 'refresh_token'.
    """
    try:
        CLIENT_ID = settings.GMAIL_OAUTH2_CLIENT_ID  # BEAM
        CLIENT_SECRET = settings.GMAIL_OAUTH2_CLIENT_SECRET  # BEAM
    except AttributeError:
        return False
    params = {'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET, 'refresh_token': refresh_token,  # BEAM - swapped out client_id and client_secret vars
              'grant_type': 'refresh_token'}
    request_url = accounts_url('o/oauth2/token')

    response = urlopen(request_url, urlencode(params).encode('utf-8')).read()
    return json.loads(response)


def refresh_microsoft_tokens(importer):
    outlook_config = {
        "scope": ["https://outlook.office365.com/.default"],
        "authority": f"https://login.microsoftonline.com/{importer.tenant}",
        "client_id": f"{importer.client}",
        "secret": f"{importer.secret}",
    }
    app = msal.ConfidentialClientApplication(
        outlook_config["client_id"],
        authority=outlook_config["authority"],
        client_credential=outlook_config["secret"],
    )
    access_token = app.acquire_token_silent(outlook_config["scope"], account=None)
    if not access_token:
        access_token = app.acquire_token_for_client(scopes=outlook_config["scope"])

    if 'access_token' in access_token:
        return access_token
    else:
        return None


def generate_oauth2_string(user, token):
    auth_string = f"user={user}\1auth=Bearer {token}\1\1"
    return auth_string

"""
def generate_oauth2_string(username, access_token, base64_encode=True):
    Generates an IMAP OAuth2 authentication string.

  See https://developers.google.com/google-apps/gmail/oauth2_overview

  Args:
    username: the username (email address) of the account to authenticate
    access_token: An OAuth2 access token.
    base64_encode: Whether to base64-encode the output.

  Returns:
    The SASL argument for the OAuth2 mechanism.
  
    auth_string = 'user=%s\1auth=Bearer %s\1\1' % (username, access_token)
    auth_string = auth_string.encode('utf-8')
    if base64_encode:
        auth_string = base64.b64encode(auth_string)
    return auth_string.decode('utf-8')
"""

