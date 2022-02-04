# -*- coding: utf-8 -*-
from django.test import TestCase
from django.test.client import Client
from helpdesk.models import Queue, Ticket, FormType, KBCategory, KBItem
from seed.lib.superperms.orgs.models import Organization, get_helpdesk_organizations


'''
Suite of Test Cases to check behavior of multiple Organizations which may share the same Helpdesk and to check the behavior
of changing an Organization's Helpdesk Organization.

'''
import logging

logging.disable(logging.CRITICAL)


class MultipleOrganizationTestCase(TestCase):
    IDENTIFIERS = ('A', 'B', 'C')

    def setUp(self):
        """
        Create three different Organizations that each has a FormType, Queue, and KBCategory
        """
        self.client = Client()

        for i in self.IDENTIFIERS:
            org = Organization.objects.create(name='Org ' + i)
            Queue.objects.create(title='Queue for Org ' + i, slug='queue-org-' + i, organization=org)
            FormType.objects.create(organization=org)
            KBCategory.objects.create(title='KBCat for Org ' + i, slug='kbcat-org-' + i, organization=org)

    def test_helpdesk_org_change_from_self(self):
        """
        Changing Helpdesk Organization from itself to another Organization should also change associated Models.
        If the Helpdesk Organization field changes back, it should not affect the associated models
        """
        # Check that their Helpdesk Org is themselves
        for id in self.IDENTIFIERS:
            org = Organization.objects.get(name='Org ' + id)
            self.assertEqual(org,
                             org.helpdesk_organization,
                             'Organization post_save method is not properly setting an Orgs Helpdesk_Org to itself.')

        # Set Org B's Helpdesk Org to be Org A
        org_a = Organization.objects.get(name='Org A')
        org_b = Organization.objects.get(name='Org B')
        org_b.helpdesk_organization = org_a
        org_b.save()

        # Check that Org A now has 2 each of Queues, Forms, and KBCats.
        self.assertEqual(Queue.objects.filter(organization=org_a).count(),
                         2,
                         'Org pre_save method did not properly swap Queues Org when changing Helpdesk Org')
        self.assertEqual(FormType.objects.filter(organization=org_a).count(),
                         2,
                         'Org pre_save method did not properly swap Forms Org when changing Helpdesk Org')
        self.assertEqual(KBCategory.objects.filter(organization=org_a).count(),
                         2,
                         'Org pre_save method did not properly swap KBCats Org when changing Helpdesk Org')
        # Check that Org B has 0
        self.assertEqual(Queue.objects.filter(organization=org_b).count(),
                         0,
                         'Org pre_save method did not properly swap Queues Org when changing Helpdesk Org')
        self.assertEqual(FormType.objects.filter(organization=org_b).count(),
                         0,
                         'Org pre_save method did not properly swap Forms Org when changing Helpdesk Org')
        self.assertEqual(KBCategory.objects.filter(organization=org_b).count(),
                         0,
                         'Org pre_save method did not properly swap KBCats Org when changing Helpdesk Org')

        # Swapping Org B's Helpdesk Org back to itself or to Org C should have no affect on the models
        org_b.helpdesk_organization = org_b
        org_b.save()
        # Check that Org B still has 0 and that Org A still has 2 of each
        self.assertEqual(Queue.objects.filter(organization=org_a).count(),
                         2,
                         'Org pre_save method swapped Queues Org when it should not have for an already swapped org')
        self.assertEqual(FormType.objects.filter(organization=org_a).count(),
                         2,
                         'Org pre_save method swapped Queues Org when it should not have for an already swapped org')
        self.assertEqual(KBCategory.objects.filter(organization=org_a).count(),
                         2,
                         'Org pre_save method swapped KBCats Org when it should not have for an already swapped org')
        self.assertEqual(Queue.objects.filter(organization=org_b).count(),
                         0,
                         'Org pre_save method swapped Queues Org when it should not have for an already swapped org')
        self.assertEqual(FormType.objects.filter(organization=org_b).count(),
                         0,
                         'Org pre_save method swapped Queues Org when it should not have for an already swapped org')
        self.assertEqual(KBCategory.objects.filter(organization=org_b).count(),
                         0,
                         'Org pre_save method swapped KBCats Org when it should not have for an already swapped org')

    def test_get_helpdesk_organizations(self):
        """
        Test get_helpdesk_organizations function.
        Case: All Orgs are tied to themselves -> returns each Org for a total count of 3
        Case: Two Orgs share a Helpdesk Org and one Org is tied to itself -> returns 2 Orgs
        """
        list_of_helpdesk_orgs = get_helpdesk_organizations()
        self.assertEqual(len(list_of_helpdesk_orgs),
                         3,
                         'get_helpdesk_org did not properly filter by the list of Helpdesk Orgs')
        # Swap Org B's Helpdesk Org to Org A and check that we now get 2 consisting of [Org A, Org C]
        org_a = Organization.objects.get(name='Org A')
        org_b = Organization.objects.get(name='Org B')
        org_c = Organization.objects.get(name='Org C')

        org_b.helpdesk_organization = org_a
        org_b.save()

        list_of_helpdesk_orgs = get_helpdesk_organizations()
        self.assertEqual(len(list_of_helpdesk_orgs),
                         2,
                         'get_helpdesk_org did not properly filter after changing an orgs helpdesk_org')
        self.assertEqual(list(list_of_helpdesk_orgs),
                         [org_a, org_c],
                         'get_helpdesk_org returned the wrong orgs')
