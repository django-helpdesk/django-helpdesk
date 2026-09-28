from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()

PUBLIC_IP = [(None, None, None, None, ("93.184.216.34", 0))]
PRIVATE_IP = [(None, None, None, None, ("127.0.0.1", 0))]
DNS_PATCH = "helpdesk.views.staff.socket.getaddrinfo"
URLOPEN_PATCH = "helpdesk.views.staff.urllib.request.urlopen"


class ImageProxyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="staff", password="pass", is_staff=True
        )
        self.client.login(username="staff", password="pass")
        self.url = reverse("helpdesk:image_proxy")

    def get(self, image_url):
        return self.client.get(self.url, {"url": image_url})

    def mock_upstream(self, content_type="image/png", body=b"\x89PNG", dns=PUBLIC_IP):
        dns_patch = patch(DNS_PATCH, return_value=dns)
        urlopen_patch = patch(URLOPEN_PATCH)
        dns_patch.start()
        mock_urlopen = urlopen_patch.start()
        mock_resp = mock_urlopen.return_value.__enter__.return_value
        mock_resp.headers = {"Content-Type": content_type}
        mock_resp.read.return_value = body
        self.addCleanup(dns_patch.stop)
        self.addCleanup(urlopen_patch.stop)
        return mock_resp

    def test_non_staff_rejected(self):
        User.objects.create_user(username="regular", password="pass", is_staff=False)
        self.client.login(username="regular", password="pass")
        response = self.client.get(
            self.url, {"url": "https://example.com/img.png"}, follow=False
        )
        self.assertIn(response.status_code, (302, 403))

    def test_rejects_post(self):
        response = self.client.post(self.url, {"url": "https://example.com/img.png"})
        self.assertEqual(response.status_code, 405)

    def test_rejects_non_http_url(self):
        response = self.get("file:///etc/passwd")
        self.assertEqual(response.status_code, 400)

    def test_rejects_private_ip(self):
        self.mock_upstream(dns=PRIVATE_IP)
        response = self.get("http://internal.local/img.png")
        self.assertEqual(response.status_code, 400)

    def test_handles_dns_failure(self):
        with patch(DNS_PATCH, side_effect=OSError("DNS lookup failed")):
            response = self.get("https://nonexistent.example/img.png")
        self.assertEqual(response.status_code, 400)

    def test_rejects_non_image_content_type(self):
        self.mock_upstream(content_type="text/html")
        response = self.get("https://example.com/page.html")
        self.assertEqual(response.status_code, 400)

    def test_proxies_valid_image(self):
        image_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        self.mock_upstream(content_type="image/png", body=image_bytes)
        response = self.get("https://example.com/chart.png")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertEqual(response.content, image_bytes)

    def test_rejects_oversized_response(self):
        self.mock_upstream(
            content_type="image/jpeg", body=b"\xff" * (10 * 1024 * 1024 + 1)
        )
        response = self.get("https://example.com/huge.jpg")
        self.assertEqual(response.status_code, 413)

    def test_handles_network_error(self):
        with (
            patch(DNS_PATCH, return_value=PUBLIC_IP),
            patch(URLOPEN_PATCH, side_effect=OSError("Connection refused")),
        ):
            response = self.get("https://example.com/img.png")
        self.assertEqual(response.status_code, 502)
