from django.db import models
from django.core.validators import RegexValidator


class Member(models.Model):
    name = models.CharField(max_length=200)
    phone = models.CharField(
        max_length=10,
        validators=[RegexValidator(r'^\d{10}$', 'Enter a valid 10-digit phone number.')]
    )
    alternate_phone = models.CharField(max_length=10, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField()
    aadhar_number = models.CharField(max_length=12, unique=True)
    date_joined = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.phone})"

    class Meta:
        verbose_name = 'Member'
        verbose_name_plural = 'Members'
        ordering = ['name']


class ChitGroup(models.Model):
    STATUS_CHOICES = [
        ('upcoming', 'Upcoming'),
        ('active', 'Active'),
        ('closed', 'Closed'),
    ]
    FREQUENCY_CHOICES = [
        (1, 'Monthly'),
        (2, 'Every 2 Months'),
        (3, 'Every 3 Months'),
        (6, 'Every 6 Months'),
    ]

    name = models.CharField(max_length=200)
    total_members = models.PositiveIntegerField()
    installment_amount = models.DecimalField(max_digits=10, decimal_places=2, help_text='Amount each non-winner pays per round')
    prize_amount = models.DecimalField(max_digits=12, decimal_places=2, help_text='Total prize amount winner receives')
    frequency_months = models.PositiveIntegerField(choices=FREQUENCY_CHOICES, default=3, help_text='How often the chit auction happens')
    total_rounds = models.PositiveIntegerField(help_text='Total number of rounds (equal to total members)')
    start_date = models.DateField()
    due_day = models.PositiveIntegerField(default=10, help_text='Day of month by which payment is due')
    penalty_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0, help_text='Penalty for late payment')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='upcoming')
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} (₹{self.prize_amount})"

    class Meta:
        verbose_name = 'Chit Group'
        verbose_name_plural = 'Chit Groups'
        ordering = ['-start_date']


class RoundSchedule(models.Model):
    """Pre-defined installment amounts for each round, set at group creation time."""
    chit_group = models.ForeignKey(ChitGroup, on_delete=models.CASCADE, related_name='round_schedules')
    round_number = models.PositiveIntegerField()
    planned_date = models.DateField()
    winner_installment_amount = models.DecimalField(max_digits=10, decimal_places=2, help_text='Amount the winner of this round pays')
    others_installment_amount = models.DecimalField(max_digits=10, decimal_places=2, help_text='Amount all other members pay (usually fixed)')

    def __str__(self):
        return f"{self.chit_group.name} - Round {self.round_number} (Winner: ₹{self.winner_installment_amount} | Others: ₹{self.others_installment_amount})"

    class Meta:
        verbose_name = 'Round Schedule'
        verbose_name_plural = 'Round Schedules'
        unique_together = [['chit_group', 'round_number']]
        ordering = ['chit_group', 'round_number']


class ChitMembership(models.Model):
    member = models.ForeignKey(Member, on_delete=models.PROTECT, related_name='memberships')
    chit_group = models.ForeignKey(ChitGroup, on_delete=models.PROTECT, related_name='memberships')
    slot_number = models.PositiveIntegerField(help_text='Member slot number in this group')
    has_won = models.BooleanField(default=False)
    date_enrolled = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.member.name} - {self.chit_group.name} (Slot {self.slot_number})"

    class Meta:
        verbose_name = 'Chit Membership'
        verbose_name_plural = 'Chit Memberships'
        unique_together = [['chit_group', 'slot_number'], ['chit_group', 'member']]
        ordering = ['chit_group', 'slot_number']


class ChitRound(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
    ]

    chit_group = models.ForeignKey(ChitGroup, on_delete=models.PROTECT, related_name='rounds')
    round_number = models.PositiveIntegerField()
    round_date = models.DateField()
    winner = models.ForeignKey(ChitMembership, on_delete=models.PROTECT, related_name='won_rounds', blank=True, null=True)
    lift_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, help_text='Amount given to the lift member this round')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    disbursed_date = models.DateField(blank=True, null=True)
    disbursement_mode = models.CharField(max_length=50, choices=[('cash', 'Cash'), ('bank', 'Bank Transfer'), ('upi', 'UPI')], blank=True, null=True)
    document = models.FileField(upload_to='round_documents/', blank=True, null=True, help_text='Upload PDF or image')
    surety_details = models.TextField(blank=True, null=True, help_text='Surety/guarantor details for this round')
    remarks = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.chit_group.name} - Round {self.round_number} ({self.round_date})"

    class Meta:
        verbose_name = 'Chit Round'
        verbose_name_plural = 'Chit Rounds'
        unique_together = [['chit_group', 'round_number']]
        ordering = ['chit_group', 'round_number']


class Payment(models.Model):
    STATUS_CHOICES = [
        ('paid', 'Paid'),
        ('pending', 'Pending'),
        ('late', 'Late'),
    ]

    membership = models.ForeignKey(ChitMembership, on_delete=models.PROTECT, related_name='payments')
    chit_round = models.ForeignKey(ChitRound, on_delete=models.PROTECT, related_name='payments')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    paid_date = models.DateField(blank=True, null=True)
    is_winner_payment = models.BooleanField(default=False, help_text='True if this is the winner\'s discounted payment')
    penalty_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    receipt_number = models.CharField(max_length=50, blank=True, null=True, unique=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.membership.member.name} - Round {self.chit_round.round_number} - ₹{self.amount_paid}"

    class Meta:
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        ordering = ['-chit_round__round_date']

