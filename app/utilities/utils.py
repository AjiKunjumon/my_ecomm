import json
import time
import requests
from django.contrib.sites.shortcuts import get_current_site

from zappa.async import task

from django.conf import settings


from .helpers import report_to_developer


class QueryLogger:
    def __init__(self, *args, **kwargs):
        self.queries = []

    def __call__(self, execute, sql, params, many, context):
        current_query = {'sql': sql, 'params': params, 'many': many}
        start = time.time()
        try:
            result = execute(sql, params, many, context)
        except Exception as e:
            current_query['status'] = 'error'
            current_query['exception'] = e
            raise
        else:
            current_query['status'] = 'ok'
            return result
        finally:
            duration = time.time() - start
            current_query['duration'] = duration
            self.queries.append(current_query)


def is_email_proper(email):
    try:
        url = "https://api.usebouncer.com/v1/email/verify"
        api_key = "LeefhYMYu6bXtwek22RVtaMu39XPyZ33e4A0vAQQ"
        # api_key = "ma1rwrTWwVnYpPEINv4YniqoLF1KW4pjrSABymka"
        headers = {"x-api-key": api_key}
        # email = "ajipkunjumon@gmail.com"
        params = {"email": email}

        response = requests.get(url, params=params, headers=headers)
        if response.status_code == 200:
            return json.loads(response.content)["status"] == "deliverable"
        return None
    except Exception as e:
        return None


def is_email_valid(email):
    if 'privaterelay.appleid.com' in email:
        return False
    if is_email_proper(email) is not None and is_email_proper(email):
        return True
    return False


def isEnglish(s):
    try:
        s.encode(encoding='utf-8').decode('ascii')
    except UnicodeDecodeError:
        return False
    else:
        return True


def send_sms_for_registration(request, phone):
    protocol = "https" if request.is_secure() else "http"
    root_domain = get_current_site(request).domain
    params = {'phone_number': phone}
    url = "".join([protocol, "://", root_domain]) + "/api/phone/register/"
    r = requests.post(url, params=params)

    print(r.status_code, r.json())


class RoundFloat(float):
    def __new__(cls, value=0, places=2):
        return float.__new__(cls, value)

    def __init__(self, value=0, places=2):
        self.places = str(places)

    def __str__(self):
        return ("%." + self.places + "f") % self

    __repr__ = __str__
