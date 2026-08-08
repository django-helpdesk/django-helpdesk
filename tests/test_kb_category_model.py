from django.test import TestCase
from django.urls import reverse

from helpdesk.models import KBCategory


class KBCategoryModelTests(TestCase):
    """
    Test suite for the KB Category model.
    """

    @classmethod
    def setUpTestData(cls):
        cls.kb_category = KBCategory.objects.create(
            name="Accounts",
            title="Customer Accounts",
            slug="customer-accounts",
            description="Account access related problems",
        )

    def test_str_representation(self):
        self.assertEqual(str(self.kb_category), self.kb_category.name)

    def test_absolute_url(self):
        actual = self.kb_category.get_absolute_url()
        expected = reverse(
            "helpdesk:kb_category", kwargs={"slug": self.kb_category.slug}
        )
        self.assertEqual(actual, expected)

    def test_verbose_names(self):
        meta = self.kb_category._meta
        self.assertEqual(meta.verbose_name, "Knowledge base category")
        self.assertEqual(meta.verbose_name_plural, "Knowledge base categories")
