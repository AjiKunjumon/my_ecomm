import math
import os
import re
import json
import time

import boto3
import pytz
import requests
import googlemaps

from io import BytesIO
from random import randint
from geopy.distance import distance
from googleplaces import GooglePlaces
from datetime import date, datetime, timedelta, timezone

from django.conf import settings
from django.core.mail import send_mail
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware, now, timedelta as t_timedelta

from rest_framework.pagination import PageNumberPagination


class EagerLoadingMixin:
    @classmethod
    def setup_eager_loading(cls, queryset):
        if hasattr(cls, "_SELECT_RELATED_FIELDS"):
            queryset = queryset.select_related(*cls._SELECT_RELATED_FIELDS)
        if hasattr(cls, "_PREFETCH_RELATED_FIELDS"):
            queryset = queryset.prefetch_related(*cls._PREFETCH_RELATED_FIELDS)
        return queryset


def paginate(request, queryset, serializer):
    paginator = PageNumberPagination()
    result_page = paginator.paginate_queryset(queryset, request)
    serialize = serializer(result_page, many=True)
    return paginator.get_paginated_response(serialize.data)


def paginate_with_context(request, queryset, serializer, context):
    paginator = PageNumberPagination()
    result_page = paginator.paginate_queryset(queryset, request)
    serialize = serializer(result_page, many=True, context=context)
    return paginator.get_paginated_response(serialize.data)


def reverse_paginate_with_context(request, queryset, serializer, context):
    paginator = PageNumberPagination()
    result_page = paginator.paginate_queryset(queryset, request)
    serialize = serializer(result_page, many=True, context=context)
    return paginator.get_paginated_response(serialize.data)


# def comment_paginate_with_context(request, queryset, serializer, context):
#     paginator = CommentNotificationPagination()
#     result_page = paginator.paginate_queryset(queryset, request)
#     serialize = serializer(result_page, many=True, context=context)
#     return paginator.get_paginated_response(serialize.data)


def paginate_list(request, list_data):
    paginator = PageNumberPagination()
    result_page = paginator.paginate_queryset(list_data, request)
    return paginator.get_paginated_response(result_page)


def date_from_arabic_string(date_string):
    return date(*map(int, date_string.split("-")))


def arabic_to_euro_digits(m):
    return chr(ord(m.group(0)) - 0x630)


def date_time_from_arabic_string(date_string):
    pat = re.compile(u"[\u0660-\u0669]", re.UNICODE)
    s = pat.sub(arabic_to_euro_digits, date_string)
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


def english_date_string(date_string):
    pat = re.compile(u"[\u0660-\u0669]", re.UNICODE)
    return pat.sub(arabic_to_euro_digits, date_string)


def set_image(request, obj):
    for image in request.FILES.getlist("image[]"):
        obj.image = image
    obj.save()


def string_to_date(date_string):
    try:
        return datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def random_with_N_digits(n):
    range_start = 10**(n-1)
    range_end = (10**n)-1
    return randint(range_start, range_end)


def generate_upload_url(file_name, file_type, url):
    s3 = boto3.client('s3')

    bucket_name = settings.AWS_STORAGE_BUCKET_NAME

    presigned_post = s3.generate_presigned_post(
        Bucket=bucket_name,
        Key=file_name,
        Fields={"acl": "public-read", "Content-Type": file_type},
        Conditions=[
            {'acl': "public-read"},
            {"Content-Type": file_type}
        ],
        ExpiresIn=3600
    )

    return json.dumps({'data': presigned_post, 'url': url})


def get_gmap_client():
    return googlemaps.Client(key=settings.GOOGLE_MAPS_API_KEY)


def get_places_client():
    return GooglePlaces(settings.GOOGLE_MAPS_API_KEY)


def get_distance(location1, location2):
    if location1 == (0.0, 0.0) or location2 == (0.0, 0.0):
        return 0.0
    return round(distance(location1, location2).km, ndigits=1)


def get_distance_in_meters(location1, location2):
    if location1 == (0.0, 0.0) or location2 == (0.0, 0.0):
        return 0.0
    return round(distance(location1, location2).m, ndigits=3)


def get_presigned_url(key, file_type):
    bucket = settings.AWS_STORAGE_BUCKET_NAME

    s3 = boto3.client('s3')

    if file_type == "mp4":
        file_type = "video/mp4"

    presigned_post = s3.generate_presigned_post(
        Bucket=bucket,
        Key=key,
        Fields={"acl": "public-read", "Content-Type": file_type},
        Conditions=[
            {"acl": "public-read"},
            {"Content-Type": file_type}
        ],
        ExpiresIn=3600
    )

    return presigned_post


def get_ecomm_prod_media_key_and_path(file_name, file_type):
    key = "media/ecomm_products/medias/%s.%s" % (file_name, file_type)
    if settings.SITE_CODE == 1:
        key = "ecomm_products/medias/%s.%s" % (file_name, file_type)
    path = "ecomm_products/medias/%s.%s" % (file_name, file_type)
    return key, path


def get_post_media_cover_key_and_path(file_name, file_type):
    key = "media/posts/media_cover/%s.%s" % (file_name, file_type)
    if settings.SITE_CODE == 1:
        key = "posts/media_cover/%s.%s" % (file_name, file_type)
    path = "posts/media_cover/%s.%s" % (file_name, file_type)
    return key, path


def local_cover_image_url(file_path):
    return "".join(["http://127.0.0.1:8000", settings.MEDIA_URL, file_path])


def get_member_cover_key_and_path(file_name, file_type):
    key = "media/covers/medias/%s.%s" % (file_name, file_type)
    if settings.SITE_CODE == 1:
        key = "covers/medias/%s.%s" % (file_name, file_type)
    path = "covers/medias/%s.%s" % (file_name, file_type)
    return key, path


def get_member_video_cover_image_key_and_path(file_name, file_type):
    key = "media/covers/vidoecovers/%s.%s" % (file_name, file_type)
    if settings.SITE_CODE == 1:
        key = "covers/vidoecovers/%s.%s" % (file_name, file_type)
    path = "covers/vidoecovers/%s.%s" % (file_name, file_type)
    return key, path


def get_member_profile_photo_key_and_path(file_name, file_type):
    key = "media/members/avatars/%s.%s" % (file_name, file_type)
    if settings.SITE_CODE == 1:
        key = "members/avatars/%s.%s" % (file_name, file_type)
    path = "members/avatars/%s.%s" % (file_name, file_type)
    resized_avatar_path = "members/resized_avatars/%s_resized.%s" % (
        file_name, settings.AVATAR_IMAGE_FORMAT)
    share_avatar_path = "members/share_profile_avatars/%s.%s" % (
        file_name, settings.AVATAR_IMAGE_FORMAT)
    return key, path, resized_avatar_path, share_avatar_path


def get_member_share_profile_photo_key_and_path(file_name, file_type):
    key = "media/members/avatars/%s.%s" % (file_name, file_type)
    if settings.SITE_CODE == 1:
        key = "members/avatars/%s.%s" % (file_name, file_type)
    path = "members/avatars/%s.%s" % (file_name, file_type)
    resized_share_avatar_path = "members/share_profile_avatars/%s.%s" % (
        file_name, settings.AVATAR_IMAGE_FORMAT)
    return key, path, resized_share_avatar_path


def file_url_in_local(url):
    media_root_url = settings.MEDIA_ROOT + "/"
    return url.replace(media_root_url, "")


def upload_image_formats():
    return [".jpg", ".jpeg"]


def upload_video_formats():
    return [".mpeg4"]


def now_minus_2days():
    return make_aware(datetime.now()) - timedelta(days=5)


def nth_day_before_today(n):
    return now() - t_timedelta(days=n)


def nth_day_before_date(date, n):
    return date - t_timedelta(days=n)


def without_comma(with_comma):
    if " , " in with_comma:
        with_comma = with_comma.replace(" , ", " ")
    if ", " in with_comma:
        with_comma = with_comma.replace(", ", " ")
    if " ," in with_comma:
        with_comma = with_comma.replace(" ,", " ")
    return with_comma.replace(",", " ")


def copy_s3_image(key, media_path):
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION
    )

    bucket = settings.AWS_STORAGE_BUCKET_NAME

    outfile = key.split("/")[-1].split(".")[0] + "_tag"
    abs_path = "%s/%s.jpeg" % (media_path, outfile)
    new_key_value = "media/%s" % abs_path

    response = requests.get(key)
    response.raise_for_status()

    with BytesIO(response.content) as output:
        output.seek(0)

        s3_client.put_object(
            ACL="public-read",
            Bucket=bucket, Key=new_key_value,
            Body=output, ContentType="images/jpeg"
        )

    return abs_path


def report_to_developer(subject, problem):
    send_mail(
        subject, problem,
        settings.DEFAULT_FROM_EMAIL, [settings.DEFAULT_REPORTING_EMAIL]
    )


def get_business_cover_key_and_path(file_name, file_type):
    key = "media/business/covers/medias/%s.%s" % (file_name, file_type)
    if settings.SITE_CODE == 1:
        key = "business/covers/medias/%s.%s" % (file_name, file_type)
    path = "business/covers/medias/%s.%s" % (file_name, file_type)
    return key, path


def get_bpartner_iddocument_key_and_path(file_name, file_type):
    key = "media/business/bpartner/medias/%s.%s" % (file_name, file_type)
    if settings.SITE_CODE == 1:
        key = "business/bpartner/medias/%s.%s" % (file_name, file_type)
    path = "business/bpartner/medias/%s.%s" % (file_name, file_type)
    return key, path


def get_blicense_key_and_path(file_name, file_type):
    key = "media/business/blicense/medias/%s.%s" % (file_name, file_type)
    if settings.SITE_CODE == 1:
        key = "business/blicense/medias/%s.%s" % (file_name, file_type)
    path = "business/blicense/medias/%s.%s" % (file_name, file_type)
    return key, path


def get_business_logo_photo_key_and_path(file_name, file_type):
    key = "media/business/logos/%s.%s" % (file_name, file_type)
    if settings.SITE_CODE == 1:
        key = "business/logos/%s.%s" % (file_name, file_type)
    path = "business/logos/%s.%s" % (file_name, file_type)
    resized_logo_path = "business/resized_logos/%s_resized.%s" % (
        file_name, settings.AVATAR_IMAGE_FORMAT)
    return key, path, resized_logo_path


def get_location_logo_photo_key_and_path(file_name, file_type):
    key = "media/locations/uploaded_images/%s.%s" % (file_name, file_type)
    if settings.SITE_CODE == 1:
        key = "locations/uploaded_images/%s.%s" % (file_name, file_type)
    path = "locations/uploaded_images/%s.%s" % (file_name, file_type)
    resized_logo_path = "locations/images/%s_resized.%s" % (
        file_name, settings.AVATAR_IMAGE_FORMAT)
    return key, path, resized_logo_path


def get_day_from_code(code):
    if code == 0:
        return "Sun"
    if code == 1:
        return "Mon"
    if code == 2:
        return "Tue"
    if code == 3:
        return "Wed"
    if code == 4:
        return "Thu"
    if code == 5:
        return "Fri"
    if code == 6:
        return "Sat"


def correct_week_day(code):
    return 0 if code == 6 else code + 1


def get_time_string_from_number(number):
    am_or_pm = "am"
    if number >= 1200:
        am_or_pm = "pm"
    if number > 1200:
        number = number - 1200
    time_string = "1200" if number == 0 else str(number)
    if len(time_string) == 4:
        return "".join(
            [":".join([time_string[:2], time_string[2:]]), am_or_pm]
        )

    time_str1 = time_string[:1]
    time_str2 = time_string[1:]

    if len(time_string[:1]) < 2:
        time_str1 = "0" + time_str1
    if len(time_string[1:]) < 2:
        time_str2 = time_str2 + "0"
    return "".join(
        [":".join([time_str1, time_str2]), am_or_pm]
    )


def last_week_string():
    yesterday = nth_day_before_today(0).strftime("%b %d, %Y")
    past_week_day = nth_day_before_today(6).strftime("%b %d, %Y")
    return "".join(["(", past_week_day, " - ", yesterday, ")"])


def trending_date_range():
    return range(1, 8)[::-1]


def validate_lowercase(value):
    return not any(x.isupper() for x in value)


def get_s3_object(path):
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION
    )

    key = "/".join(["media", path])
    bucket = settings.AWS_STORAGE_BUCKET_NAME
    response = s3_client.get_object(Bucket=bucket, Key=key)
    return response['Body'].read()


def get_firebase_conf():
    base_path = os.path.join(settings.BASE_DIR)
    file_path = "/".join(base_path.split("/")[:-1])
    path = os.path.join(file_path, "app", "utilities", "fire_base_conf.json")
    return json.load(open(path, 'r'))


def day_string(datetime_obj):
    return datetime_obj.strftime("%a")


def last_day_of_month(date_time):
    next_month = date_time.replace(day=28) + t_timedelta(days=4)
    return next_month - t_timedelta(days=next_month.day)


def middle_day_of_month(month, year):
    date_string = "%s-%s-%s 14:00:00" % (year, month, 15)
    return parse_datetime(date_string)


def first_day_of_month(month, year):
    date_string = "%s-%s-%s 14:00:00" % (year, month, 1)
    return parse_datetime(date_string)


def month_date_range(month, year):
    middle_day = middle_day_of_month(month, year)
    return (first_day_of_month(month, year), last_day_of_month(middle_day))


def first_and_last_date_of_year(year):
    first = parse_datetime("%s-01-01 14:00:00" % (year))
    last = parse_datetime("%s-12-31 14:00:00" % (year))
    return first, last


def get_day_number():
    return int(datetime.today().strftime('%w'))


def getDateRangeFromWeek(p_year,p_week):
    firstdayofweek = datetime.strptime(
        f'{p_year}-W{int(p_week )- 1}-1', "%Y-W%W-%w").date()
    lastdayofweek = firstdayofweek + timedelta(days=6.9)
    return firstdayofweek, lastdayofweek

from math import sin, cos, sqrt, atan2, radians

def radial_distance(lat1,lon1,lat2,lon2):
    # approximate radius of earth in km
    R = 6373.0

    radius = 6371  # km

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) * math.sin(dlat / 2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) * math.sin(dlon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    d = radius * c
    print(a)
    print("Result:", d)
    print("Should be:", 278.546, "km")

    return d


def duration_between_datetime(date1, date2):
    date1 = datetime.strptime(
        date1.strftime("%Y-%m-%d %H:%M:%S"), "%Y-%m-%d %H:%M:%S")
    date2 = datetime.strptime(
        date2.strftime("%Y-%m-%d %H:%M:%S"), "%Y-%m-%d %H:%M:%S")
    timedelta = date1 - date2

    return timedelta


def datetime_from_utc_to_local(utc_dt):
    return utc_dt.replace(tzinfo=timezone.utc).astimezone(tz=None)


def datetime_from_utc_to_local_new(utc_dt):
    kuwait_dt_tm = utc_dt.astimezone(pytz.timezone("Asia/Kuwait"))
    return kuwait_dt_tm


def convert_date_time_to_kuwait_string(utc_dt):
    k = datetime_from_utc_to_local_new(utc_dt)
    twentyfour_hr_date_time = datetime.strptime(str(k)[:19], "%Y-%m-%d %H:%M:%S")
    twelve_hr_date_time = twentyfour_hr_date_time.strftime("%b.%d, %Y %I:%M: %p")
    return str(twelve_hr_date_time)


def convert_date_time_to_kuwait_string_date(utc_dt):
    k = datetime_from_utc_to_local_new(utc_dt)
    twentyfour_hr_date_time = datetime.strptime(str(k)[:19], "%Y-%m-%d %H:%M:%S")
    twelve_hr_date_time = twentyfour_hr_date_time.strftime("%d/%m/%Y")
    return str(twelve_hr_date_time)


def convert_date_time_to_kuwait_string_date_readable(utc_dt):
    k = datetime_from_utc_to_local_new(utc_dt)
    twentyfour_hr_date_time = datetime.strptime(str(k)[:19], "%Y-%m-%d %H:%M:%S")
    twelve_hr_date_time = twentyfour_hr_date_time.strftime("%b.%d, %Y")
    return str(twelve_hr_date_time)

def convert_datetime_timezone(dt, tz1, tz2):
    tz1 = pytz.timezone(tz1)
    tz2 = pytz.timezone(tz2)

    dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
    dt = tz1.localize(dt)
    dt = dt.astimezone(tz2)
    dt = dt.strftime("%Y-%m-%d %H:%M:%S")

    return dt


class ArabicConverter:
    regex = '[\u0621-\u064Aa-zA-Z\d\-_\s]'

    def to_python(self, value):
        print(value)
        return value

    def to_url(self, value):
        return '{}'.format(value)


class RomanNumeralConverter:
    regex = '[MDCLXVImdclxvi]+'

    def to_python(self, value):
        return str(value)

    def to_url(self, value):
        return '{}'.format(value)


def list_to_queryset(model, data):
    from django.db.models.base import ModelBase

    if not isinstance(model, ModelBase):
        raise ValueError(
            "%s must be Model" % model
        )
    if not isinstance(data, list):
        raise ValueError(
            "%s must be Dictionary Object" % data
        )

    pk_list = [obj.pk for obj in data]
    return model.objects.filter(pk__in=pk_list)


def calculateAge(birthDate):
    days_in_year = 365.2425
    age = int((date.today() - birthDate).days / days_in_year)
    return age


def str2bool(v):
    try:
        v = str(v)
        v.lower()
        return v.lower() in ("true", "True", "1")
    except Exception as e:
        return v is True


def get_order_perms_for_super_admin():
    order_permissions_for_super_admin = [
        'Can view order', 'Can edit order',
        'Can delete order', 'Can add order',
        'Can add order product', 'Can change order product',
        'Can delete order product', 'Can view order product',
        'Can add order product status track',
        'Can change order product status track',
        'Can delete order product status track',
        'Can view order product status track',
        'Can add order status track',
        'Can change order status track',
        'Can delete order status track',
        'Can view order status track',
        'Can add cancelled order product',
        'Can change cancelled order product',
        'Can delete cancelled order product',
        'Can view cancelled order product',
        'Can add card',
        'Can change card',
        'Can delete card',
        'Can view card'
    ]

    return order_permissions_for_super_admin


def get_product_perms_for_super_admin():
    product_app_labels_for_super_admin = [
        'product'
    ]
    return product_app_labels_for_super_admin


def get_seller_perms_for_super_admin():
    seller_models_for_super_admin = [
        'store', 'address',
        'social media url', 'member',
        'banner', 'city'
    ]
    return seller_models_for_super_admin


def get_users_perms_for_super_admin():
    users_models_for_super_admin = [
        'member', 'FCM device',
        'address'
    ]
    return users_models_for_super_admin


def get_discounts_perms_for_super_admin():
    discount_models_for_super_admin = [
        'coupon'
    ]
    return discount_models_for_super_admin


def get_banners_perms_for_super_admin():
    banner_models_for_super_admin = [
        'banner', 'top deals banner'
    ]
    return banner_models_for_super_admin


def get_perms_for_super_admin(module):
    if module == 'order':
        return get_order_perms_for_super_admin()
    elif module == 'product':
        return get_product_perms_for_super_admin()
    elif module == 'seller':
        return get_seller_perms_for_super_admin()
    elif module == 'user':
        return get_users_perms_for_super_admin()
    elif module == 'discount':
        return get_discounts_perms_for_super_admin()
    elif module == 'banner':
        return get_banners_perms_for_super_admin()
