from rest_framework.permissions import BasePermission


class ActiveStaffOnly(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user.is_authenticated and user.is_active and user.is_staff)
