from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from events.forms import AddUserForm, QuantitySelectForm, CommentCreateForm, ItemForm, CreateItemYoutubeVideoForm, \
    EventCreateForm, EventSettingsForm, UserSelectForm
from events.models import CaseBuy, CasePieceCommit, CaseSplit, Event, EventComment, EventMembership, Item, ItemComment,\
    ItemYoutubeVideo
from events.view_utilities import event_auth_checkpoint, validate_and_categorize_youtube_link
from general.models import Instance
from users.models import User


@login_required
def create_event(request):
    if request.method == 'POST':
        form = EventCreateForm(request.POST, target_user=request.user)
        if form.is_valid():
            title = form.cleaned_data['name']
            description = form.cleaned_data['description']
            event = Event(name=title, description=description, created_by=request.user)
            event.save()
            membership = EventMembership(user=request.user, event=event, is_organizer=True, is_creator=True)
            membership.save()
            messages.success(request, f"Event successfully created!  Click your event Event Settings button in the "
                                      f"organizer toolbar to add more members.")
            return redirect('general-home')
    else:
        context = {
            'form' : EventCreateForm(target_user=request.user),
            'title' : 'New Event'
        }
        return render(request, 'events/create_event.html', context=context)

@login_required
def event(request, event_id):
    # Note- until I find a proper way to deal with this, these three lines will be in all event views requiring auth.
    event, membership, is_valid = event_auth_checkpoint(event_id=event_id, request=request)
    if is_valid == False:
        return redirect('general-home')
    event_data = event.generate_event_pages_contents(page_type='event', membership=membership)

    if request.method == 'POST':
        form = ItemForm(request.POST)
        if form.is_valid():
            new_item = form.save(commit=False)
            new_item.added_by = membership
            new_item.event = event
            new_item.save()
            messages.success(request, "Item added!")
            return redirect('events-event', event_id=event.id)
    else:
        context = {
            'event_data': event_data,
            'title': event.name,
            'event': event,
            'form': ItemForm(),
            'membership': membership
        }
        return render(request, 'events/event.html', context=context)


@login_required
def event_settings(request, event_id):
    event, membership, is_valid = event_auth_checkpoint(event_id=event_id, request=request, organizer=True)
    if is_valid == False:
        return redirect('general-home')
    if request.method == 'POST':
        form = EventSettingsForm(request.POST, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, "Event updated!")
            return redirect('events-settings', event_id=event.id)
    else:
        form = EventSettingsForm(initial={'name':event.name,
                                 'description': event.description,
                                 'is_locked':event.is_locked,
                                 'users_full_event_visibility':event.users_full_event_visibility,
                                 'extra_charges': event.extra_charges
                                 })
        context = {
            'event': event,
            'form': form,
            'title': 'Event Settings'
        }
        return render(request, 'events/event_settings.html', context=context)


@login_required
def close_event(request, event_id):
    event, membership, is_valid = event_auth_checkpoint(event_id=event_id, request=request, organizer=True)
    if is_valid == False:
        return redirect('general-home')
    event.is_locked = True
    event.is_closed = True
    event.save()
    instance = Instance.objects.get()
    instance.total_cases_reserved += event.get_total_cases()
    instance.save()
    messages.success(request, "Event closed!")
    return redirect('events-event', event_id=event.id)


@login_required
def event_toggle_lock(request, event_id):
    event, membership, is_valid = event_auth_checkpoint(event_id=event_id, request=request, organizer=True)
    if is_valid == False:
        return redirect('general-home')


@login_required
def event_toggle_close(request, event_id):
    event, membership, is_valid = event_auth_checkpoint(event_id=event_id, request=request, organizer=True)
    if is_valid == False:
        return redirect('general-home')


@login_required
def leave_event(request, event_id):
    event, membership, is_valid = event_auth_checkpoint(event_id=event_id, request=request)
    if is_valid == False:
        return redirect('general-home')
    for commit in membership.split_commits:
        commit.case_split.is_complete = False
        commit.case_split.save()
    membership.delete()
    messages.success(request, 'You have left the event!')
    return redirect('general-home')


@login_required
def delete_event(request, event_id):
    event, membership, is_valid = event_auth_checkpoint(event_id=event_id, request=request, organizer=True)
    if is_valid == False:
        return redirect('general-home')
    if membership.is_creator or request.user.is_staff:
        name = event.name
        event.delete()
        messages.success(request, f"Poof!  Event '{name}' has been deleted.")
        return redirect('general-home')
    else:
        messages.warning(request, 'Access denied.')
        return redirect('general-home')


@login_required
def item(request, event_id, item_id):
    event, membership, is_valid = event_auth_checkpoint(event_id=event_id, request=request)
    if is_valid == False:
        return redirect('general-home')
    item = get_object_or_404(Item, pk=item_id)

    try:
        case_buy = CaseBuy.objects.filter(membership=membership).filter(item=item).get()
        initial_qty = case_buy.quantity
    except:
        case_buy = None
        initial_qty = 0

    if 'comment_submit' in request.POST:
        comment_form = CommentCreateForm(request.POST)
        if comment_form.is_valid():
            comment = comment_form.cleaned_data['comment']
            item_comment = ItemComment(author=request.user, event=event, item=item, membership=membership,
                                        comment=comment)
            item_comment.save()
            messages.success(request, 'Comment posted!')
            return redirect('events-item', event_id=event_id, item_id=item.id)
    elif 'youtube_submit' in request.POST:
        youtube_form = CreateItemYoutubeVideoForm(request.POST)
        if youtube_form.is_valid():
            url = youtube_form.cleaned_data['url']
            is_valid, is_embeddable, fragment = validate_and_categorize_youtube_link(url, request)
            if is_valid:
                youtube_video = ItemYoutubeVideo(author=request.user, membership=membership,
                                                 is_embeddable=is_embeddable, url=fragment, item=item)
                youtube_video.save()
                messages.success(request, 'Video submitted!')
        return redirect('events-item', event_id=event_id, item_id=item.id)
    elif 'casebuy_submit' in request.POST:
        case_buy_form = QuantitySelectForm(request.POST, max_pieces=100, item_price=item.price,
                                           item_packing=item.packing, whole_cases=True, initial_qty=initial_qty,
                                           is_inline=False)
        if case_buy_form.is_valid():
            quantity = case_buy_form.cleaned_data['quantity']
            if case_buy:
                    if int(quantity) == 0:
                        case_buy.delete()
                    else:
                        case_buy.quantity = quantity
                        case_buy.save()
            else:
                case_buy = CaseBuy(item=item, user=request.user, event=event, membership=membership, quantity=quantity)
                case_buy.save()
            messages.success(request, 'Quantity updated!')
            return redirect('events-item', event_id=event_id, item_id=item.id)
    elif 'casesplit_submit' in request.POST:
        case_split_form = QuantitySelectForm(request.POST, max_pieces=100, item_price=item.price,
                                           item_packing=item.packing, whole_cases=False, initial_qty=initial_qty,
                                             is_inline=False)
        if case_split_form.is_valid():
            quantity = case_split_form.cleaned_data['quantity']
            split = CaseSplit(item=item, event=event, started_by=request.user)
            split.save()
            commit = CasePieceCommit(user=request.user, event=event, quantity=quantity, membership=membership,
                                     case_split=split)
            commit.save()
            messages.success(request, 'Case split created!')
            return redirect('events-item', event_id=event_id, item_id=item.id)
    else:
        # Statistics 'Slice'
        item_data = item.render_event_view(membership=membership)

        # Case Buy
        case_buy_form = QuantitySelectForm(max_pieces=100, item_price=item.price, item_packing=item.packing,
                                           whole_cases=True, initial_qty=initial_qty, is_inline=False)

        # Case Split
        case_split_form = QuantitySelectForm(max_pieces=item.packing - 1, item_price=item.price,
                                             item_packing=item.packing, whole_cases=False, initial_qty=1,
                                             is_inline=False)

        if event.is_locked or event.is_closed:
            case_buy_form.fields['quantity'].disabled = True
            case_split_form.fields['quantity'].disabled = True

        # Chat
        event_comments = ItemComment.objects.filter(event=event).filter(item=item)
        paginator = Paginator(event_comments, 50)
        page_number = request.GET.get('page')
        page_comments = paginator.get_page(page_number)


        context = {
            'case_buy_form': case_buy_form,
            'case_split_form': case_split_form,
            'event' : event,
            'comment_form': CommentCreateForm(),
            'item': item,
            'item_data': item_data,
            'membership' : membership,
            'page_comments' : page_comments,
            'title' : item.name,
            'youtube_form': CreateItemYoutubeVideoForm()
        }
        return render(request, 'events/item.html', context=context)


@login_required
def delete_item_chat(request, event_id, item_id, chat_id):
    event, membership, is_valid = event_auth_checkpoint(event_id=event_id, request=request)
    if is_valid == False:
        return redirect('general-home')
    item = get_object_or_404(Item, pk=item_id)
    comment = get_object_or_404(ItemComment, pk=chat_id)
    if request.user == comment.author or request.user.is_staff or membership.is_organizer:
        comment.delete()
        messages.success(request, 'Comment deleted!')
        return redirect('events-item', event_id=event_id, item_id=item_id)
    else:
        messages.warning(request, 'Access denied.')
        return redirect('events-item', event_id=event_id, item_id=item_id)


@login_required
def delete_item_youtube(request, event_id, item_id, youtube_id):
    event, membership, is_valid = event_auth_checkpoint(event_id=event_id, request=request)
    if is_valid == False:
        return redirect('general-home')
    item = get_object_or_404(Item, pk=item_id)
    youtube_posting = get_object_or_404(ItemYoutubeVideo, pk=youtube_id)
    if request.user == youtube_posting.author or request.user.is_staff or membership.is_organizer:
        youtube_posting.delete()
        messages.success(request, 'Youtube posting deleted!')
        return redirect('events-item', event_id=event_id, item_id=item_id)
    else:
        messages.warning(request, 'Access denied.')
        return redirect('events-item', event_id=event_id, item_id=item_id)


@login_required
def edit_item(request, event_id, item_id):
    event, membership, is_valid = event_auth_checkpoint(event_id=event_id, request=request)
    if is_valid == False:
        return redirect('general-home')
    item = get_object_or_404(Item, pk=item_id)
    if request.method == 'POST':
        old_packing = item.packing
        form = ItemForm(request.POST, instance=item)
        if form.is_valid():
            modified_item = form.save()
            if old_packing != modified_item.packing:
                modified_item.case_splits.all().delete()
            modified_item.save()
            messages.success(request, "Item updated!")
            return redirect('events-item', event_id=event.id, item_id=item.id)

    else:
        form = ItemForm(initial={'category':item.category,
                                 'name': item.name,
                                 'price':item.price,
                                 'packing':item.packing
                                 })
        context = {
            'event': event,
            'form': form,
            'item': item,
            'title': f'Edit {item.name}'
        }
        return render(request, 'events/edit_item.html', context=context)


@login_required
def delete_item(request, event_id, item_id):
    event, membership, is_valid = event_auth_checkpoint(event_id=event_id, request=request, organizer=True)
    if is_valid == False:
        return redirect('general-home')
    item = get_object_or_404(Item, pk=item_id)
    item.delete()
    messages.success(request, 'Item successfully deleted!')
    return redirect('events-event', event_id=event_id)


@login_required
def case_split(request, event_id, item_id, case_split_id):
    event, membership, is_valid = event_auth_checkpoint(event_id=event_id, request=request)
    if is_valid == False:
        return redirect('general-home')
    item = get_object_or_404(Item, pk=item_id)
    case_split = get_object_or_404(CaseSplit, pk=case_split_id)
    if request.method == 'POST':
        form = QuantitySelectForm(request.POST, request.POST, max_pieces=item.packing, item_price=item.price,
                                        item_packing=item.packing, whole_cases=False, initial_qty=1, is_inline=True)
        if form.is_valid():
            form_quantity = int(form.cleaned_data['quantity'])
            try:
                case_split = CaseSplit.objects.get(id=case_split.id)
            except:
                messages.info(request, 'This case split has been deleted in between you loading the previous page and'
                                       'clicking submit.')
                return redirect('events-item', event=event, item=item)

            if case_split.is_complete and case_split.is_user_involved(request.user) == False:
                messages.info(request, 'This case split has been closed in the time between you loading the previous '
                                           'page and clicking submit.... someone else beat you to it!  '
                                           'Start a new case split instead')
                return redirect('events-case-split', event_id=event.id, item_id=item.id, case_split_id=case_split.id)
            elif event.is_locked:
                messages.info(request, 'This event has been locked in the time between you loading the previous page '
                                       'and clicking submit....')
                return redirect('events-case-split', event_id=event.id, item_id=item.id, case_split_id=case_split.id)
            else:
                try:
                    commit = CasePieceCommit.objects.filter(user=request.user).get(case_split=case_split)
                    commit_quantity = commit.quantity
                except:
                    commit = None
                    commit_quantity = 0
                if item.packing < form_quantity + case_split.return_reserved_pieces() - commit_quantity:
                    messages.info(request, 'Pieces pledged exceeds what is currently available for this case '
                                           'split.  This occurs when someone else places a pledge right before '
                                           'you.  Please resubmit a pledge with a different quantity, or otherwise '
                                           'create a new case split.')
                    return redirect('events-case-split', event_id=event.id, item_id=item.id,
                                    case_split_id=case_split.id)
                if commit:
                    commit.quantity = form_quantity
                    commit.save()
                else:
                    commit = CasePieceCommit(user=request.user, event=event, quantity=form_quantity,
                                             membership=membership, case_split=case_split)
                    commit.save()

                case_split.evaluate_complete_status()
                messages.info(request, 'Case split pledge accepted!')
                return redirect('events-case-split', event_id=event.id, item_id=item.id, case_split_id=case_split.id)
    else:
        if event.is_locked == False:
            try:
                commit = CasePieceCommit.objects.filter(membership=membership).filter(case_split=case_split).get()
                initial_quantity, self_offset = commit.quantity, commit.quantity
            except:
                initial_quantity = 1
                self_offset = 0
            form = QuantitySelectForm(max_pieces=item.packing - case_split.return_reserved_pieces()+ self_offset -
                                        (case_split.is_user_involved(membership.user) and
                                         case_split.split_commits.count() == 1), item_price=item.price,
                                        item_packing=item.packing, whole_cases=False, initial_qty=initial_quantity,
                                        is_inline=True)
        else:
            form = None
        context = {
            'case_split': case_split,
            'event': event,
            'form': form,
            'is_involved': case_split.is_user_involved(membership.user),
            'item': item,
            'membership': membership,
            'title': f'{item.name} Case Split'
        }
        return render(request, 'events/case_split.html', context=context)


@login_required
def case_split_delete(request, event_id, item_id, case_split_id):
    event, membership, is_valid = event_auth_checkpoint(event_id=event_id, request=request, organizer=True)
    if is_valid == False:
        return redirect('general-home')
    item = get_object_or_404(Item, pk=item_id)
    case_split = get_object_or_404(CaseSplit, pk=case_split_id)
    if event.is_closed:
        messages.warning(request, 'This action cannot be performed if the event is locked.')
        return redirect('events-item', event_id=event_id, item_id=item.id)
    case_split.delete()
    messages.success(request, 'Case split successfully deleted!')
    return redirect('events-item', event_id=event_id, item_id=item.id)


@login_required
def case_split_commit_delete(request, event_id, item_id, case_split_id, commit_id):
    event, membership, is_valid = event_auth_checkpoint(event_id=event_id, request=request)
    if is_valid == False:
        return redirect('general-home')
    item = get_object_or_404(Item, pk=item_id)
    case_split = get_object_or_404(CaseSplit, pk=case_split_id)
    commit = get_object_or_404(CasePieceCommit, pk=commit_id)
    if (request.user == commit.user and not event.is_locked) or membership.is_organizer or request.user.is_staff and \
    not event.is_closed:
        commit.delete()
        if not case_split.split_commits.count():
            case_split.delete()
            messages.success(request, 'Commit successfully removed!')
            return redirect('events-item', event_id=event.id, item_id=item.id)
        else:
            if case_split.is_complete == True:
                case_split.is_complete = False
                case_split.save()
                messages.success(request, 'Commit successfully removed!')
                return redirect('events-case-split', event_id=event.id, item_id=item.id, case_split_id=case_split.id)

    if event.is_closed:
        messages.warning(request, 'This action cannot be performed if the event is locked.')
        return redirect('events-item', event_id=event_id, item_id=item.id)


@login_required
def manage_payments(request, event_id):
    event, membership, is_valid = event_auth_checkpoint(event_id=event_id, request=request, organizer=True)
    if is_valid == False:
        return redirect('general-home')

    master_dict = event.generate_user_totals_all()

    context = {
        'event': event,
        'master_dict': master_dict,
        'title': 'Manage Payments'
    }
    return render(request, 'events/manage_payments.html', context=context)


@login_required
def toggle_payment(request, event_id, target_membership_id):
    event, your_membership, is_valid = event_auth_checkpoint(event_id=event_id, request=request, organizer=True)
    if is_valid == False:
        return redirect('general-home')
    membership = get_object_or_404(EventMembership, pk=target_membership_id)
    membership.has_paid = not membership.has_paid
    membership.save()
    if membership.has_paid:
        messages.success(request, f'{membership.user.username} has been marked as paid!')
        return redirect('events-manage-payments', event_id=event_id)
    else:
        messages.success(request, f'{membership.user.username} has been marked as unpaid!')
        return redirect('events-manage-payments', event_id=event_id)


@login_required
def manage_users(request, event_id):
    event, your_membership, is_valid = event_auth_checkpoint(event_id=event_id, request=request, organizer=True)
    if is_valid == False:
        return redirect('general-home')

    memberships = EventMembership.objects.filter(event=event)
    add_user_form = AddUserForm()

    if request.method == 'POST':
        form = AddUserForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            try:
                user = User.objects.get(username=username)
                membership = EventMembership(event=event, user=user)
                membership.save()
                messages.success(request, 'User successfully added.')
                return redirect('events-manage-users', event_id=event_id)
            except:
                messages.warning(request, f"User '{username}' does not exist.  Maybe it is misspelled?")
                return redirect('events-manage-users', event_id=event_id)

    else:
        context = {
            'add_user_form': add_user_form,
            'event': event,
            'memberships': memberships,
            'title': 'Manage Users',
            'your_membership': your_membership
        }
        return render(request, 'events/manage_users.html', context=context)


@login_required
def toggle_organizer(request, event_id, user_id):
    event, membership, is_valid = event_auth_checkpoint(event_id=event_id, request=request, organizer=True)
    if is_valid == False:
        return redirect('general-home')
    if request.user.is_staff or membership.is_creator:
        target_membership = EventMembership.objects.get(user__id=user_id, event__id=event_id)
        target_membership.is_organizer = not target_membership.is_organizer
        target_membership.save()
        if target_membership.is_organizer:
            messages.success(request, f'Organizer status enabled for {target_membership.user.username}.')
        else:
            messages.success(request, f'Organizer status disabled for {target_membership.user.username}.')
        return redirect('events-manage-users', event_id=event.id)
    else:
        messages.warning(request, 'Access denied.')
        return redirect('general-home')


@login_required
def remove_participant(request, event_id, user_id):
    event, membership, is_valid = event_auth_checkpoint(event_id=event_id, request=request, organizer=True)
    if is_valid == False:
        return redirect('general-home')
    if request.user.is_staff or membership.is_creator:
        target_membership = EventMembership.objects.get(user__id=user_id, event__id=event_id)
        username = target_membership.user.username
        for commit in target_membership.split_commits:
            commit.case_split.is_complete = False
            commit.case_split.save()
        target_membership.delete()
        messages.success(request, f'{username} removed from event.')
        return redirect('events-manage-users', event_id=event.id)

    else:
        messages.warning(request, 'Access denied.')
        return redirect('general-home')


@login_required
def event_order_summary(request, event_id):
    event, membership, is_valid = event_auth_checkpoint(event_id=event_id, request=request, summary_or_breakdown=True)
    if is_valid == False:
        return redirect('general-home')

    summary_data = event.generate_event_pages_contents(page_type='summary')

    context = {
        'event': event,
        'summary_data': summary_data,
        'title': 'Event Order Summary'
    }
    return render(request, 'events/event_order_summary.html', context=context)

@login_required
def order_breakdown(request, event_id):
    event, membership, is_valid = event_auth_checkpoint(event_id=event_id, request=request, summary_or_breakdown=True)
    if is_valid == False:
        return redirect('general-home')

    breakdown_data = event.generate_event_pages_contents(page_type='breakdown')

    context = {
        'breakdown_data': breakdown_data,
        'event': event,
        'title': 'Order Breakdown By User',
    }
    return render(request, 'events/user_breakdown.html', context=context)


@login_required
def my_order(request, event_id, user_id):
    event, membership, is_valid = event_auth_checkpoint(event_id=event_id, request=request)
    if is_valid == False:
        return redirect('general-home')
    targetted_user = get_object_or_404(User, pk=user_id)
    if not event.users_full_event_visibility and targetted_user != request.user and not membership.is_organizer:
        messages.info(request, "This view is restricted for organizers only.")
        return redirect('events-event', event_id=event_id)

    if request.method == 'POST':
        form = UserSelectForm(request.POST, member_list=event.members.all(), initial_choice=targetted_user.username)
        if form.is_valid():
            selected_user = form.cleaned_data['member_choice']
            switch_user_view = User.objects.get(username=selected_user)
            return redirect('events-my-order', event_id=event_id, user_id=switch_user_view.id)
    else:
        form = UserSelectForm(member_list=event.members.all(), initial_choice=targetted_user.username)

        targetted_membership = EventMembership.objects.filter(event=event).get(user=targetted_user)
        my_order_data = event.generate_event_pages_contents(page_type='my_order', membership=targetted_membership)

        context = {
            'event': event,
            'form': form,
            'my_order_data': my_order_data,
            'title': f"{targetted_user.username}'s Order",
            'targetted_user': targetted_user
        }
        return render(request, 'events/my_order.html', context=context)


@login_required
def chat(request, event_id):
    event, membership, is_valid = event_auth_checkpoint(event_id=event_id, request=request)
    if is_valid == False:
        return redirect('general-home')

    if request.method == 'POST':
        form = CommentCreateForm(request.POST)
        if form.is_valid():
            comment = form.cleaned_data['comment']
            event_comment = EventComment(author=request.user, event=event, membership=membership, comment=comment)
            event_comment.save()
            messages.success(request, 'Comment posted!')
            return redirect('events-chat', event_id=event_id)
    else:
        event_comments = EventComment.objects.filter(event=event)
        paginator = Paginator(event_comments, 50)
        page_number = request.GET.get('page')
        page_comments = paginator.get_page(page_number)

        context = {
            'event' : event,
            'form' : CommentCreateForm(),
            'membership' : membership,
            'page_comments' : page_comments,
            'title' : 'Event Chat'
        }
        return render(request, 'events/chat.html', context=context)


@login_required
def comment_delete(request, event_id, comment_id):
    event, membership, is_valid = event_auth_checkpoint(event_id=event_id, request=request)
    if is_valid == False:
        return redirect('general-home')
    comment = get_object_or_404(EventComment, pk=comment_id)
    if request.user == comment.author or request.user.is_staff or membership.is_organizer:
        comment.delete()
        messages.success(request, 'Comment deleted!')
        return redirect('events-chat', event_id=event_id)
    else:
        messages.warning(request, 'Access denied.')
        return redirect('events-chat', event_id=event_id)