# -*- coding: utf-8 -*-
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import TestCase
from django.test.client import Client

from helpdesk.models import Queue, Ticket, FormType, KBCategory, KBItem

from seed.lib.superperms.orgs.models import Organization, OrganizationUser, ROLE_VIEWER, ROLE_OWNER, ROLE_MEMBER
from helpdesk.tests.helpers import (get_user, reload_urlconf, User, create_ticket, print_response)
from django.contrib.auth.models import AnonymousUser
from helpdesk.decorators import is_helpdesk_staff
from helpdesk.templatetags.organization_info import organization_info
from helpdesk.templatetags.form_list import form_list
from django.http import HttpRequest, QueryDict

'''
Suite of Test Cases to check Forms, Org access in Helpdesk, and KBCategories are being
properly limited by a users default_organization for staff members, or by the org in the url
for public members.

'''
import logging

logging.disable(logging.CRITICAL)


# TODO Test non-logged in users
class PerOrgMembershipTestCase(TestCase):

    IDENTIFIERS = (1, 2, 3, 4)

    def setUp(self):
        """
        Create three different users with varying levels of permissions, and two different orgs
        user_1 has access to one org as an owner and another as a public member.
        user_2 has access to the other org as an owner and to the first as a public member
        user_3 is a user who isn't logged in

        Create a 4th user, that is paty of 1 that has superuser permissions
        """
        self.client = Client()
        User = get_user_model()
        self.users = {}
        self.name = {1: 'user_1', 2: 'user_2', 3: 'anon', 4: 'superuser'}
        self.login = {1: 'password', 2: 'password', 3: 'ymous', 4: 'superuser'}

        # Create users
        for i in self.IDENTIFIERS:
            if i != 3:
                self.users[i] = get_user(username=self.name[i], password=self.login[i],
                                                    is_superuser=True if i == 4 else False)
            else:
                self.users[i] = AnonymousUser()

        # Create Orgs
        org1 = Organization.objects.create(name='org1')
        org2 = Organization.objects.create(name='org2')
        org3 = Organization.objects.create(name='org3')  # No one is a member of this org

        # Add users to org with different permissions
        #       User 1
        OrganizationUser.objects.create(user=self.users[1], organization=org1, role_level=ROLE_OWNER)
        OrganizationUser.objects.create(user=self.users[1], organization=org2, role_level=ROLE_VIEWER)
        #       User 2
        OrganizationUser.objects.create(user=self.users[2], organization=org1, role_level=ROLE_VIEWER)
        OrganizationUser.objects.create(user=self.users[2], organization=org2, role_level=ROLE_OWNER)
        #       Super User
        OrganizationUser.objects.create(user=self.users[4], organization=org1, role_level=ROLE_MEMBER)

        # Set their default organizations
        self.users[1].default_organization = org1
        self.users[1].save()
        self.users[2].default_organization = org2
        self.users[2].save()
        self.users[4].default_organization = org1
        self.users[4].save()

        # Create Queues
        queue1 = Queue.objects.create(title='Queue 1', slug='queue-1', organization=org1)
        queue2 = Queue.objects.create(title='Queue 2', slug='queue-2', organization=org2)

        # Create Forms
        form1 = FormType.objects.create(organization=org1, public=False)
        form2 = FormType.objects.create(organization=org2, public=True)
        form3 = FormType.objects.create(organization=org3, public=True)

        # Create KBCategories/KBItems
        cat1 = KBCategory.objects.create(title="Test Cat 1", slug="test_cat_1", organization=org1, public=False)
        cat2 = KBCategory.objects.create(title="Test Cat 2", slug="test_cat_2", organization=org1, public=True)
        cat3 = KBCategory.objects.create(title="Test Cat 3", slug="test_cat_3", organization=org2, public=False)
        cat4 = KBCategory.objects.create(title="Test Cat 4", slug="test_cat_4", organization=org3, public=True)

        # Finally, create tickets, 2 for org1 and 4 for org2, where half are unassigned
        create_ticket(**{'queue': queue1, 'ticket_form': form1, 'title': 'Ticket ' + str(0), 'assigned_to': self.users[1]})
        create_ticket(**{'queue': queue1, 'ticket_form': form1, 'title': 'Unassigned Ticket ' + str(1)})
        for i in range(2, 4):
            create_ticket(**{'queue': queue2, 'ticket_form': form2, 'title': 'Ticket ' + str(i), 'assigned_to': self.users[2]})
            for j in range(4,6):
                create_ticket(**{'queue': queue2, 'ticket_form': form2, 'title': 'Unassigned Ticket ' + str(j)})

    def test_org_dropdown_restriction(self):
        """
        Check that a user sees only the orgs in the dropdown menu where they are staff members
        Public members should only have one organization, either their default_org or the org in the url
        """

        # Test Staff Members
        for n in (1, 2, 4):
            self.client.login(username=self.name[n], password=self.login[n])
            org_info = organization_info(self.users[n], reverse('helpdesk:home'))
            self.assertTrue(is_helpdesk_staff(self.users[n]))
            self.assertEqual(
                len(org_info['orgs']),
                1,
                'Dropdown Menu is not being properly limited by organization for Staff members'
            )

        # Test Public Members
        # Swap default_organizations
        self.users[1].default_organization = Organization.objects.get(name='org2')
        self.users[1].save()
        self.users[2].default_organization = Organization.objects.get(name='org1')
        self.users[2].save()
        self.users[4].default_organization = Organization.objects.get(name='org2')
        self.users[4].save()

        for n in (1, 2, 4):
            self.client.login(username=self.name[n], password=self.login[n])
            org_info = organization_info(self.users[n], reverse('helpdesk:home'))
            self.assertFalse(is_helpdesk_staff(self.users[n]))
            self.assertTrue('orgs' not in org_info.keys())
            self.assertEqual(
                org_info['default_org'],
                Organization.objects.get(name='org1' if n == 2 else 'org2'),
                'Dropdown Menu is not being properly limited by organization for Public members'
            )

        # Test Public Members with Url in org
        for n in (1, 2, 4):
            self.client.login(username=self.name[n], password=self.login[n])
            org_info = organization_info(self.users[n], reverse('helpdesk:home') + '?org=org3')
            self.assertFalse(is_helpdesk_staff(self.users[n]))
            self.assertTrue('orgs' not in org_info.keys())
            self.assertEqual(
                org_info['default_org'],
                Organization.objects.get(name='org3'),
                'Public members are not being properly redirected when an org is in the url.'
            )

        # Reset default_org fields
        self.users[1].default_organization = Organization.objects.get(name='org1')
        self.users[1].save()
        self.users[2].default_organization = Organization.objects.get(name='org2')
        self.users[2].save()
        self.users[4].default_organization = Organization.objects.get(name='org1')
        self.users[4].save()

    def test_form_list_restriction(self):
        """
        Check that a user sees only the forms sidebar list that belong to their current Organization
        Public members should only have one organization, either their default_org or the org in the url
        """
        # Test Staff Members
        for n in (1, 2, 4):
            self.client.login(username=self.name[n], password=self.login[n])

            request = HttpRequest()
            request.method = 'GET'
            request.query_params = QueryDict()
            request.user = self.users[n]
            request.data = {}
            forms = form_list(self.users[n], request)

            self.assertTrue(is_helpdesk_staff(self.users[n]))
            self.assertEqual(
                len(forms),
                1,
                'Form List is not being properly limited by organization for Staff members'
            )
            self.assertEqual(
                forms.first()['organization__name'],
                'org1' if n != 2 else 'org2',
                'Incorrect form in form list for Staff members'
            )

        # Test Public Members
        # Swap default_organizations
        self.users[1].default_organization = Organization.objects.get(name='org2')
        self.users[1].save()
        self.users[2].default_organization = Organization.objects.get(name='org1')
        self.users[2].save()
        self.users[4].default_organization = Organization.objects.get(name='org2')
        self.users[4].save()

        # Only form 2 is public

        for n in (1, 2, 4):
            self.client.login(username=self.name[n], password=self.login[n])

            request = HttpRequest()
            request.method = 'GET'
            request.query_params = QueryDict()
            request.user = self.users[n]
            request.data = {}

            forms = form_list(self.users[n], request)
            self.assertFalse(is_helpdesk_staff(self.users[n]))
            self.assertEqual(
                len(forms),
                1 if n != 2 else 0,
                'Form List is not being properly limited by organization for Public members'
            )
            self.assertEqual(
                forms.first()['organization__name'] if n != 2 else 'NA',
                'org2' if n != 2 else 'NA',
                'Incorrect form in form list for Public members'
            )

        # Test Public Members with Url in org
        for n in (1, 2, 4):
            self.client.login(username=self.name[n], password=self.login[n])

            request = HttpRequest()
            request.method = 'GET'
            request.GET = QueryDict('org=org3')
            request.user = self.users[n]
            print(request.GET)
            forms = form_list(self.users[n], request)
            self.assertFalse(is_helpdesk_staff(self.users[n]))
            self.assertEqual(
                len(forms),
                1,
                'Form List is not being properly limited by organization in url for Public members in '
            )
            self.assertEqual(
                forms.first()['organization__name'],
                'org3',
                'Incorrect form in form list for Public members with org in url'
            )

        # Reset default_org fields
        self.users[1].default_organization = Organization.objects.get(name='org1')
        self.users[1].save()
        self.users[2].default_organization = Organization.objects.get(name='org2')
        self.users[2].save()
        self.users[4].default_organization = Organization.objects.get(name='org1')
        self.users[4].save()

    def test_kb_category_restriction(self):
        """
        Check that index/kb pages show the kb categories belonging to a users organization by staff status and by
        public status
        """
        # Staff members, user 1 has two, user 2 has one, and user 4 has 4 since they are superuser
        for n in (1, 2, 4):
            self.client.login(username=self.name[n], password=self.login[n])
            response = self.client.get(reverse('helpdesk:home'))
            self.assertTrue(is_helpdesk_staff(self.users[n]))
            self.assertEqual(
                len(response.context['kb_categories']),
                2 if n == 1 else 1 if n == 2 else 4,
                'KB Categories were not properly limited by Organization'
            )

        # Test Public Members, user 1 has zero since org2 has no public, user 2 has 1 since org1 has 1 public, superuser
        # still sees 4
        # Swap default_organizations
        self.users[1].default_organization = Organization.objects.get(name='org2')
        self.users[1].save()
        self.users[2].default_organization = Organization.objects.get(name='org1')
        self.users[2].save()
        self.users[4].default_organization = Organization.objects.get(name='org2')
        self.users[4].save()

        for n in (1, 2, 4):
            self.client.login(username=self.name[n], password=self.login[n])
            response = self.client.get(reverse('helpdesk:home'))
            self.assertFalse(is_helpdesk_staff(self.users[n]))
            self.assertEqual(
                len(response.context['kb_categories']),
                1 if n == 2 else 0 if n == 1 else 4,
                'KB Categories were not properly limited by Organization for Public members'
            )

        # Test Org in Url
        for n in (1, 2, 4):
            self.client.login(username=self.name[n], password=self.login[n])
            response = self.client.get(reverse('helpdesk:home') + '?org=org3')
            self.assertFalse(is_helpdesk_staff(self.users[n]))
            self.assertEqual(
                len(response.context['kb_categories']),
                1 if n != 4 else 4,
                'KB Categories were not properly limited by Organization in url for Public members'
            )

        # Reset default_org fields
        self.users[1].default_organization = Organization.objects.get(name='org1')
        self.users[1].save()
        self.users[2].default_organization = Organization.objects.get(name='org2')
        self.users[2].save()
        self.users[4].default_organization = Organization.objects.get(name='org1')
        self.users[4].save()









