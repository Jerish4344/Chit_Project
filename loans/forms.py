from django import forms
from .models import Customer, Loan, Payment
from django.utils import timezone
from datetime import timedelta

class CustomerForm(forms.ModelForm):
    """Form for creating and updating customer information"""
    
    class Meta:
        model = Customer
        exclude = ['user', 'created_at', 'updated_at', 'is_active']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 3}),
            'custom_interest_rate': forms.NumberInput(attrs={'min': '0', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes to all form fields
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
            if field_name in ['id_proof_document', 'address_proof_document', 'photo']:
                field.widget.attrs['class'] = 'form-control-file'
        
        # Make custom interest rate optional and provide help text
        self.fields['custom_interest_rate'].required = False
        self.fields['custom_interest_rate'].help_text = 'Custom interest rate per lakh (leave blank for standard rate of ₹500)'


class LoanApplicationForm(forms.ModelForm):
    """Form for creating a new loan application"""
    
    PRINCIPAL_CHOICES = [
        (100000, '₹1,00,000 (1 Lakh)'),
        (200000, '₹2,00,000 (2 Lakhs)'),
        (300000, '₹3,00,000 (3 Lakhs)'),
        (400000, '₹4,00,000 (4 Lakhs)'),
        (500000, '₹5,00,000 (5 Lakhs)'),
        (600000, '₹6,00,000 (6 Lakhs)'),
        (700000, '₹7,00,000 (7 Lakhs)'),
        (800000, '₹8,00,000 (8 Lakhs)'),
        (900000, '₹9,00,000 (9 Lakhs)'),
        (1000000, '₹10,00,000 (10 Lakhs)'),
    ]
    
    INSTALLMENT_PLAN_CHOICES = [
        (20, '20 Installments - Standard Plan'),
        (10, '10 Installments - Fast Repayment Plan'),
    ]
    
    principal_amount = forms.ChoiceField(choices=PRINCIPAL_CHOICES, label='Loan Amount')
    installment_plan = forms.ChoiceField(choices=INSTALLMENT_PLAN_CHOICES, label='Repayment Plan')
    
    class Meta:
        model = Loan
        fields = ['principal_amount', 'installment_plan', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, customer=None, **kwargs):
        self.customer = customer
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes to all form fields
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
    
    def clean_principal_amount(self):
        # Convert string to decimal
        return int(self.cleaned_data['principal_amount'])
    
    def clean_installment_plan(self):
        # Convert string to int
        return int(self.cleaned_data['installment_plan'])
    
    def save(self, commit=True):
        loan = super().save(commit=False)
        
        # Set interest rate - use customer's custom rate if available
        if self.customer and self.customer.custom_interest_rate is not None:
            loan.interest_rate = self.customer.custom_interest_rate
        else:
            loan.interest_rate = 500  # Standard rate
        
        # Set total installments based on selected plan
        loan.total_installments = self.cleaned_data['installment_plan']
        
        # Calculate installment amount based on plan
        principal = self.cleaned_data['principal_amount']
        total_installments = self.cleaned_data['installment_plan']
        
        # Import for safe decimal calculation
        from decimal import Decimal, ROUND_HALF_UP
        
        # Calculate lakhs (1 lakh = 100,000)
        lakhs = Decimal(principal) / Decimal('100000')
        
        # Calculate monthly interest based on lakhs and the customer's interest rate
        monthly_interest = lakhs * Decimal(str(loan.interest_rate))
        
        # Calculate principal per month
        principal_per_month = Decimal(principal) / Decimal(total_installments)
        
        # Calculate total installment amount
        installment_amount = (principal_per_month + monthly_interest).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        
        loan.installment_amount = installment_amount
        
        if commit:
            loan.save()
        
        return loan


class LoanApprovalForm(forms.ModelForm):
    """Form for approving or rejecting a loan application"""
    
    APPROVAL_CHOICES = [
        ('APPROVED', 'Approve Loan'),
        ('REJECTED', 'Reject Loan'),
    ]
    
    approval_decision = forms.ChoiceField(choices=APPROVAL_CHOICES, label='Decision')
    
    class Meta:
        model = Loan
        fields = ['notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Provide a reason for your decision'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes to all form fields
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
        self.fields['approval_decision'].widget.attrs['class'] = 'form-select'


class PaymentForm(forms.ModelForm):
    """Form for recording a payment"""
    
    # Add a specific field for payment_date that will use a date picker
    payment_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=False,
        help_text="Leave blank to use current date and time"
    )
    
    class Meta:
        model = Payment
        fields = ['amount', 'payment_method', 'transaction_id', 'payment_proof', 'notes', 'payment_date']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, loan=None, payment_number=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes to all form fields
        for field_name, field in self.fields.items():
            if field_name == 'payment_proof':
                field.widget.attrs['class'] = 'form-control-file'
            else:
                field.widget.attrs['class'] = 'form-control'
        
        self.fields['payment_method'].widget.attrs['class'] = 'form-select'
        
        # Set default payment date to today
        self.fields['payment_date'].initial = timezone.now().date()
        
        # Set default amount if loan is provided
        if loan:
            self.fields['amount'].initial = loan.installment_amount
            self.fields['amount'].widget.attrs['readonly'] = True
            self.instance.loan = loan
            
            if payment_number:
                self.instance.payment_number = payment_number
                # Calculate due date based on loan disbursement date and payment number
                if loan.disbursement_date:
                    if payment_number <= loan.advance_installments:
                        # For advance payments, due date is current date
                        self.instance.due_date = timezone.now().date()
                        self.instance.is_advance_payment = True
                    else:
                        # For regular payments, due date is disbursement date + (payment_number - advance_installments) months
                        months_after = payment_number - loan.advance_installments
                        self.instance.due_date = (loan.disbursement_date + timedelta(days=30 * months_after)).date()
                else:
                    # If loan not yet disbursed, all payments are advance payments
                    self.instance.due_date = timezone.now().date()
                    self.instance.is_advance_payment = True


class LatePaymentApprovalForm(forms.Form):
    """Form for approving late payments"""
    
    reason = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Reason for allowing late payment'}),
        label='Reason for Late Payment'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes to all form fields
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'