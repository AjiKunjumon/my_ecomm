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


def get_fb_params():
    return {"auth": settings.FIREBASE_ACCESS_TOKEN}


def get_fb_params_str_db():
    return {"auth": settings.FIREBASE_DB_STRUCTURING_ACCESS_TOKEN}


def get_fb_params_prod_copy_db():
    return {"auth": settings.FIREBASE_DB_PROD_COPY_ACCESS_TOKEN}


def call_firebase_sync(instance):
    sync_to_fb(
        instance.pk, instance.username, instance.first_name,
        instance.last_name, instance.is_business, instance.business_name(),
        instance.is_private, instance.is_verified, instance.is_business_verified(),
        instance.get_resized_avatar_url(),
        instance.get_fcm_token_list()
    )


@task
def sync_to_fb(
        pk, uname, fname, lname, is_bus, bus_name, is_pri, is_ver, is_bus_ver, avatar, token_list):
    try:
        url = "%susers/%s.json" % (settings.FIREBASE_DBURL, str(pk))

        user_data = {
            "id": pk,
            "username": uname,
            "first_name": fname,
            "last_name": lname,
            "is_business": is_bus,
            "business_name": bus_name,
            "is_private": is_pri,
            "is_verified": is_ver,
            "is_business_verified": is_bus_ver,
            "resized_avatar": avatar,
            "tokens": token_list
        }
        if settings.SITE_CODE == 2:
            url_str = "%susers/%s.json" % (settings.FIREBASE_DB_STRUCTURING_URL, str(pk))
            user_data_str = {
                "id": pk,
                "username": uname,
                "first_name": fname,
                "last_name": lname,
                "is_business": is_bus,
                "business_name": bus_name,
                "is_private": is_pri,
                "is_verified": is_ver,
                "is_business_verified": is_bus_ver,
                "resized_avatar": avatar,
                "tokens": token_list
            }
            requests.patch(url_str, data=json.dumps(user_data_str), params=get_fb_params_str_db())

        if settings.SITE_CODE == 3:
            url_prod_copy = "%susers/%s.json" % (settings.FIREBASE_DB_PROD_COPY_URL, str(pk))
            user_data_prod_copy = {
                "id": pk,
                "username": uname,
                "first_name": fname,
                "last_name": lname,
                "is_business": is_bus,
                "business_name": bus_name,
                "is_private": is_pri,
                "is_verified": is_ver,
                "is_business_verified": is_bus_ver,
                "resized_avatar": avatar,
                "tokens": token_list
            }
            requests.patch(
                url_prod_copy, data=json.dumps(user_data_prod_copy),
                params=get_fb_params_prod_copy_db())
        requests.patch(url, data=json.dumps(user_data), params=get_fb_params())
        return True
    except Exception as e:
        # report_to_developer("Failed to sync user %s" % pk, str(e))
        return False


def is_email_proper(email):
    # url = "https://api.zerobounce.net/v2/validate"
    # api_key = "5fde4a1b9d4b48b0a210e9c893356877"
    # email = "invalid@example.com"
    # ip_address = "99.123.12.122"  # ip_address can be blank
    #
    # params = {"email": email, "api_key": api_key, "ip_address": ''}

    # response = requests.get(url, params=params)
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


# def is_email_valid(json):
#     if is_email_proper(email) is not None and is_email_proper(email):
#         return True
#     return False


def isEnglish(s):
    try:
        s.encode(encoding='utf-8').decode('ascii')
    except UnicodeDecodeError:
        return False
    else:
        return True


# def send_sms_aws_pinpoint():
#     import boto3
#     from botocore.exceptions import ClientError
#
#     # The AWS Region that you want to use to send the message. For a list of
#     # AWS Regions where the Amazon Pinpoint API is available, see
#     # https://docs.aws.amazon.com/pinpoint/latest/apireference/
#     region = "eu-west-1"
#
#     # The phone number or short code to send the message from. The phone number
#     # or short code that you specify has to be associated with your Amazon Pinpoint
#     # account. For best results, specify long codes in E.164 format.
#     originationNumber = "+12065550199"
#
#     # The recipient's phone number.  For best results, you should specify the
#     # phone number in E.164 format.
#     destinationNumber = "+96597724601"
#
#     # The content of the SMS message.
#     message = ("This is a sample message sent from Amazon Pinpoint by using the "
#                "AWS SDK for Python (Boto 3).")
#
#     # The Amazon Pinpoint project/application ID to use when you send this message.
#     # Make sure that the SMS channel is enabled for the project or application
#     # that you choose.
#     applicationId = "2d579aa19e5942d3bca35b377bfbd9cc"
#
#     # The type of SMS message that you want to send. If you plan to send
#     # time-sensitive content, specify TRANSACTIONAL. If you plan to send
#     # marketing-related content, specify PROMOTIONAL.
#     messageType = "TRANSACTIONAL"
#
#     # The registered keyword associated with the originating short code.
#     registeredKeyword = "myKeyword"
#
#     # The sender ID to use when sending the message. Support for sender ID
#     # varies by country or region. For more information, see
#     # https://docs.aws.amazon.com/pinpoint/latest/userguide/channels-sms-countries.html
#     senderId = "Becon"
#
#     # Create a new client and specify a region.
#     client = boto3.client('pinpoint', region_name=region)
#     try:
#         response = client.send_messages(
#             ApplicationId=applicationId,
#             MessageRequest={
#                 'Addresses': {
#                     destinationNumber: {
#                         'ChannelType': 'SMS'
#                     }
#                 },
#                 'MessageConfiguration': {
#                     'SMSMessage': {
#                         'Body': message,
#                         'Keyword': registeredKeyword,
#                         'MessageType': messageType,
#                         'OriginationNumber': originationNumber,
#                         'SenderId': senderId
#                     }
#                 }
#             }
#         )
#
#     except ClientError as e:
#         print(e.response['Error']['Message'])
#     else:
#         print("Message sent! Message ID: "
#               + response['MessageResponse']['Result'][destinationNumber]['MessageId'])


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
