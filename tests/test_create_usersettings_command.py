from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from helpdesk.models import UserSettings


class CreateUserSettingsCommandTests(TestCase):
    def test_creates_settings_for_user_without_settings(self):
        user = get_user_model().objects.create_user(username="test_user")

        # New users receive settings automatically through a post_save signal.
        # Remove them to simulate an existing user with missing settings.
        UserSettings.objects.filter(user=user).delete()

        self.assertFalse(UserSettings.objects.filter(user=user).exists())

        call_command("create_usersettings")

        self.assertTrue(UserSettings.objects.filter(user=user).exists())

    def test_preserves_existing_user_settings(self):
        user = get_user_model().objects.create_user(username="existing_user")
        settings = UserSettings.objects.get(user=user)

        settings.tickets_per_page = 50
        settings.save()

        original_id = settings.pk

        call_command("create_usersettings")

        settings.refresh_from_db()

        self.assertEqual(settings.pk, original_id)
        self.assertEqual(settings.tickets_per_page, 50)
        self.assertEqual(UserSettings.objects.filter(user=user).count(), 1)

    def test_creates_settings_for_multiple_users(self):
        User = get_user_model()
        users = [
            User.objects.create_user(username=f"user_{i}")
            for i in range(3)
        ]

        # Simulate missing settings for two users.
        UserSettings.objects.filter(user__in=users[:2]).delete()

        call_command("create_usersettings")

        for user in users:
            self.assertEqual(
                UserSettings.objects.filter(user=user).count(),
                1,
            )

    def test_handles_no_users(self):
        User = get_user_model()

        self.assertEqual(User.objects.count(), 0)

        call_command("create_usersettings")

        self.assertEqual(UserSettings.objects.count(), 0)

    def test_command_is_idempotent(self):
        user = get_user_model().objects.create_user(username="repeat_user")

        # Simulate missing settings.
        UserSettings.objects.filter(user=user).delete()

        call_command("create_usersettings")

        first_settings = UserSettings.objects.get(user=user)
        first_settings_id = first_settings.pk

        # Running the command again should not recreate existing settings.
        call_command("create_usersettings")

        second_settings = UserSettings.objects.get(user=user)

        self.assertEqual(second_settings.pk, first_settings_id)
        self.assertEqual(UserSettings.objects.filter(user=user).count(), 1)
