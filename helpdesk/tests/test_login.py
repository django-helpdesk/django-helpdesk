from django.test import TestCase, override_settings
from django.urls import reverse


class TestLoginRedirect(TestCase):

    @override_settings(LOGIN_URL='/custom/login/')
    def test_custom_login_view_with_url(self):
        """Test login redirect when LOGIN_URL is set to custom url"""
        response = self.client.get(reverse('helpdesk:login'))
        # We expect that that helpdesk:home url is passed as next parameter in
        # the redirect url, so that the custom login can redirect the browser
        # back to helpdesk after the login.
        home_url = reverse('helpdesk:home')
        expected = '/custom/login/?next={}'.format(home_url)
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    @override_settings(LOGIN_URL='/custom/login/')
    def test_custom_login_next_param(self):
        """Test that the next url parameter is correctly relayed to custom login"""
        next_param = "/redirect/back"
        url = reverse('helpdesk:login') + "?next=" + next_param
        response = self.client.get(url)
        expected = '/custom/login/?next={}'.format(next_param)
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    @override_settings(LOGIN_URL='helpdesk:login', SITE_ID=1)
    def test_default_login_view(self):
        """Test that default login is used when LOGIN_URL is helpdesk:login"""
        response = self.client.get(reverse('helpdesk:login'))
        self.assertTemplateUsed(response, 'helpdesk/registration/login.html')

    @override_settings(LOGIN_URL=None, SITE_ID=1)
    def test_login_url_none(self):
        """Test that default login is used when LOGIN_URL is None"""
        response = self.client.get(reverse('helpdesk:login'))
        self.assertTemplateUsed(response, 'helpdesk/registration/login.html')

    @override_settings(LOGIN_URL='admin:login', SITE_ID=1)
    def test_custom_login_view_with_name(self):
        """Test that LOGIN_URL can be a view name"""
        response = self.client.get(reverse('helpdesk:login'))
        home_url = reverse('helpdesk:home')
        expected = reverse('admin:login') + "?next=" + home_url
        self.assertRedirects(response, expected)
