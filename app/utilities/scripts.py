import json
import requests

from django.conf import settings

from rest_framework.views import APIView
from rest_framework.response import Response

from .utils import get_fb_params, get_fb_params_str_db


class FirebaseAccess(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        url = "%schatroom.json" % settings.FIREBASE_DBURL
        resp = requests.get(url, params=get_fb_params())
        return Response(json.loads(resp.content))
