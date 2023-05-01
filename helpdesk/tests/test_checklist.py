from datetime import datetime
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from helpdesk.models import Checklist, ChecklistTask, ChecklistTemplate, Queue, Ticket


class TicketChecklistTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = get_user_model().objects.create_user('User', password='pass')
        user.is_staff = True
        user.save()
        cls.user = user

    def setUp(self) -> None:
        self.client.login(username='User', password='pass')

        self.ticket = Ticket.objects.create(queue=Queue.objects.create(title='Queue', slug='queue'))

    def test_create_checklist(self):
        self.assertEqual(self.ticket.checklists.count(), 0)
        checklist_name = 'test empty checklist'

        response = self.client.post(
            reverse('helpdesk:view', kwargs={'ticket_id': self.ticket.id}),
            data={'name': checklist_name},
            follow=True
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'helpdesk/checklist_form.html')
        self.assertContains(response, checklist_name)

        self.assertEqual(self.ticket.checklists.count(), 1)

    def test_create_checklist_from_template(self):
        self.assertEqual(self.ticket.checklists.count(), 0)
        checklist_name = 'test checklist from template'

        checklist_template = ChecklistTemplate.objects.create(
            name='Test template',
            task_list=['first', 'second', 'last']
        )

        response = self.client.post(
            reverse('helpdesk:view', kwargs={'ticket_id': self.ticket.id}),
            data={'name': checklist_name, 'checklist_template': checklist_template.id},
            follow=True
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'helpdesk/checklist_form.html')
        self.assertContains(response, checklist_name)

        self.assertEqual(self.ticket.checklists.count(), 1)
        created_checklist = self.ticket.checklists.get()
        self.assertEqual(created_checklist.tasks.count(), 3)
        self.assertEqual(created_checklist.tasks.all()[0].description, 'first')
        self.assertEqual(created_checklist.tasks.all()[1].description, 'second')
        self.assertEqual(created_checklist.tasks.all()[2].description, 'last')

    def test_edit_checklist(self):
        checklist = self.ticket.checklists.create(name='Test checklist')
        first_task = checklist.tasks.create(description='First task', position=1)
        checklist.tasks.create(description='To delete task', position=2)

        url = reverse('helpdesk:edit_ticket_checklist', kwargs={
            'ticket_id': self.ticket.id,
            'checklist_id': checklist.id,
        })

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'helpdesk/checklist_form.html')
        self.assertContains(response, 'Test checklist')
        self.assertContains(response, 'First task')
        self.assertContains(response, 'To delete task')

        response = self.client.post(
            url,
            data={
                'name': 'New name',
                'tasks-TOTAL_FORMS': 3,
                'tasks-INITIAL_FORMS': 2,
                'tasks-0-id': '1',
                'tasks-0-description': 'First task edited',
                'tasks-0-position': '2',
                'tasks-1-id': '2',
                'tasks-1-description': 'To delete task',
                'tasks-1-DELETE': 'on',
                'tasks-1-position': '2',
                'tasks-2-description': 'New first task',
                'tasks-2-position': '1',
            },
            follow=True
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'helpdesk/ticket.html')

        checklist.refresh_from_db()
        self.assertEqual(checklist.name, 'New name')
        self.assertEqual(checklist.tasks.count(), 2)
        first_task.refresh_from_db()
        self.assertEqual(first_task.description, 'First task edited')
        self.assertEqual(checklist.tasks.all()[0].description, 'New first task')
        self.assertEqual(checklist.tasks.all()[1].description, 'First task edited')

    def test_delete_checklist(self):
        checklist = self.ticket.checklists.create(name='Test checklist')
        checklist.tasks.create(description='First task', position=1)
        self.assertEqual(Checklist.objects.count(), 1)
        self.assertEqual(ChecklistTask.objects.count(), 1)

        response = self.client.post(
            reverse(
                'helpdesk:delete_ticket_checklist',
                kwargs={'ticket_id': self.ticket.id, 'checklist_id': checklist.id}
            ),
            follow=True
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'helpdesk/ticket.html')

        self.assertEqual(Checklist.objects.count(), 0)
        self.assertEqual(ChecklistTask.objects.count(), 0)

    def test_mark_task_as_done(self):
        checklist = self.ticket.checklists.create(name='Test checklist')
        task = checklist.tasks.create(description='Task', position=1)
        self.assertIsNone(task.completion_date)

        self.assertEqual(self.ticket.followup_set.count(), 0)

        response = self.client.post(
            reverse('helpdesk:update', kwargs={'ticket_id': self.ticket.id}),
            data={
                f'checklist-{checklist.id}': task.id
            },
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'helpdesk/ticket.html')

        self.assertEqual(self.ticket.followup_set.count(), 1)
        followup = self.ticket.followup_set.get()
        self.assertEqual(followup.ticketchange_set.count(), 1)
        self.assertEqual(followup.ticketchange_set.get().old_value, 'To do')
        self.assertEqual(followup.ticketchange_set.get().new_value, 'Completed')

        task.refresh_from_db()
        self.assertIsNotNone(task.completion_date)

    def test_mark_task_as_undone(self):
        checklist = self.ticket.checklists.create(name='Test checklist')
        task = checklist.tasks.create(description='Task', position=1, completion_date=datetime(2023, 5, 1))
        self.assertIsNotNone(task.completion_date)

        self.assertEqual(self.ticket.followup_set.count(), 0)

        response = self.client.post(
            reverse('helpdesk:update', kwargs={'ticket_id': self.ticket.id}),
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'helpdesk/ticket.html')

        self.assertEqual(self.ticket.followup_set.count(), 1)
        followup = self.ticket.followup_set.get()
        self.assertEqual(followup.ticketchange_set.count(), 1)
        self.assertEqual(followup.ticketchange_set.get().old_value, 'Completed')
        self.assertEqual(followup.ticketchange_set.get().new_value, 'To do')

        task.refresh_from_db()
        self.assertIsNone(task.completion_date)

    def test_display_checklist_templates(self):
        ChecklistTemplate.objects.create(
            name='Test checklist template',
            task_list=['first', 'second', 'third']
        )

        response = self.client.get(reverse('helpdesk:checklist_templates'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'helpdesk/checklist_templates.html')
        self.assertContains(response, 'Test checklist template')
        self.assertContains(response, '3 tasks')

    def test_create_checklist_template(self):
        self.assertEqual(ChecklistTemplate.objects.count(), 0)

        response = self.client.post(
            reverse('helpdesk:checklist_templates'),
            data={
                'name': 'Test checklist template',
                'task_list': '["first", "second", "third"]'
            },
            follow=True
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'helpdesk/checklist_templates.html')

        self.assertEqual(ChecklistTemplate.objects.count(), 1)
        checklist_template = ChecklistTemplate.objects.get()
        self.assertEqual(checklist_template.name, 'Test checklist template')
        self.assertEqual(checklist_template.task_list, ['first', 'second', 'third'])

    def test_edit_checklist_template(self):
        checklist_template = ChecklistTemplate.objects.create(
            name='Test checklist template',
            task_list=['first', 'second', 'third']
        )
        self.assertEqual(ChecklistTemplate.objects.count(), 1)

        response = self.client.post(
            reverse('helpdesk:edit_checklist_template', kwargs={'checklist_template_id': checklist_template.id}),
            data={
                'name': 'New checklist template',
                'task_list': '["new first", "second", "third", "last"]'
            },
            follow=True
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'helpdesk/checklist_templates.html')

        self.assertEqual(ChecklistTemplate.objects.count(), 1)
        checklist_template.refresh_from_db()
        self.assertEqual(checklist_template.name, 'New checklist template')
        self.assertEqual(checklist_template.task_list, ['new first', 'second', 'third', 'last'])

    def test_delete_checklist_template(self):
        checklist_template = ChecklistTemplate.objects.create(
            name='Test checklist template',
            task_list=['first', 'second', 'third']
        )
        self.assertEqual(ChecklistTemplate.objects.count(), 1)

        response = self.client.post(
            reverse('helpdesk:delete_checklist_template', kwargs={'checklist_template_id': checklist_template.id}),
            follow=True
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'helpdesk/checklist_templates.html')

        self.assertEqual(ChecklistTemplate.objects.count(), 0)
