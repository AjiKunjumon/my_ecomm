import json
import logging
import os
import urllib.request as ur

from PIL import Image
from django.core import signing
from django.utils.decorators import method_decorator
from django.views import View
from django.conf import settings
from django.http import HttpResponse, JsonResponse, HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.response import Response

from app.authentication.models import Member


class HomeView(View):
    def get(self, request):
        settings.SHOULD_REDIRECT = False

        if settings.SITE_CODE == 2 or settings.SITE_CODE == 1:
            return redirect("https://webdev.beconapp.com")

        if settings.SITE_CODE == 3:
            return redirect("https://beconapp.com")


class ResetPassword(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super(ResetPassword, self).dispatch(request, *args, **kwargs)

    def get(self, request, resetPassString):
        try:
            member = Member.objects.get(resetPassString=resetPassString)
        except Member.DoesNotExist:
            member = None
        if member is not None:
            return render(
                request, 'authentication/resetPassword.html',
                {'resetString': resetPassString}
            )
        else:
            return HttpResponseNotFound('<h1>Page not found</h1>')

    def post(self, request, resetPassString):
        try:
            member = Member.objects.get(resetPassString=resetPassString)
        except Member.DoesNotExist:
            member = None
        if member is not None:
            password = request.POST.get('password', None)
            if password is not None:
                member.set_password(password)
                member.resetPassString = None
                member.save()
                status = 'Password changed successfully'
            else:
                status = 'failure'
            return HttpResponse('<h1>' + status + '</h1>')

        else:
            return HttpResponseNotFound('<h1>Page not found</h1>')
