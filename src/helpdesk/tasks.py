from .email import process_email
from celery import shared_task


@shared_task
def helpdesk_process_email():
    process_email()
