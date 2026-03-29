import calendar
import json
from datetime import date

from django.db import transaction
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.db import models as db_models
from .models import ChitGroup, ChitRound, ChitMembership, Payment, Member, RoundSchedule

# List all members with details and delete option
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt

def all_members(request):
    members = Member.objects.all().order_by('-date_joined')
    return render(request, 'management/all_members.html', {'members': members})


def edit_member_details(request, member_id):
    member = get_object_or_404(Member, pk=member_id)
    error_message = None
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        phone = request.POST.get('phone', '').strip()
        alternate_phone = request.POST.get('alternate_phone', '').strip()
        aadhar_number = request.POST.get('aadhar_number', '').strip()
        if not name or not phone or not aadhar_number:
            error_message = 'Name, phone and Aadhar number are required.'
        elif len(phone) != 10 or not phone.isdigit():
            error_message = 'Enter a valid 10-digit phone number.'
        elif alternate_phone and (len(alternate_phone) != 10 or not alternate_phone.isdigit()):
            error_message = 'Enter a valid 10-digit alternate phone number.'
        elif len(aadhar_number) != 12 or not aadhar_number.isdigit():
            error_message = 'Enter a valid 12-digit Aadhar number.'
        else:
            member.name = name
            member.phone = phone
            member.alternate_phone = alternate_phone or None
            member.email = request.POST.get('email') or None
            member.address = request.POST.get('address', member.address)
            member.aadhar_number = aadhar_number
            member.is_active = request.POST.get('is_active') == 'on'
            member.save()
            return redirect('all_members')
    return render(request, 'management/edit_member_details.html', {
        'member': member,
        'error_message': error_message,
    })

# Delete member with confirmation
@csrf_exempt
def delete_member(request, member_id):
    member = get_object_or_404(Member, pk=member_id)
    if request.method == 'POST':
        member.delete()
        messages.success(request, f"Member '{member.name}' deleted successfully.")
        return redirect('all_members')
    return render(request, 'management/delete_member_confirm.html', {'member': member})


def create_member(request):
    error_message = None
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        phone = request.POST.get('phone', '').strip()
        alternate_phone = request.POST.get('alternate_phone', '').strip()
        email = request.POST.get('email', '').strip()
        address = request.POST.get('address', '').strip()
        aadhar_number = request.POST.get('aadhar_number', '').strip()
        is_active = request.POST.get('is_active', 'on') == 'on'
        # Validate required fields
        if not name or not phone or not address or not aadhar_number:
            error_message = 'Please fill all required fields.'
        elif len(phone) != 10 or not phone.isdigit():
            error_message = 'Enter a valid 10-digit phone number.'
        elif alternate_phone and (len(alternate_phone) != 10 or not alternate_phone.isdigit()):
            error_message = 'Enter a valid 10-digit alternate phone number.'
        elif len(aadhar_number) != 12 or not aadhar_number.isdigit():
            error_message = 'Enter a valid 12-digit Aadhar number.'
        else:
            try:
                member = Member.objects.create(
                    name=name,
                    phone=phone,
                    alternate_phone=alternate_phone or None,
                    email=email or None,
                    address=address,
                    aadhar_number=aadhar_number,
                    is_active=is_active,
                )
                return redirect('dashboard')
            except Exception as e:
                error_message = str(e)
    return render(request, 'management/create_member.html', {
        'error_message': error_message,
        'form_data': request.POST if request.method == 'POST' else {},
    })


def add_months(base_date, months_to_add):
    month_index = (base_date.month - 1) + months_to_add
    year = base_date.year + (month_index // 12)
    month = (month_index % 12) + 1
    day = min(base_date.day, calendar.monthrange(year, month)[1])
    return base_date.replace(year=year, month=month, day=day)


def group_print(request, group_id):
    from decimal import Decimal
    group = get_object_or_404(
        ChitGroup.objects.prefetch_related(
            'memberships__member', 'rounds__winner__member', 'round_schedules'
        ), pk=group_id
    )
    memberships = list(group.memberships.all().order_by('slot_number'))
    paid_map = {}
    for p in Payment.objects.filter(
        chit_round__chit_group=group,
        status__in=['paid', 'late'],
    ).select_related('chit_round').order_by('paid_date'):
        key = (p.chit_round.round_number, p.membership_id)
        if key not in paid_map:
            paid_map[key] = []
        paid_map[key].append({
            'amount': str(p.amount_paid),
            'date': str(p.paid_date) if p.paid_date else '',
        })
    member_totals = {m.id: Decimal('0') for m in memberships}
    schedule_winner_total = Decimal('0')
    schedule_others_total = Decimal('0')
    schedule_due_total = Decimal('0')
    schedule_data = []
    for sched in group.round_schedules.all():
        member_payments = []
        round_total = Decimal('0')
        winner_installment = Decimal(str(sched.winner_installment_amount))
        others_installment = Decimal(str(sched.others_installment_amount))
        schedule_winner_total += winner_installment
        schedule_others_total += others_installment
        round_no = sched.round_number
        total_rounds = group.total_rounds
        lifted_count = max(round_no - 1, 0)
        not_lifted_count = max(total_rounds - round_no + 1, 0)
        expected_round_total = (winner_installment * lifted_count) + (others_installment * not_lifted_count)
        for m in memberships:
            key = (sched.round_number, m.id)
            if key in paid_map:
                cell_total = sum(Decimal(p['amount']) for p in paid_map[key])
                round_total += cell_total
                member_totals[m.id] += cell_total
                member_payments.append({
                    'paid': True,
                    'payments': paid_map[key],
                    'cell_total': str(cell_total),
                })
            else:
                member_payments.append({'paid': False})
        due_amount = expected_round_total - round_total
        schedule_due_total += due_amount
        schedule_data.append({
            'schedule': sched,
            'member_payments': member_payments,
            'round_total': str(round_total),
            'due_amount': str(due_amount),
        })
    member_totals_list = [str(member_totals[m.id]) for m in memberships]
    grand_total = str(sum(member_totals.values()))
    lift_round_map = {}
    for r in group.rounds.filter(winner__isnull=False).select_related('winner'):
        if r.winner_id:
            lift_round_map[r.winner_id] = r
    members_data = []
    for m in memberships:
        total_paid = member_totals[m.id]
        if m.id in lift_round_map:
            lift_round = lift_round_map[m.id]
            lift_amt = Decimal(str(lift_round.lift_amount)) if lift_round.lift_amount else Decimal('0')
            due = lift_amt - total_paid
            members_data.append({
                'membership': m,
                'is_lifted': True,
                'lift_amount': str(lift_amt),
                'total_paid': str(total_paid),
                'due_amount': str(due),
                'due_positive': due >= Decimal('0'),
            })
        else:
            members_data.append({
                'membership': m,
                'is_lifted': False,
                'total_paid': str(total_paid),
            })
    return render(request, 'management/group_print.html', {
        'group': group,
        'memberships': memberships,
        'members_data': members_data,
        'schedule_data': schedule_data,
        'member_totals': member_totals_list,
        'grand_total': grand_total,
        'schedule_winner_total': str(schedule_winner_total),
        'schedule_others_total': str(schedule_others_total),
        'schedule_due_total': str(schedule_due_total),
    })


def dashboard(request, group_id=None):
    groups = ChitGroup.objects.all()
    selected_group = None
    members_data = []
    member_totals_list = []
    grand_total = '0'
    schedule_due_total = '0'
    schedule_winner_total = '0'
    schedule_others_total = '0'
    if group_id:
        selected_group = get_object_or_404(
            ChitGroup.objects.prefetch_related(
                'memberships__member', 'rounds__winner__member', 'round_schedules'
            ), pk=group_id
        )
    elif groups.exists():
        first = groups.first()
        selected_group = ChitGroup.objects.prefetch_related(
            'memberships__member', 'rounds__winner__member', 'round_schedules'
        ).get(pk=first.pk)
    lifted_ids = set()
    memberships = []
    schedule_data = []
    if selected_group:
        lifted_ids = set(
            selected_group.rounds.filter(winner__isnull=False)
            .values_list('winner_id', flat=True)
        )
        memberships = list(selected_group.memberships.all().order_by('slot_number'))
        paid_map = {}
        for p in Payment.objects.filter(
            chit_round__chit_group=selected_group,
            status__in=['paid', 'late'],
        ).select_related('chit_round').order_by('paid_date'):
            key = (p.chit_round.round_number, p.membership_id)
            if key not in paid_map:
                paid_map[key] = []
            paid_map[key].append({
                'amount': str(p.amount_paid),
                'date': str(p.paid_date) if p.paid_date else '',
            })
        from decimal import Decimal
        member_totals = {m.id: Decimal('0') for m in memberships}
        schedule_winner_total_decimal = Decimal('0')
        schedule_others_total_decimal = Decimal('0')
        schedule_due_total_decimal = Decimal('0')
        for sched in selected_group.round_schedules.all():
            member_payments = []
            round_total = Decimal('0')
            winner_installment = Decimal(str(sched.winner_installment_amount))
            others_installment = Decimal(str(sched.others_installment_amount))
            schedule_winner_total_decimal += winner_installment
            schedule_others_total_decimal += others_installment
            round_no = sched.round_number
            total_rounds = selected_group.total_rounds
            lifted_count = max(round_no - 1, 0)
            not_lifted_count = max(total_rounds - round_no + 1, 0)
            expected_round_total = (winner_installment * lifted_count) + (others_installment * not_lifted_count)
            for m in memberships:
                key = (sched.round_number, m.id)
                if key in paid_map:
                    cell_total = sum(Decimal(p['amount']) for p in paid_map[key])
                    round_total += cell_total
                    member_totals[m.id] += cell_total
                    member_payments.append({
                        'paid': True,
                        'payments': paid_map[key],
                        'cell_total': str(cell_total),
                        'membership_id': m.id,
                        'round_number': sched.round_number,
                    })
                else:
                    member_payments.append({
                        'paid': False,
                        'membership_id': m.id,
                        'round_number': sched.round_number,
                    })
            due_amount = expected_round_total - round_total
            schedule_due_total_decimal += due_amount
            schedule_data.append({
                'schedule': sched,
                'member_payments': member_payments,
                'round_total': str(round_total),
                'due_amount': str(due_amount),
            })
        member_totals_list = [str(member_totals[m.id]) for m in memberships]
        grand_total = str(sum(member_totals.values()))
        schedule_winner_total = str(schedule_winner_total_decimal)
        schedule_others_total = str(schedule_others_total_decimal)
        schedule_due_total = str(schedule_due_total_decimal)
        # Build members table data with due amount for lift members
        lift_round_map = {}  # membership_id -> ChitRound
        for r in selected_group.rounds.filter(winner__isnull=False).select_related('winner'):
            if r.winner_id:
                lift_round_map[r.winner_id] = r
        members_data = []
        for m in memberships:
            total_paid = member_totals[m.id]
            if m.id in lift_round_map:
                lift_round = lift_round_map[m.id]
                lift_amt = Decimal(str(lift_round.lift_amount)) if lift_round.lift_amount else Decimal('0')
                due = lift_amt - total_paid
                members_data.append({
                    'membership': m,
                    'is_lifted': True,
                    'lift_amount': str(lift_amt),
                    'total_paid': str(total_paid),
                    'due_amount': str(due),
                    'due_positive': due >= Decimal('0'),
                })
            else:
                members_data.append({
                    'membership': m,
                    'is_lifted': False,
                    'total_paid': str(total_paid),
                })
    return render(request, 'management/dashboard.html', {
        'groups': groups,
        'selected_group': selected_group,
        'lifted_ids': lifted_ids,
        'memberships': memberships,
        'members_data': members_data,
        'schedule_data': schedule_data,
        'member_totals': member_totals_list,
        'grand_total': grand_total,
        'schedule_winner_total': schedule_winner_total,
        'schedule_others_total': schedule_others_total,
        'schedule_due_total': schedule_due_total,
    })


def create_group(request):
    members = list(Member.objects.filter(is_active=True).order_by('name'))
    error_message = None
    form_data = {}
    selected_member_ids = []

    if request.method == 'POST':
        form_data = request.POST
        selected_member_ids = request.POST.getlist('member_ids')

        try:
            total_members = int(request.POST.get('total_members') or 0)
            total_rounds = int(request.POST.get('total_rounds') or 0)
            frequency_months = int(request.POST.get('frequency_months') or 0)
            due_day = int(request.POST.get('due_day') or 10)
        except ValueError:
            error_message = 'Enter valid numeric values for members, rounds, frequency, and due day.'
        else:
            if total_members <= 0 or total_rounds <= 0:
                error_message = 'Total members and total rounds must be greater than 0.'
            elif len(selected_member_ids) != total_members:
                error_message = 'Selected member count must match total members.'
            else:
                try:
                    start_date = date.fromisoformat(request.POST.get('start_date'))
                except (TypeError, ValueError):
                    error_message = 'Enter a valid start date.'
                else:
                    members_by_id = {
                        str(member.id): member
                        for member in Member.objects.filter(id__in=selected_member_ids, is_active=True)
                    }
                    ordered_members = [members_by_id[member_id] for member_id in selected_member_ids if member_id in members_by_id]

                    if len(ordered_members) != len(selected_member_ids):
                        error_message = 'One or more selected members are invalid or inactive.'
                    else:
                        with transaction.atomic():
                            group = ChitGroup.objects.create(
                                name=request.POST.get('name'),
                                total_members=total_members,
                                installment_amount=request.POST.get('installment_amount'),
                                prize_amount=request.POST.get('prize_amount'),
                                frequency_months=frequency_months,
                                total_rounds=total_rounds,
                                start_date=start_date,
                                due_day=due_day,
                                penalty_amount=request.POST.get('penalty_amount') or 0,
                                status=request.POST.get('status') or 'upcoming',
                                notes=request.POST.get('notes') or None,
                            )

                            for slot_number, member in enumerate(ordered_members, start=1):
                                ChitMembership.objects.create(
                                    chit_group=group,
                                    member=member,
                                    slot_number=slot_number,
                                )

                            for round_number in range(1, total_rounds + 1):
                                RoundSchedule.objects.create(
                                    chit_group=group,
                                    round_number=round_number,
                                    planned_date=add_months(start_date, (round_number - 1) * frequency_months),
                                    winner_installment_amount=request.POST.get('winner_installment_amount'),
                                    others_installment_amount=request.POST.get('others_installment_amount'),
                                )

                        return redirect('dashboard_group', group_id=group.id)

    return render(request, 'management/create_group.html', {
        'members': members,
        'members_json': json.dumps([
            {'id': m.id, 'name': m.name, 'phone': m.phone}
            for m in members
        ]),
        'error_message': error_message,
        'form_data': form_data,
        'selected_member_ids_json': json.dumps(selected_member_ids),
    })


@require_POST
def add_round(request, group_id):
    group = get_object_or_404(ChitGroup, pk=group_id)
    last_round = group.rounds.order_by('-round_number').first()
    next_number = (last_round.round_number + 1) if last_round else 1

    winner_id = request.POST.get('winner')
    winner = None
    if winner_id:
        winner = get_object_or_404(ChitMembership, pk=winner_id, chit_group=group)

    ChitRound.objects.create(
        chit_group=group,
        round_number=next_number,
        round_date=request.POST.get('round_date'),
        winner=winner,
        lift_amount=request.POST.get('lift_amount') or None,
        disbursed_date=request.POST.get('disbursed_date') or None,
        disbursement_mode=request.POST.get('disbursement_mode') or None,
        document=request.FILES.get('document'),
        surety_details=request.POST.get('surety_details') or None,
        remarks=request.POST.get('remarks') or None,
    )
    return redirect('dashboard_group', group_id=group.id)


@require_POST
def save_payment(request, group_id):
    group = get_object_or_404(ChitGroup, pk=group_id)
    membership_id = request.POST.get('membership_id')
    round_number = request.POST.get('round_number')
    amount = request.POST.get('amount')
    paid_date = request.POST.get('paid_date')

    if not all([membership_id, round_number, amount, paid_date]):
        return JsonResponse({'success': False, 'error': 'All fields are required.'}, status=400)

    membership = get_object_or_404(ChitMembership, pk=membership_id, chit_group=group)
    chit_round = get_object_or_404(ChitRound, chit_group=group, round_number=round_number)

    payment = Payment.objects.create(
        membership=membership,
        chit_round=chit_round,
        amount_paid=amount,
        paid_date=paid_date,
        status='paid',
    )
    # Calculate new cell total
    from decimal import Decimal
    cell_total = Payment.objects.filter(
        membership=membership,
        chit_round=chit_round,
        status__in=['paid', 'late'],
    ).aggregate(total=db_models.Sum('amount_paid'))['total'] or Decimal('0')
    return JsonResponse({
        'success': True,
        'amount': str(payment.amount_paid),
        'date': str(payment.paid_date),
        'cell_total': str(cell_total),
    })


def edit_group(request, group_id):
    group = get_object_or_404(ChitGroup, pk=group_id)
    
    if request.method == 'POST':
        group.name = request.POST.get('name', group.name)
        group.total_members = request.POST.get('total_members', group.total_members)
        group.installment_amount = request.POST.get('installment_amount', group.installment_amount)
        group.prize_amount = request.POST.get('prize_amount', group.prize_amount)
        group.frequency_months = request.POST.get('frequency_months', group.frequency_months)
        group.total_rounds = request.POST.get('total_rounds', group.total_rounds)
        group.start_date = request.POST.get('start_date', group.start_date)
        group.due_day = request.POST.get('due_day', group.due_day)
        group.penalty_amount = request.POST.get('penalty_amount', group.penalty_amount)
        group.status = request.POST.get('status', group.status)
        group.notes = request.POST.get('notes', group.notes)
        group.save()
        return redirect('dashboard_group', group_id=group.id)
    
    return render(request, 'management/edit_group.html', {'group': group})


def delete_group(request, group_id):
    group = get_object_or_404(ChitGroup, pk=group_id)
    if request.method == 'POST':
        group_name = group.name
        with transaction.atomic():
            # Delete in dependency order to avoid ProtectedError
            # 1. Payments (reference ChitMembership and ChitRound)
            Payment.objects.filter(chit_round__chit_group=group).delete()
            # 2. Clear round winners before deleting rounds (winner FK is PROTECT on ChitMembership)
            ChitRound.objects.filter(chit_group=group).update(winner=None)
            # 3. Delete rounds and schedules
            ChitRound.objects.filter(chit_group=group).delete()
            RoundSchedule.objects.filter(chit_group=group).delete()
            # 4. Delete memberships
            ChitMembership.objects.filter(chit_group=group).delete()
            # 5. Delete the group
            group.delete()
        messages.success(request, f"Chit group '{group_name}' deleted successfully.")
        return redirect('dashboard')
    return render(request, 'management/delete_group_confirm.html', {'group': group})


def edit_members(request, group_id):
    group = get_object_or_404(ChitGroup, pk=group_id)
    memberships = group.memberships.select_related('member').order_by('slot_number')
    return render(request, 'management/edit_members.html', {
        'group': group,
        'memberships': memberships,
    })


def edit_member(request, group_id, member_id):
    group = get_object_or_404(ChitGroup, pk=group_id)
    membership = get_object_or_404(ChitMembership, pk=member_id, chit_group=group)
    member = membership.member
    
    if request.method == 'POST':
        member.name = request.POST.get('name', member.name)
        member.phone = request.POST.get('phone', member.phone)
        member.alternate_phone = request.POST.get('alternate_phone') or None
        member.email = request.POST.get('email') or None
        member.address = request.POST.get('address', member.address)
        member.aadhar_number = request.POST.get('aadhar_number', member.aadhar_number)
        member.save()
        committed_round = request.POST.get('committed_round_number') or None
        committed_lift = request.POST.get('committed_lift_amount') or None
        membership.committed_round_number = int(committed_round) if committed_round else None
        membership.committed_lift_amount = committed_lift if committed_lift else None
        membership.save()
        return redirect('edit_members', group_id=group.id)
    
    return render(request, 'management/edit_member.html', {
        'group': group,
        'membership': membership,
        'member': member,
    })


def member_book(request, group_id, membership_id):
    from decimal import Decimal

    group = get_object_or_404(
        ChitGroup.objects.prefetch_related(
            'round_schedules', 'rounds__winner__member', 'memberships__member'
        ),
        pk=group_id,
    )
    membership = get_object_or_404(
        ChitMembership.objects.select_related('member'),
        pk=membership_id,
        chit_group=group,
    )

    payments_by_round = {}
    for payment in Payment.objects.filter(
        membership=membership,
        chit_round__chit_group=group,
        status__in=['paid', 'late'],
    ).select_related('chit_round').order_by('chit_round__round_number', 'paid_date'):
        round_no = payment.chit_round.round_number
        payments_by_round.setdefault(round_no, []).append(payment)

    winner_round = group.rounds.filter(winner=membership).first()
    total_paid = Payment.objects.filter(
        membership=membership,
        chit_round__chit_group=group,
        status__in=['paid', 'late'],
    ).aggregate(total=db_models.Sum('amount_paid'))['total'] or Decimal('0')

    schedule_rows = []
    for schedule in group.round_schedules.all().order_by('round_number'):
        round_payments = payments_by_round.get(schedule.round_number, [])
        round_total = sum((payment.amount_paid for payment in round_payments), Decimal('0'))
        schedule_rows.append({
            'round_number': schedule.round_number,
            'planned_date': schedule.planned_date,
            'lift_installment': schedule.winner_installment_amount,
            'chit_installment': schedule.others_installment_amount,
            'payments': round_payments,
            'round_total': round_total,
        })

    return render(request, 'management/member_book.html', {
        'group': group,
        'membership': membership,
        'member': membership.member,
        'winner_round': winner_round,
        'total_paid': total_paid,
        'schedule_rows': schedule_rows,
    })


def edit_rounds(request, group_id):
    group = get_object_or_404(ChitGroup, pk=group_id)
    rounds = group.rounds.select_related('winner__member').order_by('round_number')
    return render(request, 'management/edit_rounds.html', {
        'group': group,
        'rounds': rounds,
    })


def edit_round(request, group_id, round_id):
    group = get_object_or_404(ChitGroup, pk=group_id)
    chit_round = get_object_or_404(ChitRound, pk=round_id, chit_group=group)
    memberships = group.memberships.select_related('member').order_by('slot_number')
    
    if request.method == 'POST':
        chit_round.round_date = request.POST.get('round_date', chit_round.round_date)
        winner_id = request.POST.get('winner')
        if winner_id:
            chit_round.winner = get_object_or_404(ChitMembership, pk=winner_id, chit_group=group)
        else:
            chit_round.winner = None
        chit_round.lift_amount = request.POST.get('lift_amount') or None
        chit_round.surety_details = request.POST.get('surety_details') or None
        chit_round.disbursed_date = request.POST.get('disbursed_date') or None
        chit_round.disbursement_mode = request.POST.get('disbursement_mode') or None
        if request.FILES.get('document'):
            chit_round.document = request.FILES.get('document')
        chit_round.remarks = request.POST.get('remarks') or None
        chit_round.status = request.POST.get('status', chit_round.status)
        chit_round.save()
        return redirect('edit_rounds', group_id=group.id)
    
    return render(request, 'management/edit_round.html', {
        'group': group,
        'chit_round': chit_round,
        'memberships': memberships,
    })


def add_membership(request, group_id):
    group = get_object_or_404(ChitGroup, pk=group_id)
    members = Member.objects.filter(is_active=True).order_by('name')
    existing_slots = set(group.memberships.values_list('slot_number', flat=True))
    next_slot = 1
    while next_slot in existing_slots:
        next_slot += 1

    error_message = None
    if request.method == 'POST':
        member_id = request.POST.get('member_id', '').strip()
        slot_number_raw = request.POST.get('slot_number', '').strip()
        if not member_id or not slot_number_raw:
            error_message = 'Member and slot number are required.'
        else:
            try:
                slot_number = int(slot_number_raw)
                if slot_number < 1:
                    raise ValueError
            except ValueError:
                error_message = 'Enter a valid slot number.'
            else:
                if slot_number in existing_slots:
                    error_message = f'Slot {slot_number} is already occupied. Choose a different slot number.'
                else:
                    member = get_object_or_404(Member, pk=member_id, is_active=True)
                    ChitMembership.objects.create(
                        chit_group=group,
                        member=member,
                        slot_number=slot_number,
                    )
                    return redirect('edit_members', group_id=group.id)

    return render(request, 'management/add_membership.html', {
        'group': group,
        'members': members,
        'next_slot': next_slot,
        'error_message': error_message,
        'form_data': request.POST if request.method == 'POST' else {},
    })


def edit_schedules(request, group_id):
    group = get_object_or_404(ChitGroup, pk=group_id)
    schedules = group.round_schedules.order_by('round_number')
    return render(request, 'management/edit_schedules.html', {
        'group': group,
        'schedules': schedules,
    })


def edit_schedule(request, group_id, schedule_id):
    group = get_object_or_404(ChitGroup, pk=group_id)
    schedule = get_object_or_404(RoundSchedule, pk=schedule_id, chit_group=group)

    if request.method == 'POST':
        schedule.planned_date = request.POST.get('planned_date', schedule.planned_date)
        schedule.winner_installment_amount = request.POST.get('winner_installment_amount', schedule.winner_installment_amount)
        schedule.others_installment_amount = request.POST.get('others_installment_amount', schedule.others_installment_amount)
        schedule.save()
        return redirect('edit_schedules', group_id=group.id)

    return render(request, 'management/edit_schedule.html', {
        'group': group,
        'schedule': schedule,
    })
