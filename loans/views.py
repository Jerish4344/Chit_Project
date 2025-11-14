from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.http import HttpResponseForbidden
from django.core.paginator import Paginator
from .models import Customer, Loan, Payment, LoanActivity
from .forms import CustomerForm, LoanApplicationForm, LoanApprovalForm, PaymentForm, LatePaymentApprovalForm
from accounts.models import ActivityLog
from decimal import Decimal, ROUND_HALF_UP


@login_required
def dashboard(request):
    """Dashboard view with summary statistics"""
    
    # Get summary statistics
    total_customers = Customer.objects.filter(is_active=True).count()
    active_loans = Loan.objects.filter(status='DISBURSED').count()
    completed_loans = Loan.objects.filter(status='COMPLETED').count()
    pending_loans = Loan.objects.filter(status='PENDING').count()
    
    # Calculate total disbursed, accounting for refunds
    disbursed_loans = Loan.objects.filter(status__in=['DISBURSED', 'COMPLETED'])
    total_disbursed = disbursed_loans.aggregate(total=Sum('principal_amount'))['total'] or 0
    
    # Calculate total collected, accounting for refunds (negative payments)
    total_collected = Payment.objects.filter(status='COMPLETED').aggregate(total=Sum('amount'))['total'] or 0
    
    # Rest of your dashboard view code...
    
    context = {
        'total_customers': total_customers,
        'active_loans': active_loans,
        'completed_loans': completed_loans,
        'pending_loans': pending_loans,
        'total_disbursed': total_disbursed,
        'total_collected': total_collected,
        # Other context variables...
    }
    
    return render(request, 'loans/dashboard.html', context)

@login_required
def customer_list(request):
    """View to display a list of all customers"""
    
    # Get filter parameters
    search_query = request.GET.get('search', '')
    
    # Filter customers based on search query
    if search_query:
        customers = Customer.objects.filter(
            Q(first_name__icontains=search_query) | 
            Q(last_name__icontains=search_query) | 
            Q(phone_number__icontains=search_query) | 
            Q(email__icontains=search_query)
        ).order_by('-created_at')
    else:
        customers = Customer.objects.all().order_by('-created_at')
    
    # Pagination
    paginator = Paginator(customers, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
    }
    
    return render(request, 'loans/customer_list.html', context)

@login_required
def customer_create(request):
    """View to create a new customer"""
    
    if request.method == 'POST':
        form = CustomerForm(request.POST, request.FILES)
        if form.is_valid():
            customer = form.save()
            messages.success(request, f'Customer {customer.full_name} created successfully.')
            
            # Log the activity
            ActivityLog.objects.create(
                user=request.user,
                action=f'Created customer: {customer.full_name}',
                ip_address=get_client_ip(request)
            )
            
            return redirect('customer_detail', pk=customer.pk)
    else:
        form = CustomerForm()
    
    context = {
        'form': form,
        'title': 'Add New Customer',
    }
    
    return render(request, 'loans/customer_form.html', context)

@login_required
def customer_detail(request, pk):
    """View to display customer details"""
    
    customer = get_object_or_404(Customer, pk=pk)
    loans = Loan.objects.filter(customer=customer).order_by('-created_at')
    
    # Calculate loan statistics
    active_loans_count = loans.filter(status='DISBURSED').count()
    completed_loans_count = loans.filter(status='COMPLETED').count()
    
    # Calculate total loan amount
    total_loan_amount = 0
    for loan in loans:
        total_loan_amount += loan.principal_amount
    
    context = {
        'customer': customer,
        'loans': loans,
        'active_loans_count': active_loans_count,
        'completed_loans_count': completed_loans_count,
        'total_loan_amount': total_loan_amount
    }
    
    return render(request, 'loans/customer_detail.html', context)

@login_required
def customer_update(request, pk):
    """View to update an existing customer"""
    
    customer = get_object_or_404(Customer, pk=pk)
    
    if request.method == 'POST':
        form = CustomerForm(request.POST, request.FILES, instance=customer)
        if form.is_valid():
            customer = form.save()
            messages.success(request, f'Customer {customer.full_name} updated successfully.')
            
            # Log the activity
            ActivityLog.objects.create(
                user=request.user,
                action=f'Updated customer: {customer.full_name}',
                ip_address=get_client_ip(request)
            )
            
            return redirect('customer_detail', pk=customer.pk)
    else:
        form = CustomerForm(instance=customer)
    
    context = {
        'form': form,
        'customer': customer,
        'title': 'Update Customer',
    }
    
    return render(request, 'loans/customer_form.html', context)

@login_required
def loan_list(request):
    """View to display a list of all loans"""
    
    # Get filter parameters
    status = request.GET.get('status', '')
    search_query = request.GET.get('search', '')
    
    # Start with all loans
    loans = Loan.objects.select_related('customer').all()
    
    # Apply filters
    if status:
        loans = loans.filter(status=status)
    
    if search_query:
        loans = loans.filter(
            Q(loan_number__icontains=search_query) | 
            Q(customer__first_name__icontains=search_query) | 
            Q(customer__last_name__icontains=search_query) | 
            Q(customer__phone_number__icontains=search_query)
        )
    
    # Order by creation date (newest first)
    loans = loans.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(loans, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status': status,
        'search_query': search_query,
    }
    
    return render(request, 'loans/loan_list.html', context)

@login_required
def loan_create(request, customer_pk):
    """View to create a new loan application"""

    customer = get_object_or_404(Customer, pk=customer_pk)

    if request.method == 'POST':
        form = LoanApplicationForm(request.POST, customer=customer)
        if form.is_valid():
            loan = form.save(commit=False)
            loan.customer = customer

            # Ensure remaining_installments matches total_installments for new loans
            loan.remaining_installments = loan.total_installments

            loan.save()

            # Create a loan activity record
            LoanActivity.objects.create(
                loan=loan,
                activity_type='LOAN_APPLIED',
                performed_by=request.user,
                notes=f"Loan application created by {request.user.get_full_name()}, " +
                      f"plan: {loan.total_installments} installments with interest rate: ₹{loan.interest_rate} per lakh"
            )

            # Log the activity
            ActivityLog.objects.create(
                user=request.user,
                action=f'Created loan application: {loan.loan_number} with {loan.total_installments} installments',
                ip_address=get_client_ip(request)
            )

            messages.success(request, f'Loan application {loan.loan_number} created successfully.')
            return redirect('loan_detail', pk=loan.pk)
    else:
        form = LoanApplicationForm(customer=customer)

    # Check if customer has a custom interest rate
    has_custom_rate = customer.custom_interest_rate is not None

    # Calculate values needed in the template
    interest_value = customer.interest_rate * 2 if has_custom_rate else 1000
    total_value = (10000 + customer.interest_rate) * 2 if has_custom_rate else 11000

    context = {
        'form': form,
        'customer': customer,
        'title': 'Create Loan Application',
        'has_custom_rate': has_custom_rate,
        'interest_rate': customer.interest_rate,
        'interest_value': interest_value,
        'total_value': total_value,
    }

    return render(request, 'loans/loan_form.html', context)

@login_required
def loan_detail(request, pk):
    """View to display loan details"""
    
    loan = get_object_or_404(Loan, pk=pk)
    payments = Payment.objects.filter(loan=loan).order_by('payment_number')
    activities = LoanActivity.objects.filter(loan=loan).order_by('-performed_at')
    
    # Check if all advance payments are made
    advance_payments_completed = payments.filter(
        is_advance_payment=True,
        status='COMPLETED'
    ).count() >= loan.advance_installments
    
    context = {
        'loan': loan,
        'payments': payments,
        'activities': activities,
        'advance_payments_completed': advance_payments_completed,
    }
    
    return render(request, 'loans/loan_detail.html', context)

@login_required
def loan_approve(request, pk):
    """View to approve or reject a loan application"""
    
    loan = get_object_or_404(Loan, pk=pk)
    
    # Check if user has permission to approve loans - handle users without profiles
    if not hasattr(request.user, 'profile'):
        # Create a default profile for admin users
        from accounts.models import UserProfile
        UserProfile.objects.create(
            user=request.user,
            role='ADMIN',
            phone_number='',
            is_active=True
        )
    
    # Now proceed with the check
    if not request.user.profile.is_admin and not request.user.profile.is_manager:
        messages.error(request, 'You do not have permission to approve loans.')
        return redirect('loan_detail', pk=loan.pk)
    
    # Continue with the rest of your function...
    if request.method == 'POST':
        form = LoanApprovalForm(request.POST, instance=loan)
        if form.is_valid():
            decision = form.cleaned_data['approval_decision']
            
            if decision == 'APPROVED':
                loan.status = 'APPROVED'
                loan.approval_date = timezone.now()
                loan.save()
                
                # Create a loan activity record
                LoanActivity.objects.create(
                    loan=loan,
                    activity_type='LOAN_APPROVED',
                    performed_by=request.user,
                    notes=form.cleaned_data['notes'] or f"Loan approved by {request.user.get_full_name()}"
                )
                
                messages.success(request, f'Loan {loan.loan_number} has been approved.')
            else:
                loan.status = 'REJECTED'
                loan.save()
                
                # Create a loan activity record
                LoanActivity.objects.create(
                    loan=loan,
                    activity_type='LOAN_REJECTED',
                    performed_by=request.user,
                    notes=form.cleaned_data['notes'] or f"Loan rejected by {request.user.get_full_name()}"
                )
                
                messages.info(request, f'Loan {loan.loan_number} has been rejected.')
            
            # Log the activity
            try:
                ActivityLog.objects.create(
                    user=request.user,
                    action=f'{decision.capitalize()} loan: {loan.loan_number}',
                    ip_address=get_client_ip(request)
                )
            except:
                # Skip activity logging if it fails
                pass
                
            return redirect('loan_detail', pk=loan.pk)
    else:
        form = LoanApprovalForm(instance=loan)
    
    context = {
        'form': form,
        'loan': loan,
        'title': 'Approve or Reject Loan',
    }
    
    return render(request, 'loans/loan_approval_form.html', context)

@login_required
def loan_disburse(request, pk):
    """View to disburse an approved loan"""
    
    loan = get_object_or_404(Loan, pk=pk)
    
    # Check if user has permission to disburse loans
    if not request.user.profile.is_admin and not request.user.profile.is_manager:
        messages.error(request, 'You do not have permission to disburse loans.')
        return redirect('loan_detail', pk=loan.pk)
    
    # Check if loan is in approved status
    if loan.status != 'APPROVED':
        messages.error(request, 'Only approved loans can be disbursed.')
        return redirect('loan_detail', pk=loan.pk)
    
    # Check if all advance payments are made
    advance_payments_completed = Payment.objects.filter(
        loan=loan,
        is_advance_payment=True,
        status='COMPLETED'
    ).count() >= loan.advance_installments
    
    if not advance_payments_completed:
        messages.error(request, 'All advance installments must be paid before disbursement.')
        return redirect('loan_detail', pk=loan.pk)
    
    if request.method == 'POST':
        loan.status = 'DISBURSED'
        loan.disbursement_date = timezone.now()
        loan.first_payment_date = (timezone.now() + timezone.timedelta(days=30)).date()
        loan.is_advance_paid = True
        
        # Set remaining installments to 17 (after 3 advance payments)
        loan.remaining_installments = loan.total_installments - loan.advance_installments
        
        loan.save()
        
        # Create a loan activity record
        LoanActivity.objects.create(
            loan=loan,
            activity_type='LOAN_DISBURSED',
            performed_by=request.user,
            notes=f"Loan disbursed by {request.user.get_full_name()}"
        )
        
        # Log the activity
        ActivityLog.objects.create(
            user=request.user,
            action=f'Disbursed loan: {loan.loan_number}',
            ip_address=get_client_ip(request)
        )
        
        messages.success(request, f'Loan {loan.loan_number} has been disbursed successfully.')
        return redirect('loan_detail', pk=loan.pk)
    
    context = {
        'loan': loan,
    }
    
    return render(request, 'loans/loan_disburse_confirm.html', context)

# In loans/views.py
@login_required
def refund_advance(request, pk):
    """View to refund advance payments for rejected loans"""
    
    loan = get_object_or_404(Loan, pk=pk)
    
    # Check if user has permission
    if not request.user.profile.is_admin and not request.user.profile.is_manager:
        messages.error(request, 'You do not have permission to process refunds.')
        return redirect('loan_detail', pk=loan.pk)
    
    # Check if loan is rejected and not already refunded
    if loan.status != 'REJECTED' or loan.is_advance_refunded:
        messages.error(request, 'This loan is not eligible for advance refund.')
        return redirect('loan_detail', pk=loan.pk)
    
    if request.method == 'POST':
        # Calculate advance payments amount
        advance_payments = Payment.objects.filter(
            loan=loan,
            is_advance_payment=True,
            status='COMPLETED'
        )
        
        refund_amount = advance_payments.aggregate(total=Sum('amount'))['total'] or 0
        
        if refund_amount > 0:
            # Create a refund record
            refund = Payment.objects.create(
                loan=loan,
                payment_number=0,  # Special number for refund
                amount=-refund_amount,  # Negative amount to indicate refund
                due_date=timezone.now().date(),
                payment_method='CASH',  # Default, can be changed if needed
                status='COMPLETED',
                is_advance_payment=True,
                received_by=request.user,
                notes=f"Refund of advance payments for rejected loan. Processed by {request.user.get_full_name()}"
            )
            
            # Mark loan as refunded
            loan.is_advance_refunded = True
            loan.save()
            
            # Create activity record
            LoanActivity.objects.create(
                loan=loan,
                activity_type='PAYMENT_REFUNDED',
                performed_by=request.user,
                notes=f"Refunded ₹{refund_amount} advance payment to {loan.customer.full_name}"
            )
            
            # Log the activity
            ActivityLog.objects.create(
                user=request.user,
                action=f'Refunded advance payment for loan: {loan.loan_number}',
                ip_address=get_client_ip(request)
            )
            
            messages.success(request, f'Advance payment of ₹{refund_amount} has been refunded.')
        else:
            messages.warning(request, 'No advance payments were found for this loan.')
        
        return redirect('loan_detail', pk=loan.pk)
    
    # If GET request, show confirmation page
    context = {
        'loan': loan,
        'advance_payments': Payment.objects.filter(
            loan=loan,
            is_advance_payment=True,
            status='COMPLETED'
        ),
        'refund_amount': Payment.objects.filter(
            loan=loan,
            is_advance_payment=True,
            status='COMPLETED'
        ).aggregate(total=Sum('amount'))['total'] or 0,
    }
    
    return render(request, 'loans/refund_confirm.html', context)

def payment_create(request, loan_pk, payment_number=None):
    """View to record a new payment"""
    
    loan = get_object_or_404(Loan, pk=loan_pk)
    
    # Determine payment number if not provided
    if payment_number is None:
        # Check if this is an advance payment
        if loan.status in ['PENDING', 'APPROVED']:
            # For a loan not yet disbursed, find the next advance payment number
            advance_payments_completed = Payment.objects.filter(
                loan=loan, 
                is_advance_payment=True, 
                status='COMPLETED'
            ).count()
            
            payment_number = advance_payments_completed + 1
            
            if payment_number > loan.advance_installments:
                messages.error(request, 'All advance installments have already been created.')
                return redirect('loan_detail', pk=loan.pk)
        else:
            # For a disbursed loan, find the next regular payment number
            # First, count advance payments
            advance_payments = loan.advance_installments
            
            # Then count completed regular payments
            regular_payments_completed = Payment.objects.filter(
                loan=loan, 
                is_advance_payment=False, 
                status='COMPLETED'
            ).count()
            
            # Calculate next payment number
            payment_number = advance_payments + regular_payments_completed + 1
            
            if payment_number > loan.total_installments:
                messages.error(request, 'All installments have already been paid.')
                return redirect('loan_detail', pk=loan.pk)
    
    # Check if payment already exists
    existing_payment = Payment.objects.filter(loan=loan, payment_number=payment_number).first()
    if existing_payment:
        if existing_payment.status == 'COMPLETED':
            messages.info(request, f'Payment #{payment_number} has already been completed.')
            return redirect('loan_detail', pk=loan.pk)
        else:
            # If payment exists but not completed, redirect to update view
            return redirect('payment_update', pk=existing_payment.pk)
    
    if request.method == 'POST':
        form = PaymentForm(request.POST, request.FILES, loan=loan, payment_number=payment_number)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.status = 'COMPLETED'  # Mark as completed immediately
            payment.received_by = request.user
            
            # If payment_date is provided in the form, use it
            if 'payment_date' in form.cleaned_data and form.cleaned_data['payment_date']:
                payment.payment_date = form.cleaned_data['payment_date']
            
            payment.save()
            
            # Update loan information
            if payment.is_advance_payment:
                # Check if all advance payments are made
                advance_completed = Payment.objects.filter(
                    loan=loan,
                    is_advance_payment=True,
                    status='COMPLETED'
                ).count() >= loan.advance_installments
                
                if advance_completed:
                    loan.is_advance_paid = True
                    loan.save()
            else:
                # Calculate the accurate count of regular installments paid
                regular_payments_completed = Payment.objects.filter(
                    loan=loan, 
                    is_advance_payment=False, 
                    status='COMPLETED'
                ).count()
                
                # Update remaining installments
                # For regular payments, start with (total - advance) and subtract completed regular payments
                regular_installments_total = loan.total_installments - loan.advance_installments
                loan.remaining_installments = regular_installments_total - regular_payments_completed
                
                # Check if all regular installments have been paid
                if loan.remaining_installments <= 0:
                    loan.status = 'COMPLETED'
                    loan.completion_date = timezone.now()
                    
                    # Create a loan activity for loan completion
                    LoanActivity.objects.create(
                        loan=loan,
                        activity_type='LOAN_COMPLETED',
                        performed_by=request.user,
                        notes=f"Loan completed with final payment by {request.user.get_full_name()}"
                    )
                
                loan.save()
            
            # Create a loan activity record for the payment
            LoanActivity.objects.create(
                loan=loan,
                activity_type='PAYMENT_RECEIVED',
                performed_by=request.user,
                notes=f"Payment #{payment.payment_number} received by {request.user.get_full_name()}"
            )
            
            # Log the activity
            ActivityLog.objects.create(
                user=request.user,
                action=f'Recorded payment #{payment.payment_number} for loan: {loan.loan_number}',
                ip_address=get_client_ip(request)
            )
            
            messages.success(request, f'Payment #{payment.payment_number} recorded successfully.')
            return redirect('loan_detail', pk=loan.pk)
    else:
        form = PaymentForm(loan=loan, payment_number=payment_number)
    
    context = {
        'form': form,
        'loan': loan,
        'payment_number': payment_number,
        'title': f'Record Payment #{payment_number}',
    }
    
    return render(request, 'loans/payment_form.html', context)

@login_required
def payment_update(request, pk):
    """View to update an existing payment"""
    
    payment = get_object_or_404(Payment, pk=pk)
    loan = payment.loan
    
    # Only allow updating pending payments
    if payment.status != 'PENDING':
        messages.error(request, 'Only pending payments can be updated.')
        return redirect('loan_detail', pk=loan.pk)
    
    if request.method == 'POST':
        form = PaymentForm(request.POST, request.FILES, instance=payment, loan=loan, payment_number=payment.payment_number)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.status = 'COMPLETED'
            payment.received_by = request.user
            payment.save()
            
            # Update loan information (same logic as in payment_create)
            if payment.is_advance_payment:
                # Check if all advance payments are made
                advance_completed = Payment.objects.filter(
                    loan=loan,
                    is_advance_payment=True,
                    status='COMPLETED'
                ).count() >= loan.advance_installments
                
                if advance_completed:
                    loan.is_advance_paid = True
                    loan.save()
            else:
                # Regular payment
                if loan.remaining_installments > 0:
                    loan.remaining_installments -= 1
                    loan.save()
                
                # Check if this is the final payment
                if loan.remaining_installments == 0:
                    loan.status = 'COMPLETED'
                    loan.completion_date = timezone.now()
                    loan.save()
                    
                    # Create a loan activity for loan completion
                    LoanActivity.objects.create(
                        loan=loan,
                        activity_type='LOAN_COMPLETED',
                        performed_by=request.user,
                        notes=f"Loan completed with final payment by {request.user.get_full_name()}"
                    )
            
            # Create a loan activity record for the payment
            LoanActivity.objects.create(
                loan=loan,
                activity_type='PAYMENT_RECEIVED',
                performed_by=request.user,
                notes=f"Payment #{payment.payment_number} received by {request.user.get_full_name()}"
            )
            
            # Log the activity
            ActivityLog.objects.create(
                user=request.user,
                action=f'Updated payment #{payment.payment_number} for loan: {loan.loan_number}',
                ip_address=get_client_ip(request)
            )
            
            messages.success(request, f'Payment #{payment.payment_number} updated successfully.')
            return redirect('loan_detail', pk=loan.pk)
    else:
        form = PaymentForm(instance=payment, loan=loan, payment_number=payment.payment_number)
    
    context = {
        'form': form,
        'loan': loan,
        'payment': payment,
        'title': f'Update Payment #{payment.payment_number}',
    }
    
    return render(request, 'loans/payment_form.html', context)

@login_required
def approve_late_payment(request, loan_pk):
    """View to approve a late payment"""
    
    loan = get_object_or_404(Loan, pk=loan_pk)
    
    # Check if user has permission to approve late payments
    if not request.user.profile.is_admin and not request.user.profile.is_manager:
        messages.error(request, 'You do not have permission to approve late payments.')
        return redirect('loan_detail', pk=loan.pk)
    
    if request.method == 'POST':
        form = LatePaymentApprovalForm(request.POST)
        if form.is_valid():
            # Create a loan activity record for late payment approval
            LoanActivity.objects.create(
                loan=loan,
                activity_type='LATE_PAYMENT_APPROVED',
                performed_by=request.user,
                notes=form.cleaned_data['reason']
            )
            
            # Log the activity
            ActivityLog.objects.create(
                user=request.user,
                action=f'Approved late payment for loan: {loan.loan_number}',
                ip_address=get_client_ip(request)
            )
            
            messages.success(request, 'Late payment has been approved.')
            return redirect('loan_detail', pk=loan.pk)
    else:
        form = LatePaymentApprovalForm()
    
    context = {
        'form': form,
        'loan': loan,
        'title': 'Approve Late Payment',
    }
    
    return render(request, 'loans/late_payment_form.html', context)

@login_required
def payment_history(request):
    """View to display payment history"""
    
    # Get filter parameters
    status = request.GET.get('status', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search_query = request.GET.get('search', '')
    
    # Start with all payments
    payments = Payment.objects.select_related('loan', 'loan__customer', 'received_by').all()
    
    # Apply filters
    if status:
        payments = payments.filter(status=status)
    
    if date_from:
        payments = payments.filter(payment_date__gte=date_from)
    
    if date_to:
        payments = payments.filter(payment_date__lte=date_to)
    
    if search_query:
        payments = payments.filter(
            Q(loan__loan_number__icontains=search_query) | 
            Q(loan__customer__first_name__icontains=search_query) | 
            Q(loan__customer__last_name__icontains=search_query) | 
            Q(loan__customer__phone_number__icontains=search_query)
        )
    
    # Order by payment date (newest first)
    payments = payments.order_by('-payment_date')
    
    # Pagination
    paginator = Paginator(payments, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status': status,
        'date_from': date_from,
        'date_to': date_to,
        'search_query': search_query,
    }
    
    return render(request, 'loans/payment_history.html', context)

@login_required
def customer_delete(request, pk):
    """View to delete a customer"""
    
    # Only admins can delete customers
    if not hasattr(request.user, 'profile') or not request.user.profile.is_admin:
        messages.error(request, 'You do not have permission to delete customers.')
        return redirect('customer_list')
    
    customer = get_object_or_404(Customer, pk=pk)
    
    # Check if customer has active loans
    active_loans_count = Loan.objects.filter(
        customer=customer, 
        status__in=['PENDING', 'APPROVED', 'DISBURSED']
    ).count()
    
    if active_loans_count > 0:
        messages.error(request, f'Cannot delete customer with active loans. Please complete or cancel all loans first.')
        return redirect('customer_detail', pk=pk)
    
    if request.method == 'POST':
        customer_name = customer.full_name
        customer.delete()
        
        # Log the activity
        ActivityLog.objects.create(
            user=request.user,
            action=f'Deleted customer: {customer_name}',
            ip_address=get_client_ip(request)
        )
        
        messages.success(request, f'Customer {customer_name} has been deleted successfully.')
        return redirect('customer_list')
    
    context = {
        'customer': customer,
        'active_loans_count': active_loans_count,
    }
    
    return render(request, 'loans/customer_delete_confirm.html', context)

@login_required
def loan_delete(request, pk):
    """View to delete a loan"""
    
    # Only admins can delete loans
    if not hasattr(request.user, 'profile') or not request.user.profile.is_admin:
        messages.error(request, 'You do not have permission to delete loans.')
        return redirect('loan_list')
    
    loan = get_object_or_404(Loan, pk=pk)
    
    # Only allow deleting loans that are not disbursed
    if loan.status == 'DISBURSED':
        messages.error(request, 'Cannot delete a disbursed loan. You must complete or cancel the loan first.')
        return redirect('loan_detail', pk=pk)
    
    if request.method == 'POST':
        customer = loan.customer
        loan_number = loan.loan_number
        loan.delete()
        
        # Log the activity
        ActivityLog.objects.create(
            user=request.user,
            action=f'Deleted loan: {loan_number}',
            ip_address=get_client_ip(request)
        )
        
        messages.success(request, f'Loan {loan_number} has been deleted successfully.')
        return redirect('customer_detail', pk=customer.pk)
    
    context = {
        'loan': loan,
    }
    
    return render(request, 'loans/loan_delete_confirm.html', context)

@login_required
def complete_loan_early(request, pk):
    """View to mark a loan as completed early or convert to 10-installment plan"""
    
    from decimal import Decimal, ROUND_HALF_UP
    
    loan = get_object_or_404(Loan, pk=pk)
    
    # Check if user has permission
    if not request.user.profile.is_admin and not request.user.profile.is_manager:
        messages.error(request, 'You do not have permission to modify loan terms.')
        return redirect('loan_detail', pk=loan.pk)
    
    # Check if loan is in disbursed status
    if loan.status != 'DISBURSED':
        messages.error(request, 'Only disbursed loans can be modified or completed early.')
        return redirect('loan_detail', pk=loan.pk)
    
    if request.method == 'POST':
        notes = request.POST.get('notes', '')
        completion_option = request.POST.get('completion_option', 'standard_early')
        
        # Calculate loan details
        total_installments = loan.total_installments
        installment_amount = loan.installment_amount
        total_expected = total_installments * installment_amount
        
        total_paid = Payment.objects.filter(
            loan=loan,
            status='COMPLETED'
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        # Handle different completion options
        if completion_option == 'ten_installments':
            # Convert to 10-installment plan
            
            # Calculate new plan details
            principal_amount = loan.principal_amount
            lakhs = principal_amount / Decimal('100000')
            monthly_interest = lakhs * Decimal('500')  # ₹500 per lakh per month
            
            # Calculate total for 10 installments (principal + 10 months of interest)
            ten_installment_total = principal_amount + (monthly_interest * 10)
            
            # Calculate how many installments have been paid already
            paid_installments_count = Payment.objects.filter(
                loan=loan,
                status='COMPLETED'
            ).count()
            
            # Determine remaining installments (of the 10 total)
            remaining_installments = max(0, 10 - paid_installments_count)
            
            # Calculate remaining amount to be paid
            remaining_amount = ten_installment_total - total_paid
            
            # Calculate new installment amount (if there are still installments remaining)
            if remaining_installments > 0:
                new_installment_amount = (remaining_amount / Decimal(remaining_installments)).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                )
            else:
                new_installment_amount = Decimal('0.00')
            
            # Update the loan with new terms
            loan.total_installments = 10  # Change to 10 total installments
            loan.remaining_installments = remaining_installments
            loan.installment_amount = new_installment_amount
            loan.save()
            
            # Create an activity record for plan conversion
            LoanActivity.objects.create(
                loan=loan,
                activity_type='LOAN_MODIFIED',
                performed_by=request.user,
                notes=f"Converted to 10-installment plan: {notes}"
            )
            
            # Log the activity
            ActivityLog.objects.create(
                user=request.user,
                action=f'Converted loan {loan.loan_number} to 10-installment plan',
                ip_address=get_client_ip(request)
            )
            
            messages.success(request, f'Loan {loan.loan_number} has been converted to a 10-installment plan successfully.')
            
            # If all 10 installments are already paid, complete the loan
            if remaining_installments == 0:
                loan.status = 'COMPLETED'
                loan.completion_date = timezone.now()
                loan.save()
                
                LoanActivity.objects.create(
                    loan=loan,
                    activity_type='LOAN_COMPLETED',
                    performed_by=request.user,
                    notes=f"Loan completed after conversion to 10-installment plan"
                )
                
                messages.info(request, f'All 10 installments have been paid. The loan has been marked as completed.')
                
        elif completion_option == 'custom_payment':
            # Record a custom final payment and close the loan
            final_payment_amount = request.POST.get('final_payment_amount')
            
            try:
                final_payment_amount = Decimal(final_payment_amount).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                )
                
                # Create the final payment
                next_payment_number = loan.advance_installments + Payment.objects.filter(
                    loan=loan,
                    is_advance_payment=False,
                    status='COMPLETED'
                ).count() + 1
                
                payment = Payment.objects.create(
                    loan=loan,
                    payment_number=next_payment_number,
                    amount=final_payment_amount,
                    due_date=timezone.now().date(),
                    payment_date=timezone.now(),
                    payment_method=request.POST.get('payment_method', 'CASH'),
                    transaction_id=request.POST.get('transaction_id', ''),
                    status='COMPLETED',
                    is_advance_payment=False,
                    received_by=request.user,
                    notes=f"Final payment for early loan completion: {notes}"
                )
                
                # Log the payment activity
                LoanActivity.objects.create(
                    loan=loan,
                    activity_type='PAYMENT_RECEIVED',
                    performed_by=request.user,
                    notes=f"Final payment #{payment.payment_number} of ₹{final_payment_amount} received by {request.user.get_full_name()}"
                )
                
                # Complete the loan
                loan.status = 'COMPLETED'
                loan.completion_date = timezone.now()
                loan.remaining_installments = 0
                loan.save()
                
                # Create completion activity
                LoanActivity.objects.create(
                    loan=loan,
                    activity_type='LOAN_COMPLETED',
                    performed_by=request.user,
                    notes=f"Loan completed early with final payment: {notes}"
                )
                
            except:
                messages.error(request, 'Invalid payment amount. Please enter a valid number.')
                return redirect('complete_loan_early', pk=loan.pk)
                
        else:  # standard_early
            # Standard early completion without additional payment
            loan.status = 'COMPLETED'
            loan.completion_date = timezone.now()
            loan.remaining_installments = 0
            loan.save()
            
            # Create a loan activity record
            LoanActivity.objects.create(
                loan=loan,
                activity_type='LOAN_COMPLETED',
                performed_by=request.user,
                notes=f"Loan completed early: {notes}"
            )
            
            # Log the activity
            ActivityLog.objects.create(
                user=request.user,
                action=f'Completed loan early: {loan.loan_number}',
                ip_address=get_client_ip(request)
            )
            
            messages.success(request, f'Loan {loan.loan_number} has been marked as completed early.')
            
        return redirect('loan_detail', pk=loan.pk)
    
    # Prepare data for the template
    # Calculate standard 20-installment plan details
    total_installments = loan.total_installments
    installment_amount = loan.installment_amount
    total_expected = total_installments * installment_amount
    
    total_paid = Payment.objects.filter(
        loan=loan,
        status='COMPLETED'
    ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    
    remaining_amount = total_expected - total_paid
    
    # Get paid installments count
    paid_installments = Payment.objects.filter(
        loan=loan,
        status='COMPLETED'
    ).count()
    
    pending_installments = loan.total_installments - paid_installments
    
    # Calculate 10-installment plan details
    principal_amount = loan.principal_amount
    lakhs = principal_amount / Decimal('100000')
    monthly_interest = lakhs * Decimal('500')  # ₹500 per lakh per month
    
    # For 10-installment plan: principal + 10 months of interest
    ten_installment_total = principal_amount + (monthly_interest * 10)
    
    # Discount compared to 20-installment plan
    discount_amount = total_expected - ten_installment_total
    
    # Remaining after discount
    ten_installment_remaining = ten_installment_total - total_paid
    
    # Determine remaining installments (of the 10 total)
    remaining_ten_installments = max(0, 10 - paid_installments)
    
    # Calculate new installment amount (if installments remaining)
    if remaining_ten_installments > 0:
        new_installment_amount = (ten_installment_remaining / Decimal(remaining_ten_installments)).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
    else:
        new_installment_amount = Decimal('0.00')
    
    context = {
        'loan': loan,
        'total_expected': total_expected,
        'total_paid': total_paid,
        'remaining_amount': remaining_amount,
        'paid_installments': paid_installments,
        'pending_installments': pending_installments,
        
        # 10-installment plan details
        'ten_installment_total': ten_installment_total,
        'discount_amount': discount_amount,
        'ten_installment_remaining': ten_installment_remaining,
        'remaining_ten_installments': remaining_ten_installments,
        'new_installment_amount': new_installment_amount
    }
    
    return render(request, 'loans/loan_complete_early.html', context)

def get_client_ip(request):
    """Helper function to get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
