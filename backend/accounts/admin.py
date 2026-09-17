from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .demo_users import DEMO_PASSWORD, demo_users_enabled, is_demo_identity
from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ("id", "username", "email", "nickname", "is_staff", "is_active", "date_joined")
    search_fields = ("username", "email", "nickname")

    def get_list_display(self, request):
        fields = super().get_list_display(request)
        return (*fields, "demo_password") if demo_users_enabled() else fields

    @admin.display(description="더미 비밀번호")
    def demo_password(self, user):
        return DEMO_PASSWORD if is_demo_identity(user) else ""
