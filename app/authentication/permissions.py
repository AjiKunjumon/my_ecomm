from rest_framework.permissions import BasePermission

from app.authentication.models import Member
from app.store.models import Store


class IsSuperAdmin(BasePermission):
    message = "Permission denied"

    def has_permission(self, request, view):
        if request.user.is_authenticated:
            return request.user.is_super_admin
        return False


class IsSuperAdminOrSeller(BasePermission):
    message = "Permission denied"

    def has_permission(self, request, view):
        if request.user.is_authenticated:
            return request.user.is_super_admin or request.user.is_seller
        return False


class IsSuperAdminOrObjectSeller(BasePermission):
    message = "Permission denied"

    def has_permission(self, request, view):
        if request.user.is_authenticated:
            return request.user.is_super_admin or request.user.is_seller
        return False

    def has_object_permission(self, request, view, obj):
        if request.user.is_authenticated:
            conds = [request.user.is_super_admin,
                     request.user == obj.owner(),
                     request.user.id in obj.sub_admins().values_list('member_id', flat=True)]
            filter__true_conds = [x for x in conds if x is True]
            if len(filter__true_conds) >= 1:
                return True
            return False
        return False
