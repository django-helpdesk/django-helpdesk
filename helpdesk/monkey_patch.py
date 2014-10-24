"""
django-helpdesk - A Django powered ticket tracker for small enterprise.

(c) Copyright 2008 Jutda. All Rights Reserved. See LICENSE for details.

monkey_patch.py - Monkey Patch the User model for older versions of
Django that don't support USERNAME_FIELD and get_username
"""

from django.contrib.auth import get_user_model
User = get_user_model()
if not hasattr(User, "USERNAME_FIELD"):
	User.add_to_class("USERNAME_FIELD", "username")
if not hasattr(User, "get_username"):
	User.add_to_class("get_username", lambda self: getattr(self, self.USERNAME_FIELD))
