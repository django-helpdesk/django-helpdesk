"""Copy follow-up content without duplicating ticket history or work logs."""

from pathlib import PurePath

from django.db import transaction
from django.utils.translation import gettext as _

from helpdesk.models import FollowUp, FollowUpAttachment


def copy_followup(source, ticket, user, *, public=False):
    """The caller must authorize access to both source and destination tickets."""
    saved_files = []
    try:
        with transaction.atomic():
            title = _("Copied from ticket #%(ticket)s: %(title)s") % {
                "ticket": source.ticket_id,
                "title": source.title,
            }
            copied = FollowUp.objects.create(
                ticket=ticket,
                title=title[:200],
                comment=source.comment,
                user=user,
                public=public,
                email_recipients=[],
            )
            # Saving a follow-up may calculate work time automatically. Copying
            # existing content is not additional work to bill to this ticket.
            FollowUp.objects.filter(pk=copied.pk).update(time_spent=None)
            copied.time_spent = None
            for attachment in source.followupattachment_set.all():
                duplicate = FollowUpAttachment(
                    followup=copied,
                    filename=attachment.filename,
                    mime_type=attachment.mime_type,
                    size=attachment.size,
                )
                with attachment.file.open("rb") as content:
                    duplicate.file.save(
                        PurePath(attachment.file.name).name, content, save=False
                    )
                saved_files.append((duplicate.file.storage, duplicate.file.name))
                duplicate.save()
            return copied
    except Exception:
        # Storage writes are not rolled back by the database transaction.
        for storage, name in saved_files:
            storage.delete(name)
        raise
