from rest_framework import permissions

class IsAdmin(permissions.BasePermission):
    """
    Custom permission to only allow admins to access the view.
    """

    def has_permission(self, request, view):
        # Allow access only to users with the 'admin' role
        return request.user.role == 'admin'

class IsUser(permissions.BasePermission):
    """
    Custom permission to only allow users with the 'user' role to access the view.
    """

    def has_permission(self, request, view):
        return request.user.role == 'user'
