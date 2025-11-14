from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone
from datetime import timedelta
import uuid

class Customer(models.Model):
    """Customer model to store customer information"""
    
    GENDER_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=15)
    email = models.EmailField(unique=True)
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    id_proof_type = models.CharField(max_length=50)
    id_proof_number = models.CharField(max_length=50)
    id_proof_document = models.FileField(upload_to='id_proofs/', null=True, blank=True)
    address_proof_document = models.FileField(upload_to='address_proofs/', null=True, blank=True)
    photo = models.ImageField(upload_to='customer_photos/', null=True, blank=True)
    date_of_birth = models.DateField()
    occupation = models.CharField(max_length=100)
    income = models.DecimalField(max_digits=15, decimal_places=2)
    custom_interest_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, 
                                              help_text="Custom interest rate per lakh (leave blank for standard rate)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def interest_rate(self):
        """Get the customer's interest rate (custom or standard)"""
        if self.custom_interest_rate is not None:
            return self.custom_interest_rate
        return 500  # Standard rate
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['phone_number']),
            models.Index(fields=['email']),
        ]


class Loan(models.Model):
    """Loan model to manage loan details"""
    
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('DISBURSED', 'Disbursed'),
        ('COMPLETED', 'Completed'),
        ('DEFAULTED', 'Defaulted'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loan_number = models.CharField(max_length=10, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='loans')
    principal_amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0.01)])
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=500.00)  # Fixed 500 per lakh
    total_installments = models.PositiveIntegerField(default=20)  # Can be 10 or 20
    advance_installments = models.PositiveIntegerField(default=3)  # Fixed 3 advance installments
    installment_amount = models.DecimalField(max_digits=15, decimal_places=2)
    approval_date = models.DateTimeField(null=True, blank=True)
    disbursement_date = models.DateTimeField(null=True, blank=True)
    first_payment_date = models.DateField(null=True, blank=True)
    completion_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    is_advance_paid = models.BooleanField(default=False)
    remaining_installments = models.PositiveIntegerField(default=20)
    notes = models.TextField(blank=True, null=True)
    is_advance_refunded = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Loan #{self.loan_number} - {self.customer.full_name}"
    
    def save(self, *args, **kwargs):
        # Calculate installment amount if not set
        if not self.installment_amount:
            # Import Decimal for precision
            from decimal import Decimal, ROUND_HALF_UP
            
            # Calculate lakhs (1 lakh = 100,000)
            lakhs = self.principal_amount / Decimal('100000')
            
            # Calculate monthly interest based on lakhs (₹500 per lakh)
            monthly_interest = lakhs * Decimal('500')
            
            # Calculate principal per month based on total installments (10 or 20)
            principal_per_month = self.principal_amount / Decimal(self.total_installments)
            
            # Calculate total installment amount with proper rounding
            installment_amount = (principal_per_month + monthly_interest).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            
            self.installment_amount = installment_amount
            
        # Set remaining installments to match total when creating new loan
        if not self.pk:  # If this is a new loan
            self.remaining_installments = self.total_installments
    
        super().save(*args, **kwargs)
    
    def approve_loan(self, approved_by):
        self.status = 'APPROVED'
        self.approval_date = timezone.now()
        self.save()
        
        # Create a loan activity record
        LoanActivity.objects.create(
            loan=self,
            activity_type='LOAN_APPROVED',
            performed_by=approved_by,
            notes=f"Loan approved by {approved_by.get_full_name()}"
        )
    
    def disburse_loan(self, disbursed_by):
        # Check if advance installments are paid
        if not self.is_advance_paid:
            raise ValueError("Advance installments must be paid before disbursement")
        
        self.status = 'DISBURSED'
        self.disbursement_date = timezone.now()
        self.first_payment_date = (timezone.now() + timedelta(days=30)).date()
        
        # When the loan is disbursed, set the remaining installments to total - advance
        self.remaining_installments = self.total_installments - self.advance_installments
        
        self.save()
        
        # Create a loan activity record
        LoanActivity.objects.create(
            loan=self,
            activity_type='LOAN_DISBURSED',
            performed_by=disbursed_by,
            notes=f"Loan disbursed by {disbursed_by.get_full_name()}"
        )

    def complete_early(self, completed_by, notes=""):
        """Mark a loan as completed early"""
        self.status = 'COMPLETED'
        self.completion_date = timezone.now()
        self.remaining_installments = 0
        self.save()
        
        # Create a loan activity record for early completion
        LoanActivity.objects.create(
            loan=self,
            activity_type='LOAN_COMPLETED',
            performed_by=completed_by,
            notes=f"Loan completed early: {notes}"
        )
    
        return True
    
    def complete_loan(self):
        self.status = 'COMPLETED'
        self.completion_date = timezone.now()
        self.remaining_installments = 0
        self.save()
    
    def is_late_payment_allowed(self):
        """Check if late payment is allowed by admin"""
        return LoanActivity.objects.filter(
            loan=self,
            activity_type='LATE_PAYMENT_APPROVED',
            is_active=True
        ).exists()
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['loan_number']),
            models.Index(fields=['status']),
        ]


class Payment(models.Model):
    """Payment model to track loan payments"""
    
    PAYMENT_STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('LATE', 'Late'),
    )
    
    PAYMENT_METHOD_CHOICES = (
        ('CASH', 'Cash'),
        ('UPI', 'UPI'),
        ('BANK_TRANSFER', 'Bank Transfer'),
        ('CHEQUE', 'Cheque'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='payments')
    payment_number = models.PositiveIntegerField()  # Installment number
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    payment_date = models.DateTimeField(default=timezone.now)  # Changed from auto_now_add=True to allow manual entry
    due_date = models.DateField()
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    payment_proof = models.FileField(upload_to='payment_proofs/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='PENDING')
    is_advance_payment = models.BooleanField(default=False)
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Payment #{self.payment_number} for Loan #{self.loan.loan_number}"
    
    def is_late(self):
        return timezone.now().date() > self.due_date


class LoanActivity(models.Model):
    """Track all activities related to a loan"""
    
    ACTIVITY_TYPE_CHOICES = (
        ('LOAN_APPLIED', 'Loan Applied'),
        ('LOAN_APPROVED', 'Loan Approved'),
        ('LOAN_REJECTED', 'Loan Rejected'),
        ('LOAN_DISBURSED', 'Loan Disbursed'),
        ('PAYMENT_RECEIVED', 'Payment Received'),
        ('PAYMENT_FAILED', 'Payment Failed'),
        ('LATE_PAYMENT_APPROVED', 'Late Payment Approved'),
        ('LOAN_COMPLETED', 'Loan Completed'),
        ('LOAN_DEFAULTED', 'Loan Defaulted'),
        ('NOTE_ADDED', 'Note Added'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=30, choices=ACTIVITY_TYPE_CHOICES)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    performed_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.activity_type} for Loan #{self.loan.loan_number}"
    
    class Meta:
        ordering = ['-performed_at']
        verbose_name_plural = 'Loan Activities'
