from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from .models import UserProfile, ActivityLog
from .forms import UserRegistrationForm, UserLoginForm, UserProfileForm, PasswordChangeForm

def login_view(request):
    """Handle user login"""
    
    # Redirect if user is already logged in
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = UserLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                login(request, user)
                
                # Log the activity
                ActivityLog.objects.create(
                    user=user,
                    action='Logged in',
                    ip_address=get_client_ip(request)
                )
                
                # Redirect to the page user was trying to access or dashboard
                next_page = request.GET.get('next', 'dashboard')
                return redirect(next_page)
            else:
                messages.error(request, 'Invalid username or password.')
    else:
        form = UserLoginForm()
    
    return render(request, 'accounts/login.html', {'form': form})

def logout_view(request):
    """Handle user logout"""
    
    if request.user.is_authenticated:
        # Log the activity
        ActivityLog.objects.create(
            user=request.user,
            action='Logged out',
            ip_address=get_client_ip(request)
        )
        
        logout(request)
        messages.success(request, 'You have been logged out successfully.')
    
    return redirect('login')

@login_required
def profile_view(request):
    """Display and update user profile"""
    
    user = request.user
    
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        # Create profile if it doesn't exist
        profile = UserProfile.objects.create(user=user)
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            
            # Update User model fields
            user.first_name = request.POST.get('first_name')
            user.last_name = request.POST.get('last_name')
            user.email = request.POST.get('email')
            user.save()
            
            # Log the activity
            ActivityLog.objects.create(
                user=user,
                action='Updated profile',
                ip_address=get_client_ip(request)
            )
            
            messages.success(request, 'Your profile has been updated successfully.')
            return redirect('profile')
    else:
        form = UserProfileForm(instance=profile, initial={
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email
        })
    
    context = {
        'form': form,
        'user': user,
        'profile': profile
    }
    
    return render(request, 'accounts/profile.html', context)

@login_required
def change_password(request):
    """Change user password"""
    
    if request.method == 'POST':
        form = PasswordChangeForm(request.POST)
        if form.is_valid():
            user = request.user
            current_password = form.cleaned_data['current_password']
            
            # Verify current password
            if user.check_password(current_password):
                new_password = form.cleaned_data['new_password']
                user.set_password(new_password)
                user.save()
                
                # Log the activity
                ActivityLog.objects.create(
                    user=user,
                    action='Changed password',
                    ip_address=get_client_ip(request)
                )
                
                messages.success(request, 'Your password has been changed successfully. Please login again.')
                return redirect('login')
            else:
                messages.error(request, 'Current password is incorrect.')
    else:
        form = PasswordChangeForm()
    
    return render(request, 'accounts/change_password.html', {'form': form})

@login_required
def activity_logs(request):
    """Display user activity logs"""
    
    # Only administrators can see all logs
    if request.user.profile.is_admin:
        logs = ActivityLog.objects.all().order_by('-timestamp')
    else:
        logs = ActivityLog.objects.filter(user=request.user).order_by('-timestamp')
    
    return render(request, 'accounts/activity_logs.html', {'logs': logs})

def register_user(request):
    """Register a new user"""
    
    # Only allow registration if user is an admin
    if not request.user.is_authenticated or not request.user.profile.is_admin:
        messages.error(request, 'You do not have permission to register new users.')
        return redirect('login')
    
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Check if the user already has a profile
            try:
                profile = user.profile
                # Update existing profile
                profile.role = form.cleaned_data['role']
                profile.phone_number = form.cleaned_data['phone_number']
                profile.save()
            except:
                # Create user profile only if it doesn't exist
                UserProfile.objects.create(
                    user=user,
                    role=form.cleaned_data['role'],
                    phone_number=form.cleaned_data['phone_number']
                )
            
            # Log the activity
            ActivityLog.objects.create(
                user=request.user,
                action=f'Registered new user: {user.username}',
                ip_address=get_client_ip(request)
            )
            
            messages.success(request, f'User {user.username} has been registered successfully.')
            return redirect('dashboard')
    else:
        form = UserRegistrationForm()
    
    return render(request, 'accounts/register.html', {'form': form})

def get_client_ip(request):
    """Helper function to get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip