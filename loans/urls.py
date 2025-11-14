from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Customer URLs
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/create/', views.customer_create, name='customer_create'),
    path('customers/<uuid:pk>/', views.customer_detail, name='customer_detail'),
    path('customers/<uuid:pk>/update/', views.customer_update, name='customer_update'),
    path('customers/<uuid:pk>/delete/', views.customer_delete, name='customer_delete'),
    
    # Loan URLs
    path('loans/', views.loan_list, name='loan_list'),
    path('customers/<uuid:customer_pk>/loans/create/', views.loan_create, name='loan_create'),
    path('loans/<uuid:pk>/', views.loan_detail, name='loan_detail'),
    path('loans/<uuid:pk>/approve/', views.loan_approve, name='loan_approve'),
    path('loans/<uuid:pk>/disburse/', views.loan_disburse, name='loan_disburse'),
    path('loans/<uuid:loan_pk>/late-payment/', views.approve_late_payment, name='approve_late_payment'),
    path('loans/<uuid:pk>/refund/', views.refund_advance, name='refund_advance'),
    path('loans/<uuid:pk>/delete/', views.loan_delete, name='loan_delete'),
    # Add this URL pattern to your loans/urls.py file
    path('loans/<uuid:pk>/complete-early/', views.complete_loan_early, name='complete_loan_early'),
    
    # Payment URLs
    path('loans/<uuid:loan_pk>/payments/create/', views.payment_create, name='payment_create'),
    path('loans/<uuid:loan_pk>/payments/create/<int:payment_number>/', views.payment_create, name='payment_create_with_number'),
    path('payments/<uuid:pk>/update/', views.payment_update, name='payment_update'),
    path('payments/', views.payment_history, name='payment_history'),

]