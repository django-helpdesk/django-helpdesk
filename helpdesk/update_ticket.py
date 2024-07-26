import typing

from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext as _

from helpdesk.lib import safe_template_context
from helpdesk import settings as helpdesk_settings
from helpdesk.lib import process_attachments
from helpdesk.decorators import (
    is_helpdesk_staff,
)
from helpdesk.models import (
    FollowUp,
    Ticket,
    TicketCC,
)
from helpdesk.signals import update_ticket_done

User = get_user_model()

def add_staff_subscription(
    user: User,
    ticket: Ticket
) -> None:
    """Auto subscribe the staff member if that's what the settigs say and the
    user is authenticated and a staff member"""
    if helpdesk_settings.HELPDESK_AUTO_SUBSCRIBE_ON_TICKET_RESPONSE \
            and user.is_authenticated \
            and return_ticketccstring_and_show_subscribe(user, ticket)[1]:
        subscribe_to_ticket_updates(ticket, user)


def return_ticketccstring_and_show_subscribe(user, ticket):
    """used in view_ticket() and followup_edit()"""
    # create the ticketcc_string and check whether current user is already
    # subscribed
    username = user.get_username().upper()
    try:
        useremail = user.email.upper()
    except AttributeError:
        useremail = ""
    strings_to_check = list()
    strings_to_check.append(username)
    strings_to_check.append(useremail)

    ticketcc_string = ''
    all_ticketcc = ticket.ticketcc_set.all()
    counter_all_ticketcc = len(all_ticketcc) - 1
    show_subscribe = True
    for i, ticketcc in enumerate(all_ticketcc):
        ticketcc_this_entry = str(ticketcc.display)
        ticketcc_string += ticketcc_this_entry
        if i < counter_all_ticketcc:
            ticketcc_string += ', '
        if strings_to_check.__contains__(ticketcc_this_entry.upper()):
            show_subscribe = False

    # check whether current user is a submitter or assigned to ticket
    assignedto_username = str(ticket.assigned_to).upper()
    strings_to_check = list()
    if ticket.submitter_email is not None:
        submitter_email = ticket.submitter_email.upper()
        strings_to_check.append(submitter_email)
    strings_to_check.append(assignedto_username)
    if strings_to_check.__contains__(username) or strings_to_check.__contains__(useremail):
        show_subscribe = False

    return ticketcc_string, show_subscribe


def subscribe_to_ticket_updates(ticket, user=None, email=None, can_view=True, can_update=False):

    if ticket is not None:

        queryset = TicketCC.objects.filter(
            ticket=ticket, user=user, email=email)

        # Don't create duplicate entries for subscribers
        if queryset.count() > 0:
            return queryset.first()

        if user is None and len(email) < 5:
            raise ValidationError(
                _('When you add somebody on Cc, you must provide either a User or a valid email. Email: %s' % email)
            )

        return ticket.ticketcc_set.create(
            user=user,
            email=email,
            can_view=can_view,
            can_update=can_update
        )


def get_and_set_ticket_status(
    new_status: int,
    ticket: Ticket,
    follow_up: FollowUp
) -> typing.Tuple[str, int]:
    """Performs comparision on previous status to new status,
    updating the title as required.

    Returns:
        The old status as a display string, old status code string
    """
    old_status_str = ticket.get_status_display()
    old_status = ticket.status
    if new_status != ticket.status:
        ticket.status = new_status
        ticket.save()
        follow_up.new_status = new_status
        if follow_up.title:
            follow_up.title += ' and %s' % ticket.get_status_display()
        else:
            follow_up.title = '%s' % ticket.get_status_display()

    if not follow_up.title:
        if follow_up.comment:
            follow_up.title = _('Comment')
        else:
            follow_up.title = _('Updated')

    follow_up.save()
    return old_status_str, old_status


def update_messages_sent_to_by_public_and_status(
    public: bool,
    ticket: Ticket,
    follow_up: FollowUp,
    context: str,
    messages_sent_to: typing.Set[str],
    files: typing.List[typing.Tuple[str, str]]
) -> Ticket:
    """Sets the status of the ticket"""
    if public and (
        follow_up.comment or (
            follow_up.new_status in (
                Ticket.RESOLVED_STATUS,
                Ticket.CLOSED_STATUS
            )
        )
    ):
        if follow_up.new_status == Ticket.RESOLVED_STATUS:
            template = 'resolved_'
        elif follow_up.new_status == Ticket.CLOSED_STATUS:
            template = 'closed_'
        else:
            template = 'updated_'

        roles = {
            'submitter': (template + 'submitter', context),
            'ticket_cc': (template + 'cc', context),
        }
        if ticket.assigned_to and ticket.assigned_to.usersettings_helpdesk.email_on_ticket_change:
            roles['assigned_to'] = (template + 'cc', context)
        messages_sent_to.update(
            ticket.send(
                roles,
                dont_send_to=messages_sent_to,
                fail_silently=True,
                files=files
            )
        )
    return ticket


def get_template_staff_and_template_cc(
    reassigned, follow_up:  FollowUp
) -> typing.Tuple[str, str]:
    if reassigned:
        template_staff = 'assigned_owner'
    elif follow_up.new_status == Ticket.RESOLVED_STATUS:
        template_staff = 'resolved_owner'
    elif follow_up.new_status == Ticket.CLOSED_STATUS:
        template_staff = 'closed_owner'
    else:
        template_staff = 'updated_owner'
    if reassigned:
        template_cc = 'assigned_cc'
    elif follow_up.new_status == Ticket.RESOLVED_STATUS:
        template_cc = 'resolved_cc'
    elif follow_up.new_status == Ticket.CLOSED_STATUS:
        template_cc = 'closed_cc'
    else:
        template_cc = 'updated_cc'

    return template_staff, template_cc


def update_ticket(
        user,
        ticket,
        title=None,
        comment="",
        files=None,
        public=False,
        owner=-1,
        ticket_title=None,
        priority=-1,
        queue=-1,
        new_status=None,
        time_spent=None,
        due_date=None,
        new_checklists=None,
        message_id=None,
        customfields_form=None,
):
    # We need to allow the 'ticket' and 'queue' contexts to be applied to the
    # comment.
    context = safe_template_context(ticket)
    if title is None:
        title = ticket.title
    if priority == -1:
        priority = ticket.priority
    if queue == -1:
        queue = ticket.queue.id
    if new_status is None:
        new_status = ticket.status
    if new_checklists is None:
        new_checklists = {}

    from django.template import engines
    template_func = engines['django'].from_string
    # this prevents system from trying to render any template tags
    # broken into two stages to prevent changes from first replace being themselves
    # changed by the second replace due to conflicting syntax
    comment = comment.replace(
        '{%', 'X-HELPDESK-COMMENT-VERBATIM').replace('%}', 'X-HELPDESK-COMMENT-ENDVERBATIM')
    comment = comment.replace(
        'X-HELPDESK-COMMENT-VERBATIM', '{% verbatim %}{%'
    ).replace(
        'X-HELPDESK-COMMENT-ENDVERBATIM', '%}{% endverbatim %}'
    )
    # render the neutralized template
    comment = template_func(comment).render(context)

    if owner == -1 and ticket.assigned_to:
        owner = ticket.assigned_to.id

    f = FollowUp(ticket=ticket, date=timezone.now(), comment=comment,
                 time_spent=time_spent, message_id=message_id, title=title)

    if is_helpdesk_staff(user):
        f.user = user

    f.public = public

    reassigned = False

    old_owner = ticket.assigned_to
    if owner != -1:
        if owner != 0 and ((ticket.assigned_to and owner != ticket.assigned_to.id) or not ticket.assigned_to):
            new_user = User.objects.get(id=owner)
            f.title = _('Assigned to %(username)s') % {
                'username': new_user.get_username(),
            }
            ticket.assigned_to = new_user
            reassigned = True
        # user changed owner to 'unassign'
        elif owner == 0 and ticket.assigned_to is not None:
            f.title = _('Unassigned')
            ticket.assigned_to = None

    old_status_str, old_status = get_and_set_ticket_status(new_status, ticket, f)

    files = process_attachments(f, files) if files else []

    if ticket_title and ticket_title != ticket.title:
        c = f.ticketchange_set.create(
            field=_('Title'),
            old_value=ticket.title,
            new_value=ticket_title,
        )
        ticket.title = ticket_title

    if new_status != old_status:
        c = f.ticketchange_set.create(
            field=_('Status'),
            old_value=old_status_str,
            new_value=ticket.get_status_display(),
        )

    if ticket.assigned_to != old_owner:
        c = f.ticketchange_set.create(
            field=_('Owner'),
            old_value=old_owner,
            new_value=ticket.assigned_to,
        )

    if priority != ticket.priority:
        c = f.ticketchange_set.create(
            field=_('Priority'),
            old_value=ticket.priority,
            new_value=priority,
        )
        ticket.priority = priority

    if queue != ticket.queue.id:
        c = f.ticketchange_set.create(
            field=_('Queue'),
            old_value=ticket.queue.id,
            new_value=queue,
        )
        ticket.queue_id = queue

    if due_date != ticket.due_date:
        c = f.ticketchange_set.create(
            field=_('Due on'),
            old_value=ticket.due_date,
            new_value=due_date,
        )
        ticket.due_date = due_date
    
    # save custom fields and ticket changes
    if customfields_form and customfields_form.is_valid():
        customfields_form.save(followup=f)
    
    for checklist in ticket.checklists.all():
        if checklist.id not in new_checklists:
            continue
        new_completed_tasks = new_checklists[checklist.id]
        for task in checklist.tasks.all():
            changed = None

            # Add completion if it was not done yet
            if not task.completion_date and task.id in new_completed_tasks:
                task.completion_date = timezone.now()
                changed = 'completed'
            # Remove it if it was done before
            elif task.completion_date and task.id not in new_completed_tasks:
                task.completion_date = None
                changed = 'uncompleted'

            # Save and add ticket change if task state has changed
            if changed:
                task.save(update_fields=['completion_date'])
                f.ticketchange_set.create(
                    field=f'[{checklist.name}] {task.description}',
                    old_value=_('To do') if changed == 'completed' else _('Completed'),
                    new_value=_('Completed') if changed == 'completed' else _('To do'),
                )

    if new_status in (
        Ticket.RESOLVED_STATUS, Ticket.CLOSED_STATUS
    ) and (
        new_status == Ticket.RESOLVED_STATUS or ticket.resolution is None
    ):
        ticket.resolution = comment

    # ticket might have changed above, so we re-instantiate context with the
    # (possibly) updated ticket.
    context = safe_template_context(ticket)
    context.update(
        resolution=ticket.resolution,
        comment=f.comment,
    )

    messages_sent_to = set()
    try:
        messages_sent_to.add(user.email)
    except AttributeError:
        pass
    ticket = update_messages_sent_to_by_public_and_status(
        public,
        ticket,
        f,
        context,
        messages_sent_to,
        files
    )

    template_staff, template_cc = get_template_staff_and_template_cc(reassigned, f)
    if ticket.assigned_to and (
        ticket.assigned_to.usersettings_helpdesk.email_on_ticket_change
        or (reassigned and ticket.assigned_to.usersettings_helpdesk.email_on_ticket_assign)
    ):
        messages_sent_to.update(ticket.send(
            {'assigned_to': (template_staff, context)},
            dont_send_to=messages_sent_to,
            fail_silently=True,
            files=files,
        ))

    messages_sent_to.update(ticket.send(
        {'ticket_cc': (template_cc, context)},
        dont_send_to=messages_sent_to,
        fail_silently=True,
        files=files,
    ))
    ticket.save()

    # emit signal with followup when the ticket update is done
    # internally used for webhooks
    update_ticket_done.send(sender="update_ticket", followup=f)

    # auto subscribe user if enabled
    add_staff_subscription(user, ticket)
    return f

