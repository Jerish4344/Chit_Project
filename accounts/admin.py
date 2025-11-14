from django.contrib import admin
from .models import UserProfile, ActivityLog

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'phone_number', 'is_active')
    list_filter = ('role', 'is_active')
    search_fields = ('user__username', 'user__email', 'phone_number')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'role', 'phone_number', 'is_active')
        }),
        ('Personal Information', {
            'fields': ('profile_picture', 'address', 'date_of_birth')
        }),
        ('System Information', {
            'fields': ('created_at', 'updated_at')
        }),
    )

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'ip_address', 'timestamp')
    list_filter = ('user',)
    search_fields = ('user__username', 'action', 'ip_address')
    date_hierarchy = 'timestamp'
    readonly_fields = ('user', 'action', 'ip_address', 'timestamp')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False