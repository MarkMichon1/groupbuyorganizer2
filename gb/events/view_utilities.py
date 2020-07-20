from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect

from events.models import Event, EventMembership


def event_auth_checkpoint(event_id, request, organizer=False):
    event = get_object_or_404(Event, pk=event_id)
    membership = None
    try:
        membership = EventMembership.objects.get(user=request.user, event=event)
    except EventMembership.DoesNotExist:
        messages.info(request, f"You don't have access to this event.  Please have an event organizer add you.")
        return event, membership, False
    if organizer:
        if not membership.is_organizer:
            messages.info(request, f"You must be an organizer to have access to this view.")
            return event, membership, False
    return event, membership, True