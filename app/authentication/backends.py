from django.db.models import Q
from django.contrib.auth.backends import ModelBackend

from .models import Member


class EmailOrUsernameModelBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            user = Member.objects.get(
                Q(username__iexact=username) | Q(email__iexact=username))

            if user.check_password(password):
                return user
        except Member.DoesNotExist:
            return None

    def get_user(self, user_id):
        try:
            return Member.objects.get(pk=user_id)
        except Member.DoesNotExist:
            return None
