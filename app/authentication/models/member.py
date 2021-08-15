from datetime import date

import reverse_geocoder as rg
from django.db.models.signals import post_save
from fcm_django.models import FCMDevice
from geopy import Point
from geopy.geocoders import Nominatim

from phonenumber_field.modelfields import PhoneNumberField

from django.db import models
from django.conf import settings
from django.db.models import Count, F, Q, Sum, CASCADE
from django.utils.timezone import now, timedelta
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from phonenumbers import national_significant_number

from app.authentication.models.managers import MemberManager, MemberQueryset
from app.order.models import CartProduct


class Member(AbstractBaseUser, PermissionsMixin):
    MALE = "M"
    FEMALE = "F"
    NA = "N"
    GENDER_CHOICES = (
        (MALE, "Male"),
        (FEMALE, "Female"),
        (NA, "Not Applicable"),
    )

    STATUS_CHOICES = (
        ('AC', 'Active'),
        ('IN', 'In-Active')
    )
    status = models.CharField(
        max_length=2, default='AC',
        choices=STATUS_CHOICES)

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    full_name = models.CharField(max_length=100)
    username = models.CharField(
        unique=True, max_length=30, blank=True, null=True)
    email = models.EmailField(unique=True)
    birthday = models.DateField(blank=True, null=True)
    gender = models.CharField(
        max_length=1, choices=GENDER_CHOICES, default=MALE)

    phone = PhoneNumberField(blank=True, null=True)
    avatar = models.ImageField(
        upload_to="members/avatars", blank=True, null=True)
    resized_avatar = models.ImageField(
        upload_to="members/resized_avatars", blank=True, null=True)
    share_profile_avatar = models.ImageField(
        upload_to="members/share_profile_avatars", blank=True, null=True)
    beams = models.FloatField(default=0.0)
    title_or_profession = models.CharField(
        max_length=100, blank=True, null=True)
    bio = models.TextField(max_length=100, blank=True, null=True)
    website_url = models.URLField(blank=True, null=True)
    no_of_followers = models.BigIntegerField(default=0)
    no_of_following = models.BigIntegerField(default=0)
    no_of_checked_in_places = models.BigIntegerField(default=0)
    is_beams_public = models.BooleanField(default=False)
    contact_email = models.EmailField(blank=True, null=True)
    country_code = models.CharField(max_length=10, blank=True)
    nationality_code = models.CharField(max_length=100, blank=True, null=True)

    is_verified = models.BooleanField(default=False)
    is_private = models.BooleanField(default=False)
    is_business = models.BooleanField(default=False)
    is_location = models.BooleanField(default=False)
    is_tag = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    has_enabled_public_checkins = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    is_active = models.BooleanField(default=True)
    is_email_verified = models.BooleanField(default=False)

    # optimization fields
    has_checkin_history = models.BooleanField(default=False)
    checkin_notification = models.BooleanField(default=True)

    # beams program
    is_excluded_for_beam_program = models.BooleanField(default=False)
    last_changed_to_public = models.DateTimeField(blank=True, null=True)
    beams_eligibility_email_sent = models.BooleanField(default=False)
    beams_eligibility_email_sent_time = models.DateTimeField(blank=True, null=True)

    last_time_checked_nfs_api = models.DateTimeField(blank=True, null=True)
    last_nfs_posts_count = models.BigIntegerField(default=0)
    money_earned_for_beams = models.FloatField(default=0.00)
    req_money_for_beams = models.FloatField(default=0.00)

    chat_restructure_email_sent = models.BooleanField(default=False)
    can_download_media = models.BooleanField(default=True)

    # ecomm specific fields
    is_mobile_verified = models.BooleanField(default=False)
    is_store_admin = models.BooleanField(default=False)
    is_seller = models.BooleanField(default=False)
    is_super_admin = models.BooleanField(default=False)
    last_login = models.DateTimeField(blank=True, null=True)
    designation = models.CharField(
        max_length=255, blank=True, null=True)
    company = models.CharField(
        max_length=255, blank=True, null=True)
    has_full_access = models.BooleanField(default=False)
    resetPassString = models.CharField(max_length=255, null=True)
    is_from_fb = models.BooleanField(default=False)
    is_from_google = models.BooleanField(default=False)
    is_ecomm_user = models.BooleanField(default=False)
    apple_user_id = models.CharField(
        max_length=100, blank=True, null=True)

    wishlishted_products = models.ManyToManyField(
        "product.EcommProduct", related_name="wishlishted_products",
        blank=True)
    search_keywords = models.ManyToManyField(
        "product.SearchKeyWord", related_name="search_keywords",
        blank=True)

    objects = MemberManager()
    members = MemberQueryset.as_manager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = (
        "first_name", "last_name", "email", "birthday", "gender",
    )

    def get_latest_fcm_device(self):
        fcm_devices = FCMDevice.objects.filter(
            user=self,
            active=True
        )
        if fcm_devices.exists():
            fcm_device = fcm_devices.latest('id')
            return fcm_device
        return None

    def get_full_name(self):
        return " ".join([
            self.first_name.capitalize(), self.last_name.capitalize()
        ])

    def get_exact_full_name(self):
        if self.full_name == "":
            return self.get_full_name()
        return self.full_name

    def get_short_name(self):
        return self.first_name

    def can_login_to_dashboard_app(self):
        return self.is_seller or self.is_super_admin

    def get_shipping_area_id(self):
        if self.orders.exists():
            latest_order = self.orders.latest('id')
            if latest_order.address:
                if latest_order.address.area:
                    return latest_order.address.area.id
            return 0
        return 0

    def get_shipping_area_ids(self):
        if self.orders.exists():
            shipping_area_ids = list(self.orders.filter(
                address__area__name__isnull=False
            ).values_list(
                'address__area__id', flat=True).distinct())
            return shipping_area_ids
        return []

    def get_wishlist_count(self):
        return self.wishlishted_products.all().count()

    def get_cart_count(self):
        if self.cart.exists():
            cart_prods = CartProduct.objects.filter(
                cart=self.cart.latest('id')
            )
            return cart_prods.count()
        return 0

    def get_total_purchase(self):
        orders = self.orders.filter(payments__status='SU')
        total_sum = sum(order.get_totalPrice_float() for order in orders)
        rounded_sum = round(total_sum, ndigits=3)
        return "{0:.3f}".format(rounded_sum)

    def get_total_purchase_float(self):
        orders = self.orders.filter(payments__status='SU')
        total_sum = sum(order.get_totalPrice_float() for order in orders)
        rounded_sum = round(total_sum, ndigits=3)
        return rounded_sum

    def get_device_types(self):
        return FCMDevice.objects.filter(
            user=self, active=True
        ).order_by('type').distinct('type').values_list(
            'type', flat=True)

    def get_unseen_ecomm_notification_count_non_device_specific(self):
        return self.ecommnotifications.filter(
            has_seen=False).count()

    def get_unseen_ecomm_dash_notification_count(self):
        return self.dash_ecommnotifications.filter(
            has_seen=False).count()

    def get_unseen_ecomm_notification_count(self, fcm_device_id):
        return self.ecommnotifications.filter(has_seen=False).count()

    def get_order_count(self):
        orders = self.orders.filter(payments__isnull=False).distinct()
        if orders.exists():
            order_prod_filter = filter(
                lambda x: x.order_prods_has_prod() is True, orders)
            qs = orders.filter(id__in=list([x.id for x in order_prod_filter]))
            return qs.count()
        return 0

    def __str__(self):
        if self.username:
            return " ".join([
                self.username, self.full_name
            ])
        if self.full_name != "":
            return self.full_name
        return str(self.pk)

    class Meta:
        ordering = ("username", )


class BlackListedEmails(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ("email", )
        verbose_name_plural = "BlackListedEmails"


class EcommMemberPermission(models.Model):
    module = models.CharField(max_length=100)
    name = models.CharField(
        max_length=100, blank=True, null=True)
    has_view_access = models.BooleanField(default=False)
    has_add_access = models.BooleanField(default=False)
    has_edit_access = models.BooleanField(default=False)
    has_delete_access = models.BooleanField(default=False)
    has_full_access = models.BooleanField(default=False)

    member = models.ForeignKey(
        "authentication.Member",
        related_name="ecomm_member_permissions_for",
        on_delete=CASCADE, blank=True, null=True)

    created_by = models.ForeignKey(
        "authentication.Member",
        related_name="ecomm_member_permissions_by",
        on_delete=CASCADE, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.module

    class Meta:
        ordering = ("id", )


class GuestAccount(models.Model):
    full_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = PhoneNumberField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.full_name

    class Meta:
        ordering = ("id", )

    def get_exact_full_name(self):
        if self.full_name:
            return self.full_name
        return ''

    def get_phone(self):
        if self.phone != "" and self.phone is not None:
            phone_string = "-".join([
                str(self.phone.country_code),
                str(national_significant_number(self.phone))
            ])
            return "+" + phone_string
        return ""
