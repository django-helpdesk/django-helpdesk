from celery import shared_task

from .email import process_email


@shared_task
def helpdesk_process_email():
    process_email()
