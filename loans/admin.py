from django.contrib import admin
from .models import Customer, Loan, Payment, LoanActivity

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'phone_number', 'email', 'is_active')
    list_filter = ('is_active', 'gender', 'city', 'state')
    search_fields = ('first_name', 'last_name', 'phone_number', 'email', 'id_proof_number')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'gender', 'date_of_birth', 'phone_number', 'email')
        }),
        ('Address Information', {
            'fields': ('address', 'city', 'state', 'pincode')
        }),
        ('Identification', {
            'fields': ('id_proof_type', 'id_proof_number', 'id_proof_document', 'address_proof_document', 'photo')
        }),
        ('Financial Information', {
            'fields': ('occupation', 'income')
        }),
        ('System Information', {
            'fields': ('user', 'is_active', 'created_at', 'updated_at')
        }),
    )


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ('payment_number', 'amount', 'payment_date', 'status')
    can_delete = False


class LoanActivityInline(admin.TabularInline):
    model = LoanActivity
    extra = 0
    readonly_fields = ('activity_type', 'performed_by', 'performed_at', 'notes')
    can_delete = False


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ('loan_number', 'customer', 'principal_amount', 'status', 'disbursement_date', 'remaining_installments')
    list_filter = ('status', 'is_advance_paid')
    search_fields = ('loan_number', 'customer__first_name', 'customer__last_name', 'customer__phone_number')
    date_hierarchy = 'created_at'
    readonly_fields = ('loan_number', 'created_at', 'updated_at', 'installment_amount')
    inlines = [PaymentInline, LoanActivityInline]
    fieldsets = (
        ('Loan Information', {
            'fields': ('loan_number', 'customer', 'principal_amount', 'interest_rate', 'installment_amount')
        }),
        ('Installment Details', {
            'fields': ('total_installments', 'advance_installments', 'remaining_installments', 'is_advance_paid')
        }),
        ('Status Information', {
            'fields': ('status', 'application_date', 'approval_date', 'disbursement_date', 'first_payment_date', 'completion_date')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('System Information', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('loan', 'payment_number', 'amount', 'payment_date', 'due_date', 'status')
    list_filter = ('status', 'payment_method', 'is_advance_payment')
    search_fields = ('loan__loan_number', 'loan__customer__first_name', 'loan__customer__last_name', 'transaction_id')
    date_hierarchy = 'payment_date'
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Payment Information', {
            'fields': ('loan', 'payment_number', 'amount', 'payment_date', 'due_date', 'status')
        }),
        ('Payment Details', {
            'fields': ('payment_method', 'transaction_id', 'payment_proof', 'is_advance_payment')
        }),
        ('Processing Information', {
            'fields': ('received_by', 'notes')
        }),
        ('System Information', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(LoanActivity)
class LoanActivityAdmin(admin.ModelAdmin):
    list_display = ('loan', 'activity_type', 'performed_by', 'performed_at', 'is_active')
    list_filter = ('activity_type', 'is_active')
    search_fields = ('loan__loan_number', 'notes')
    date_hierarchy = 'performed_at'
    readonly_fields = ('performed_at',)
    fieldsets = (
        ('Activity Information', {
            'fields': ('loan', 'activity_type', 'performed_by', 'performed_at', 'is_active')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
    )