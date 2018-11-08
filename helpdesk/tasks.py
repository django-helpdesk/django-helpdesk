from celery import task

from .email import process_email


@task()
def helpdesk_process_email():
    process_email()
