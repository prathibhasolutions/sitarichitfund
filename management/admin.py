from django.contrib import admin
from .models import Member, ChitGroup, ChitMembership, ChitRound, Payment, RoundSchedule


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'aadhar_number', 'is_active', 'date_joined']
    search_fields = ['name', 'phone', 'aadhar_number']
    list_filter = ['is_active']


class RoundScheduleInline(admin.TabularInline):
    model = RoundSchedule
    extra = 12
    fields = ['round_number', 'planned_date', 'winner_installment_amount', 'others_installment_amount']
    verbose_name = 'Round'
    verbose_name_plural = 'Round-wise Installment Amounts'


class ChitMembershipInline(admin.TabularInline):
    model = ChitMembership
    extra = 1
    fields = ['member', 'slot_number', 'has_won']
    verbose_name = 'Member'
    verbose_name_plural = 'Members in this Group'


@admin.register(ChitGroup)
class ChitGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'total_members', 'installment_amount', 'prize_amount', 'frequency_months', 'start_date', 'status']
    search_fields = ['name']
    list_filter = ['status', 'frequency_months']
    inlines = [RoundScheduleInline, ChitMembershipInline]


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    fields = ['membership', 'amount_paid', 'paid_date', 'is_winner_payment', 'penalty_amount', 'status', 'receipt_number']


@admin.register(ChitRound)
class ChitRoundAdmin(admin.ModelAdmin):
    list_display = ['chit_group', 'round_number', 'round_date', 'winner', 'winner_installment_amount', 'others_installment_amount', 'prize_amount', 'status']
    search_fields = ['chit_group__name']
    list_filter = ['status', 'chit_group']
    inlines = [PaymentInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['membership', 'chit_round', 'amount_paid', 'paid_date', 'penalty_amount', 'status', 'receipt_number']
    search_fields = ['membership__member__name', 'receipt_number']
    list_filter = ['status', 'chit_round__chit_group']

