from datetime import date, timedelta
from django.utils import timezone
from .models import Payment, Loan

def calculate_installment_amount(principal, total_installments, interest_rate_per_lakh=500):
    """
    Calculate the installment amount for a loan.
    
    Args:
        principal (Decimal): The principal amount of the loan
        total_installments (int): Total number of installments
        interest_rate_per_lakh (Decimal): Interest rate per lakh (default: 500)
        
    Returns:
        Decimal: The calculated installment amount
    """
    from decimal import Decimal
    
    # Convert principal to lakhs (1 lakh = 100,000)
    principal_in_lakhs = principal / Decimal('100000')
    
    # Calculate monthly interest amount (scales with loan amount)
    monthly_interest = principal_in_lakhs * interest_rate_per_lakh
    
    # Calculate principal per month
    principal_per_month = principal / Decimal(total_installments)
    
    # Calculate total installment amount
    installment_amount = principal_per_month + monthly_interest
    
    return installment_amount.quantize(Decimal('0.01'))

def generate_payment_schedule(loan):
    """
    Generate a payment schedule for a loan.
    
    Args:
        loan (Loan): The loan object
        
    Returns:
        list: A list of payment dictionaries with due dates and amounts
    """
    schedule = []
    
    # Calculate the installment amount
    installment_amount = calculate_installment_amount(
        loan.principal_amount, 
        loan.total_installments, 
        loan.interest_rate
    )
    
    # Handle advance payments
    for i in range(1, loan.advance_installments + 1):
        schedule.append({
            'payment_number': i,
            'due_date': timezone.now().date(),
            'amount': installment_amount,
            'is_advance_payment': True
        })
    
    # If loan is disbursed, calculate remaining payment schedule
    if loan.disbursement_date:
        start_date = loan.disbursement_date.date()
        
        # Handle regular payments
        for i in range(loan.advance_installments + 1, loan.total_installments + 1):
            # Calculate due date (monthly payments)
            due_date = start_date + timedelta(days=30 * (i - loan.advance_installments))
            
            schedule.append({
                'payment_number': i,
                'due_date': due_date,
                'amount': installment_amount,
                'is_advance_payment': False
            })
    
    return schedule

def create_payment_objects(loan):
    """
    Create all Payment objects for a loan based on the payment schedule.
    
    Args:
        loan (Loan): The loan object
    """
    schedule = generate_payment_schedule(loan)
    
    for payment_info in schedule:
        # Check if payment already exists
        existing_payment = Payment.objects.filter(
            loan=loan,
            payment_number=payment_info['payment_number']
        ).exists()
        
        if not existing_payment:
            Payment.objects.create(
                loan=loan,
                payment_number=payment_info['payment_number'],
                amount=payment_info['amount'],
                due_date=payment_info['due_date'],
                status='PENDING',
                is_advance_payment=payment_info['is_advance_payment']
            )

def check_overdue_loans():
    """
    Check for overdue loans based on pending payments.
    
    Returns:
        list: A list of overdue loan objects
    """
    today = timezone.now().date()
    
    # Find loans with payments past due date
    overdue_loans = Loan.objects.filter(
        status='DISBURSED',
        payments__status='PENDING',
        payments__due_date__lt=today
    ).distinct()
    
    return overdue_loans

def get_loan_summary_stats():
    """
    Get summary statistics for all loans.
    
    Returns:
        dict: Dictionary containing summary statistics
    """
    from django.db.models import Sum, Count, Q
    
    active_loans = Loan.objects.filter(status='DISBURSED').count()
    completed_loans = Loan.objects.filter(status='COMPLETED').count()
    pending_loans = Loan.objects.filter(status='PENDING').count()
    
    total_disbursed = Loan.objects.filter(
        status__in=['DISBURSED', 'COMPLETED']
    ).aggregate(
        total=Sum('principal_amount')
    )['total'] or 0
    
    total_collected = Payment.objects.filter(
        status='COMPLETED'
    ).aggregate(
        total=Sum('amount')
    )['total'] or 0
    
    overdue_count = Loan.objects.filter(
        status='DISBURSED',
        payments__status='PENDING',
        payments__due_date__lt=timezone.now().date()
    ).distinct().count()
    
    return {
        'active_loans': active_loans,
        'completed_loans': completed_loans,
        'pending_loans': pending_loans,
        'total_disbursed': total_disbursed,
        'total_collected': total_collected,
        'overdue_count': overdue_count
    }

def check_late_payment_approval(loan):
    """
    Check if late payment is approved for a loan.
    
    Args:
        loan (Loan): The loan object
        
    Returns:
        bool: True if late payment is approved, False otherwise
    """
    from .models import LoanActivity
    
    # Check if there's an active late payment approval
    return LoanActivity.objects.filter(
        loan=loan,
        activity_type='LATE_PAYMENT_APPROVED',
        is_active=True
    ).exists()