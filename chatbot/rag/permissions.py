from rest_framework import permissions

class IsAdmin(permissions.BasePermission):
    """
    Custom permission to only allow admins to access the view.
    """

    def has_permission(self, request, view):
        # Allow access only to users with the 'admin' role
        return request.user.role == 'admin' or request.user.role == 'superadmin'

# IsUser is deleted since there is no need as using IsAuthenticated corresponds to the same thing.

class IsSuperAdmin(permissions.BasePermission):
    """
    Custom permission to allow only superAdmin to access certain views.
    """

    def has_permission(self, request, view):
        return request.user.role == 'superadmin'