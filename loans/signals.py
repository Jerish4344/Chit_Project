from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.db.models import Max
from django.apps import apps

@receiver(pre_save, sender='loans.Loan')
def set_loan_number(sender, instance, **kwargs):
    """
    Signal to automatically generate loan number based on principal amount
    Format: [Amount in Lakhs]L[Sequence Number]
    Example: 1L0001, 2L0001, etc.
    """
    if not instance.loan_number:
        # Calculate amount in lakhs (1 lakh = 100,000)
        amount_in_lakhs = int(instance.principal_amount / 100000)
        
        # Find the last sequence number for this amount
        prefix = f"{amount_in_lakhs}L"
        Loan = apps.get_model('loans', 'Loan')
        last_loan = Loan.objects.filter(
            loan_number__startswith=prefix
        ).aggregate(
            Max('loan_number')
        )['loan_number__max']
        
        if last_loan:
            # Extract the sequence number and increment
            sequence = int(last_loan[len(prefix):]) + 1
        else:
            # Start with 1 if no previous loans
            sequence = 1
        
        # Format: [Amount in Lakhs]L[4-digit Sequence]
        instance.loan_number = f"{prefix}{sequence:04d}"