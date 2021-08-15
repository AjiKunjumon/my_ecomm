from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import Permission
from django.contrib.humanize.templatetags import humanize
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.images import get_image_dimensions
from django.core.validators import FileExtensionValidator
from django.db.models import Sum, F, Q, FloatField
from django.shortcuts import get_object_or_404
from fcm_django.models import FCMDevice
from phonenumber_field.serializerfields import PhoneNumberField
from phonenumbers import national_significant_number
from rest_framework import serializers
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from app.authentication.mixins import SetCustomErrorMessagesMixin
from app.authentication.models import Member
from app.authentication.models.member import EcommMemberPermission
from app.order.models import Order, CartProduct
from app.product.models import Category, EcommProduct, VariantValues
from app.product.serializers import SellerInfoSerializer, BrandSerializer, CategorySerializer, \
    CategoryCommissionSerializer
from app.store.models import Store, Address, City, Country, SocialMediaURL, Commission, Inventory, InventoryProduct
from app.utilities.helpers import get_perms_for_super_admin, convert_date_time_to_kuwait_string
from app.utilities.utils import is_email_valid


class GetSellerSerializer(serializers.ModelSerializer):
    token = serializers.SerializerMethodField()
    sellers_info = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    unseen_orders_count = serializers.SerializerMethodField()
    unread_notification_count = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    company = serializers.SerializerMethodField()

    class Meta:
        model = Member
        fields = (
            "id", "full_name", "email", "created_at", "updated_at",
            "is_email_verified", "phone", "token",
            "is_seller", "is_super_admin", "sellers_info",
            "permissions", "unseen_orders_count",
            "has_full_access", "unread_notification_count", "company"
        )

    def get_company(self, obj):
        if obj.is_seller:
            try:
                store = obj.stores
                return store.name
            except ObjectDoesNotExist:
                sub_admins = obj.seller_sub_admins.all()
                if sub_admins.exists():
                    sub_admin = sub_admins.latest('id')
                    return sub_admin.store.name
                return ""
        elif obj.company and obj.company != "":
            return obj.company
        return ""

    def get_full_name(self, obj):
        return obj.get_full_name()

    def get_token(self, obj):
        if self.context.get("ignore_token", False):
            return ""
        try:
            token = Token.objects.get(user=obj)
            return token.key
        except Token.DoesNotExist:
            return ""

    def get_sellers_info(self, obj):
        if obj.is_seller:
            try:
                store = obj.stores
                return SellerMinSerializer(
                    store
                ).data
            except ObjectDoesNotExist:
                sub_admins = obj.seller_sub_admins.all()
                if sub_admins.exists():
                    sub_admin = sub_admins.latest('id')
                    return SellerMinSerializer(
                        sub_admin.store
                    ).data
                return None
        # elif obj.is_super_admin:
        #     return SellerMinSerializer(
        #         Store.objects.all(), many=True
        #     ).data
        return None

    def get_permissions(self, obj):
        perms = obj.ecomm_member_permissions_for.all()
        return EcommPermissionDetailSerializer(perms, many=True).data

    def get_unseen_orders_count(self, obj):
        if obj.is_seller:
            sub_admins = obj.seller_sub_admins.all()
            if sub_admins.exists():
                sub_admin = sub_admins.latest('id')
                qs = Order.objects.filter(
                    payments__isnull=False,
                    orderProducts__product__store=sub_admin.store).distinct()
            else:
                qs = Order.objects.filter(
                    payments__isnull=False,
                    orderProducts__product__store__member=obj).distinct()
        else:
            qs = Order.objects.filter(payments__isnull=False).distinct()

        order_prod_filter = filter(
            lambda x: x.order_prods_has_prod() is True, qs)
        qs = qs.filter(id__in=list([x.id for x in order_prod_filter]))

        print(obj)
        print("orders_count")
        print(qs.values_list('id', flat=True))
        unseen_order_count = qs.filter(~Q(
            pk__in=obj.order_views.all().values_list('order_id', flat=True))).count()
        return unseen_order_count

    def get_unread_notification_count(self, obj):
        return obj.get_unseen_ecomm_dash_notification_count()


class SellerMinSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()

    class Meta:
        model = Store
        fields = ('id', 'name', 'nameAR', 'type')

    def get_type(self, obj):
        return obj.get_type_display()


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ('id', )


class CityDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ('id', 'name', 'nameAR', 'governerate',
                  'governerateAR')


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ('id', )


class SocialMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialMediaURL
        fields = ('url', 'status', )

    def create(self, validated_data):
        social_media_url = SocialMediaURL.objects.create(**validated_data)
        return social_media_url


class SocialMediaDetailSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=True)

    class Meta:
        model = SocialMediaURL
        fields = ('id', 'url', 'status', )


class CommissionSerializer(serializers.ModelSerializer):
    category = serializers.SerializerMethodField()

    class Meta:
        model = Commission
        fields = ('id', 'percentage', 'category', )

    def get_category(self, obj):
        return CategoryCommissionSerializer(obj.category).data


class CommissionSellerSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=True)

    class Meta:
        model = Commission
        fields = ('id', 'percentage', 'category', )

    def get_category(self, obj):
        return CategorySerializer(obj.category).data


class CommissionCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Commission
        fields = ('percentage', 'category', )


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ('area', 'block', 'street', 'house',
                  'phone', 'country', 'state', 'jadda',
                  'apartment', 'extra_directions')

    def validate(self, attrs):
        area = attrs.get("area")
        country = attrs.get("country")

        if not area:
            raise ValidationError("Area is required")
        if not country:
            raise ValidationError("Country is required")
        return attrs

    def create(self, validated_data):
        address = Address.objects.create(**validated_data)
        return address


class AddressDetailSerializer(serializers.ModelSerializer):
    area = serializers.SerializerMethodField()

    class Meta:
        model = Address
        fields = ('id', 'area', 'block', 'street', 'house',
                  'phone', 'country', 'state', 'jadda',
                  'apartment', 'extra_directions', 'title',
                  'area_name', 'country_name')

    def get_area(self, obj):
        return CityDetailsSerializer(obj.area).data


class NestedCategorySerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=True)

    class Meta:
        model = Category
        fields = ('id', )


class SellerSerializer(serializers.ModelSerializer):
    seller_name = serializers.CharField(source='name', required=True)
    seller_name_ar = serializers.CharField(source='nameAR', required=True)
    seller_email = serializers.CharField(source='contact_email', required=True)
    seller_contact_no = serializers.CharField(source='phone', required=True)
    seller_logo = serializers.ImageField(
        source='image', use_url=True,
        required=False, validators=[
            FileExtensionValidator(allowed_extensions=["png", "jpeg", "jpg"])
        ])
    seller_address = serializers.CharField(source='address', required=True)
    seller_address_ar = serializers.CharField(source='addressAR', required=True)
    seller_delivery_address = AddressSerializer()
    social_media_urls = SocialMediaSerializer(required=False, many=True)
    commissions = CommissionCreateSerializer(many=True)
    selling_categories = NestedCategorySerializer(required=True, many=True)
    status_start_date = serializers.DateTimeField(
        required=False, format="%Y-%m-%d %H:%M:%S")

    class Meta:
        model = Store
        fields = ('seller_name', 'seller_name_ar', 'seller_email',
                  'seller_contact_no', 'seller_logo', 'seller_address',
                  'seller_address_ar', 'seller_delivery_address',
                  'selling_categories', 'social_media_urls',
                  'type', 'pickUpCharge', 'status', 'status_start_date',
                  'commissions')

    def validate_seller_logo(self, value):
        if settings.SITE_CODE != 1:
            if value == "":
                raise ValidationError("Please upload an image ")
            w, h = get_image_dimensions(value)
            if w != 512:
                raise ValidationError("Image is not as per the required size")
            if h != 512:
                raise ValidationError("Image is not as per the required size")
        return value

    def validate_selling_categories(self, value):
        if len(value) == 0:
            raise ValidationError("Please choose at least one category")
        return value

    def create(self, validated_data):
        seller_delivery_address = validated_data.pop('seller_delivery_address')
        selling_categories = validated_data.pop('selling_categories')
        social_media_urls = validated_data.pop('social_media_urls', None)
        commissions = validated_data.pop('commissions')

        seller = Store.objects.create(**validated_data, member=self.context)

        for selling_category_data in selling_categories:
            category_id = selling_category_data.pop('id', None)
            category = get_object_or_404(Category, pk=category_id)
            seller.selling_categories.add(category)

        if social_media_urls:
            for social_media_url in social_media_urls:
                SocialMediaURL.objects.get_or_create(store=seller, **social_media_url)

        for commission in commissions:
            Commission.objects.get_or_create(seller=seller, **commission)

        address = Address.objects.create(**seller_delivery_address)
        address.seller = seller
        address.save()
        return seller

    def update(self, instance, validated_data):

        seller_delivery_address = validated_data.pop('seller_delivery_address')
        selling_categories = validated_data.pop('selling_categories')

        social_media_urls_data = validated_data.pop('social_media_urls', None)
        social_media_urls = instance.socialmediaurls.all()
        social_media_urls = list(social_media_urls)

        commissions_data = validated_data.pop('commissions', None)
        commissions = instance.commission.all()
        commissions = list(commissions)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if len(selling_categories) > 0:
            instance.selling_categories.clear()

        for selling_category_data in selling_categories:
            category_id = selling_category_data.pop('id', None)
            category = get_object_or_404(Category, pk=category_id)
            instance.selling_categories.add(category)

        if social_media_urls_data and len(social_media_urls) > 0:
            for social_media_url_data in social_media_urls_data:
                if social_media_url_data.get('id'):
                    social_media_url = get_object_or_404(
                        SocialMediaURL, pk=social_media_url_data.get("id"))
                    social_media_url.url = social_media_url_data.get(
                        'url', social_media_url.url)
                    social_media_url.status = social_media_url_data.get(
                        'status', social_media_url.status)
                    social_media_url.save()
                else:
                    SocialMediaURL.objects.create(
                        store=instance, **social_media_url_data)

        if commissions_data and len(commissions) > 0:
            for commission_data in commissions_data:
                if commission_data.get('id'):
                    commission = get_object_or_404(
                        Commission, pk=commission_data.get("id"))
                    commission.percentage = commission_data.get(
                        'percentage', commission.percentage)
                    commission.category = commission_data.get(
                        'category', commission.category)
                    commission.save()
                else:
                    Commission.objects.create(
                        seller=instance, **commission_data)

        address_serializer = AddressSerializer()
        address = instance.addresses.first()
        if address:
            address_serializer.update(address, seller_delivery_address)
        instance.save()

        return instance


class EditSellerBeconSerializer(serializers.ModelSerializer):
    seller_name = serializers.CharField(source='name', required=True)
    seller_name_ar = serializers.CharField(source='nameAR', required=True)
    seller_email = serializers.CharField(source='contact_email', required=True)
    seller_contact_no = serializers.CharField(source='phone', required=True)
    seller_logo = serializers.ImageField(
        source='image', use_url=True,
        required=False, validators=[
            FileExtensionValidator(allowed_extensions=["png", "jpeg", "jpg"])
        ])
    seller_address = serializers.CharField(source='address', required=True)
    seller_address_ar = serializers.CharField(source='addressAR', required=True)
    seller_delivery_address = AddressSerializer()
    social_media_urls = SocialMediaDetailSerializer(required=False, many=True)
    commissions = CommissionSellerSerializer(many=True, required=False)
    selling_categories = NestedCategorySerializer(required=True, many=True)
    status_start_date = serializers.DateTimeField(
        required=False, format="%Y-%m-%d %H:%M:%S")

    class Meta:
        model = Store
        fields = ('seller_name', 'seller_name_ar', 'seller_email',
                  'seller_contact_no', 'seller_logo', 'seller_address',
                  'seller_address_ar', 'seller_delivery_address',
                  'selling_categories', 'social_media_urls',
                  'type', 'pickUpCharge', 'status', 'status_start_date',
                  'commissions')

    def validate_seller_logo(self, value):
        if settings.SITE_CODE != 1:
            if value == "":
                raise ValidationError("Please upload an image ")
            w, h = get_image_dimensions(value)
            if w != 512:
                raise ValidationError("Image is not as per the required size")
            if h != 512:
                raise ValidationError("Image is not as per the required size")
        return value

    def validate_selling_categories(self, value):
        if len(value) == 0:
            raise ValidationError("Please choose at least one category")
        return value

    def update(self, instance, validated_data):
        print("edit seller validated_data")
        print(validated_data)
        seller_delivery_address = validated_data.pop('seller_delivery_address', None)
        selling_categories = validated_data.pop('selling_categories', None)

        social_media_urls_data = validated_data.pop('social_media_urls', None)
        social_media_urls = instance.socialmediaurls.all()
        social_media_urls = list(social_media_urls)

        commissions_data = validated_data.pop('commissions', None)
        commissions = instance.commission.all()
        commissions = list(commissions)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if len(selling_categories) > 0:
            instance.selling_categories.clear()

        for selling_category_data in selling_categories:
            category_id = selling_category_data.pop('id', None)
            category = get_object_or_404(Category, pk=category_id)
            instance.selling_categories.add(category)

        if social_media_urls_data and len(social_media_urls_data) > 0:
            for social_media_url_data in social_media_urls_data:
                if social_media_url_data.get('id') != 0:
                    social_media_url = get_object_or_404(
                        SocialMediaURL, pk=social_media_url_data.get("id"))
                    social_media_url.url = social_media_url_data.get(
                        'url', social_media_url.url)
                    social_media_url.status = social_media_url_data.get(
                        'status', social_media_url.status)
                    social_media_url.save()
                else:

                    SocialMediaURL.objects.update_or_create(
                        store=instance,
                        status=social_media_url_data.get('status'),
                        defaults={
                            'url': social_media_url_data.get('url')
                        }
                    )

        if commissions_data and len(commissions_data) > 0:
            for commission_data in commissions_data:
                if commission_data.get('id') != 0:
                    commission = get_object_or_404(
                        Commission, pk=commission_data.get("id"))
                    commission.percentage = commission_data.get(
                        'percentage', commission.percentage)
                    commission.category = commission_data.get(
                        'category', commission.category)
                    commission.save()
                else:
                    Commission.objects.update_or_create(
                        seller=instance,
                        category=commission_data.get('category'),
                        defaults={
                            'percentage': commission_data.get('percentage')
                        })

        address_serializer = AddressSerializer()
        address = instance.addresses.first()
        if address:
            address_serializer.update(address, seller_delivery_address)
        else:
            Address.objects.get_or_create(seller=instance, **seller_delivery_address)
        instance.save()

        return instance


class EditSellerSerializer(serializers.ModelSerializer):
    seller_name = serializers.CharField(source='name', required=True)
    seller_name_ar = serializers.CharField(source='nameAR', required=True)
    seller_email = serializers.CharField(source='contact_email', required=True)
    seller_contact_no = serializers.CharField(source='phone', required=True)
    seller_logo = serializers.ImageField(
        source='image', use_url=True,
        required=False, validators=[
            FileExtensionValidator(allowed_extensions=["png", "jpeg", "jpg"])
        ])
    seller_address = serializers.CharField(source='address', required=True)
    seller_address_ar = serializers.CharField(source='addressAR', required=True)
    seller_delivery_address = AddressSerializer()
    social_media_urls = SocialMediaDetailSerializer(required=False, many=True)
    commissions = CommissionSellerSerializer(many=True)
    selling_categories = NestedCategorySerializer(required=True, many=True)
    status_start_date = serializers.DateTimeField(
        required=False, format="%Y-%m-%d %H:%M:%S")

    class Meta:
        model = Store
        fields = ('seller_name', 'seller_name_ar', 'seller_email',
                  'seller_contact_no', 'seller_logo', 'seller_address',
                  'seller_address_ar', 'seller_delivery_address',
                  'selling_categories', 'social_media_urls',
                  'type', 'pickUpCharge', 'status', 'status_start_date',
                  'commissions')

    def validate_seller_logo(self, value):
        if settings.SITE_CODE != 1:
            if value == "":
                raise ValidationError("Please upload an image ")
            w, h = get_image_dimensions(value)
            if w != 512:
                raise ValidationError("Image is not as per the required size")
            if h != 512:
                raise ValidationError("Image is not as per the required size")
        return value

    def validate_selling_categories(self, value):
        if len(value) == 0:
            raise ValidationError("Please choose at least one category")
        return value

    def update(self, instance, validated_data):
        print("edit seller validated_data")
        print(validated_data)
        seller_delivery_address = validated_data.pop('seller_delivery_address', None)
        selling_categories = validated_data.pop('selling_categories', None)

        social_media_urls_data = validated_data.pop('social_media_urls', None)
        social_media_urls = instance.socialmediaurls.all()
        social_media_urls = list(social_media_urls)

        commissions_data = validated_data.pop('commissions', None)
        commissions = instance.commission.all()
        commissions = list(commissions)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if len(selling_categories) > 0:
            instance.selling_categories.clear()

        for selling_category_data in selling_categories:
            category_id = selling_category_data.pop('id', None)
            category = get_object_or_404(Category, pk=category_id)
            instance.selling_categories.add(category)

        if social_media_urls_data and len(social_media_urls_data) > 0:
            for social_media_url_data in social_media_urls_data:
                if social_media_url_data.get('id') != 0:
                    social_media_url = get_object_or_404(
                        SocialMediaURL, pk=social_media_url_data.get("id"))
                    social_media_url.url = social_media_url_data.get(
                        'url', social_media_url.url)
                    social_media_url.status = social_media_url_data.get(
                        'status', social_media_url.status)
                    social_media_url.save()
                else:

                    SocialMediaURL.objects.update_or_create(
                        store=instance,
                        status=social_media_url_data.get('status'),
                        defaults={
                            'url': social_media_url_data.get('url')
                        }
                    )

        if commissions_data and len(commissions_data) > 0:
            for commission_data in commissions_data:
                if commission_data.get('id') != 0:
                    commission = get_object_or_404(
                        Commission, pk=commission_data.get("id"))
                    commission.percentage = commission_data.get(
                        'percentage', commission.percentage)
                    commission.category = commission_data.get(
                        'category', commission.category)
                    commission.save()
                else:
                    Commission.objects.update_or_create(
                        seller=instance,
                        category=commission_data.get('category'),
                        defaults={
                            'percentage': commission_data.get('percentage')
                        })

        address_serializer = AddressSerializer()
        address = instance.addresses.first()
        if address:
            address_serializer.update(address, seller_delivery_address)
        else:
            Address.objects.get_or_create(seller=instance, **seller_delivery_address)
        instance.save()

        return instance


class MemberSerializer(serializers.ModelSerializer):
    login_email = serializers.EmailField(source='email')
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Member
        fields = (
            "first_name", "last_name",
            "login_email", "password",
            "nationality_code",
        )

    def validate_login_email(self, value):
        if is_email_valid(value):
            try:
                m = Member.objects.get(email=value)
            except Member.DoesNotExist:
                m = None
            if m is not None:
                raise ValidationError("Entered email already exists.")
            else:
                return value
        raise ValidationError("Invalid email address")

    def create(self, validated_data):
        seller_name_ar = validated_data.pop("seller_name_ar", None)
        seller_logo = validated_data.pop("seller_logo", None)
        seller_address = validated_data.pop("seller_address", None)
        seller_address_ar = validated_data.pop("seller_address_ar", None)
        seller_delivery_address = validated_data.pop("seller_address_ar", None)

        member = Member.objects.create(**validated_data)
        password = validated_data.get("password", None)
        if password:
            member.set_password(password)
            member.save()
        return member

    # def update(self, instance, validated_data):
    #     instance.full_name = validated_data.get(
    #         "full_name", instance.full_name)
    #     instance.phone = validated_data.get("phone", instance.phone)
    #     instance.nationality_code = validated_data.get(
    #         "nationality_code", instance.nationality_code)
    #
    #     instance.save()
    #
    #     password = validated_data.get('password', None)
    #     if password:
    #         instance.set_password(password)
    #         instance.save()
    #     return instance


class PermissionSerializer(serializers.ModelSerializer):
    module = serializers.SerializerMethodField()

    class Meta:
        model = Permission
        fields = (
            "id", "name", "codename",
            "module"
        )

    def get_module(self, obj):
        return obj.content_type.app_label


class MemberSettingsSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    last_login = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    company = serializers.SerializerMethodField()

    class Meta:
        model = Member
        fields = (
            "id", "first_name", "last_name",
            "full_name", "company",
            "email", "last_login", "designation",
            "is_super_admin", "is_seller", "status",
            "has_full_access", "permissions"
        )

    def get_company(self, obj):
        if obj.is_seller:
            try:
                store = obj.stores
                return store.name
            except ObjectDoesNotExist:
                sub_admins = obj.seller_sub_admins.all()
                if sub_admins.exists():
                    sub_admin = sub_admins.latest('id')
                    return sub_admin.store.name
                return ""
        elif obj.company and obj.company != "":
            return obj.company
        return ""

    def get_full_name(self, obj):
        return obj.get_full_name()

    def get_status(self, obj):
        return obj.get_status_display()

    def get_permissions(self, obj):
        perms = obj.ecomm_member_permissions_for.all()
        return EcommPermissionDetailSerializer(perms, many=True).data

    def get_last_login(self, obj):
        if obj.last_login:
            # kuwait_date = convert_date_time_to_kuwait_string(obj.last_login)
            # return humanize.naturalday(obj.last_login).capitalize()
            return convert_date_time_to_kuwait_string(obj.last_login)
            # return humanize.naturalday(kuwait_date).capitalize()
        return None


class MemberEcommEditSerializer(serializers.ModelSerializer):
    login_email = serializers.EmailField(source='email')
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Member
        fields = (
            "first_name", "last_name",
            "login_email", "password",
            "nationality_code",
        )

    def validate_login_email(self, value):
        if value and value != "":
            if self.instance.email == value:
                return value
            if is_email_valid(value):
                try:
                    m = Member.objects.get(email=value)
                except Member.DoesNotExist:
                    m = None
                if m is not None:
                    raise ValidationError("Email provided already exists.")
                else:
                    return value
            raise ValidationError("Email provided is invalid")
        raise ValidationError("Kindly enter your email.")

    def update(self, instance, validated_data):
        instance.first_name = validated_data.get(
            "first_name", instance.first_name)
        instance.last_name = validated_data.get("last_name", instance.last_name)
        instance.email = validated_data.get(
            "email", instance.email)

        instance.save()
        return instance


class MemberDetailSerializer(serializers.ModelSerializer):
    login_email = serializers.EmailField(source='email')
    seller_contact_no = serializers.CharField(source='phone')

    class Meta:
        model = Member
        fields = (
            "id", "login_email", "seller_contact_no",
            "nationality_code", "first_name", "last_name"
        )


class SellerDetailSerializer(serializers.ModelSerializer):
    seller_name = serializers.SerializerMethodField()
    seller_name_ar = serializers.SerializerMethodField()
    seller_email = serializers.SerializerMethodField()
    seller_contact_no = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()
    seller_logo = serializers.SerializerMethodField()
    seller_address = serializers.SerializerMethodField()
    seller_address_ar = serializers.SerializerMethodField()
    seller_delivery_address = serializers.SerializerMethodField()
    social_media_urls = serializers.SerializerMethodField()
    commissions = serializers.SerializerMethodField()
    member = serializers.SerializerMethodField()
    seller_banners = serializers.SerializerMethodField()
    sales = serializers.SerializerMethodField()
    orders_count = serializers.SerializerMethodField()
    net_sales = serializers.SerializerMethodField()
    commission = serializers.SerializerMethodField()
    pickup_charges = serializers.SerializerMethodField()

    class Meta:
        model = Store
        fields = ('id', 'seller_name', 'seller_name_ar', 'seller_email',
                  'seller_contact_no', 'seller_logo', 'seller_address',
                  'seller_address_ar', 'seller_delivery_address',
                  'selling_categories', 'social_media_urls',
                  'type', 'pickUpCharge', 'status', 'status_start_date',
                  'status_end_date', 'commissions', 'member',
                  'seller_banners', 'sales', 'orders_count',
                  'net_sales', 'commission', 'pickup_charges')

    def get_seller_contact_no(self, obj):
        return str(obj.phone)

    def get_member(self, obj):
        if obj.member:
            return MemberDetailSerializer(obj.member).data
        return None

    def get_seller_logo(self, obj):
        if obj.image:
            return obj.image.url
        return None

    def get_seller_name(self, obj):
        return obj.name

    def get_seller_name_ar(self, obj):
        return obj.nameAR

    def get_seller_email(self, obj):
        return obj.contact_email

    def get_status(self, obj):
        return obj.get_status_display()

    def get_type(self, obj):
        return obj.get_type_display()

    def get_seller_address(self, obj):
        return obj.address

    def get_seller_address_ar(self, obj):
        return obj.addressAR

    def get_commissions(self, obj):
        if obj.commission.exists():
            return CommissionSerializer(
                obj.commission.filter(
                    category__pk__in=obj.selling_categories.all()),
                many=True).data
        return None

    def get_seller_delivery_address(self, obj):
        if obj.addresses.exists():
            return AddressDetailSerializer(obj.addresses.first()).data
        return None

    def get_social_media_urls(self, obj):
        if obj.socialmediaurls.exists():
            return SocialMediaDetailSerializer(
                obj.socialmediaurls, many=True).data
        return None

    def get_seller_banners(self, obj):
        from app.store.serializers import BannerListSerializer
        if obj.banners.exists():
            return BannerListSerializer(
                obj.banners, many=True).data
        return None

    def get_sales(self, obj):
        orders_sales_price = Order.objects.filter(
            payments__status='SU',
            orderProducts__product__store=obj
        ).aggregate(price=Sum(F('totalPrice'))).get(
            'price')

        if orders_sales_price:
            return "{0:.3f}".format(orders_sales_price)
        return 0

    def get_orders_count(self, obj):
        orders = Order.objects.filter(
            orderProducts__product__store=obj
        )
        return orders.count()

    def get_net_sales(self, obj):
        sales = obj.get_sales_float()
        total_commission = 0

        if obj.commission.exists():
            commission = obj.commission.all().values(
                'percentage', 'category__id').order_by(
                'category__id').distinct('category__id')
            for c in commission:
                category_id = c.get('category__id')
                percentage = c.get('percentage')
                orders = Order.objects.filter(
                    orderProducts__product__store=obj,
                    orderProducts__product__category_id=category_id
                )
                cat_sales_price = 0
                for order in orders:
                    cat_sales_price += order.get_totalPrice_float()
                if cat_sales_price > 0:
                    commission_per_cat = cat_sales_price - (
                            cat_sales_price * percentage) / 100
                    total_commission += commission_per_cat

        return round(sales - total_commission, ndigits=3)

    def get_commission(self, obj):
        total_commission = 0
        if obj.commission.exists():
            commission = obj.commission.all().values(
                'percentage', 'category__id').order_by(
                'category__id').distinct('category__id')
            total_commission = 0
            for c in commission:
                category_id = c.get('category__id')
                percentage = c.get('percentage')
                orders = Order.objects.filter(
                    orderProducts__product__store=obj,
                    orderProducts__product__category_id=category_id
                )
                cat_sales_price = 0
                for order in orders:
                    cat_sales_price += order.get_totalPrice_float()
                if cat_sales_price > 0:
                    commission_per_cat = cat_sales_price - (
                            cat_sales_price * percentage) / 100
                    total_commission += commission_per_cat
        return round(total_commission, ndigits=3)

    def get_pickup_charges(self, obj):
        pickup_charges = obj.pickUpCharge * self.get_orders_count(obj)
        return round(pickup_charges, ndigits=3)


class SellerListSerializer(serializers.ModelSerializer):
    seller_name = serializers.SerializerMethodField()
    seller_name_ar = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()
    seller_logo = serializers.SerializerMethodField()
    commissions = serializers.SerializerMethodField()
    seller_id = serializers.SerializerMethodField()
    prod_count = serializers.SerializerMethodField()
    sales = serializers.SerializerMethodField()
    earnings = serializers.SerializerMethodField()

    class Meta:
        model = Store
        fields = ('id', 'seller_id', 'seller_name', 'seller_name_ar',
                  'prod_count', 'seller_logo', 'sales',
                  'type', 'pickUpCharge', 'status', 'status_start_date',
                  'status_end_date', 'commissions', 'earnings')

    def get_seller_contact_no(self, obj):
        return str(obj.phone)

    def get_seller_id(self, obj):
        return '#'.join(
            [str(obj.pk)]
        )

    def get_seller_logo(self, obj):
        if obj.image:
            return obj.image.url
        return None

    def get_seller_name(self, obj):
        return obj.name

    def get_seller_name_ar(self, obj):
        return obj.nameAR

    def get_prod_count(self, obj):
        return obj.products.all().filter(
            parent__isnull=True
        ).count()

    def get_status(self, obj):
        return obj.get_status_display()

    def get_type(self, obj):
        return obj.get_type_display()

    def get_commissions(self, obj):
        if obj.commission.exists():
            return CommissionSerializer(
                obj.commission.filter(
                    category__pk__in=obj.selling_categories.all()),
                many=True).data
        return None

    def get_sales(self, obj):
        orders = Order.objects.filter(
            payments__status='SU',
            orderProducts__product__store=obj
        )
        sales_total = 0.000
        for order in orders:
            sub_total = order.orderProducts.filter(
                product__store=obj
            ).aggregate(
                sub_total=Sum(F('price') * F('quantity'),
                              output_field=FloatField())).get('sub_total')
            if sub_total:
                sales_total += sub_total
        return sales_total

        # orders_sales_price = Order.objects.filter(
        #     payments__status='SU',
        #     orderProducts__product__store=obj
        # ).aggregate(price=Sum(F('totalPrice'))).get(
        #     'price')
        #
        # if orders_sales_price:
        #     return orders_sales_price
        # return 0

    def get_earnings(self, obj):
        sales = self.get_sales(obj)
        commission_total = 0.000
        if obj.commission.exists():
            commission = obj.commission.all().values(
                'percentage', 'category__id').order_by(
                'category__id').distinct('category__id')
            total_commission = 0
            # print("commission")
            # print(commission)
            for c in commission:
                category_id = c.get('category__id')
                percentage = c.get('percentage')
                cat_sales_price = Order.objects.filter(
                    payments__status='SU',
                    orderProducts__product__store=obj,
                    orderProducts__product__category_id=category_id
                ).aggregate(price=Sum(F('totalPrice'))).get('price')

                # print("cat_sales_price")
                # print(cat_sales_price)
                if cat_sales_price:
                    commission_per_cat = cat_sales_price - (
                            cat_sales_price * percentage) / 100
                    total_commission += commission_per_cat
                #
                # orders = Order.objects.filter(
                #     payments__status='SU',
                #     orderProducts__product__store=obj,
                #     orderProducts__product__category_id=category_id
                # )
                # for order in orders:
                #     sub_total = order.orderProducts.filter(
                #         product__category_id=category_id
                #     ).aggregate(
                #         sub_total=Sum(F('price') * F('quantity'),
                #                       output_field=FloatField())).get('sub_total')
                #     if sub_total:
            return sales - total_commission
        return 0
        # if obj.commission.exists():
        #     commission = obj.commission.all().values(
        #         'percentage', 'category__id').order_by(
        #         'category__id').distinct('category__id')
        #     print("commission")
        #     print(commission)
        #     for c in commission:
        #         category_id = c.get('category__id')
        #         percentage = c.get('percentage')
        #         descendant_ids = Category.objects.descendants(
        #             get_object_or_404(Category, pk=category_id)).values_list(
        #             'id', flat=True).distinct()
        #         print("descendant_ids")
        #         print(descendant_ids)
        #         orders = Order.objects.filter(
        #             payments__status='SU',
        #             orderProducts__product__store=obj,
        #             orderProducts__product__category__pk__in=descendant_ids
        #         )
        #         print("orders")
        #         print(orders)
        #         sales_total = 0.000
        #         for order in orders:
        #             sub_total = order.orderProducts.filter(
        #                 product__category__pk__in=descendant_ids
        #             ).aggregate(
        #                 sub_total=Sum(F('price') * F('quantity'),
        #                               output_field=FloatField())).get('sub_total')
        #             if sub_total:
        #                 sales_total += sub_total
        #                 commission_total += (sales_total * percentage) / 100
        #
        # return commission_total


class SellerListCollectionSerializer(serializers.ModelSerializer):
    seller_name = serializers.SerializerMethodField()
    seller_name_ar = serializers.SerializerMethodField()

    class Meta:
        model = Store
        fields = ('id', 'seller_name', 'seller_name_ar')

    def get_seller_contact_no(self, obj):
        return str(obj.phone)

    def get_seller_name(self, obj):
        return obj.name

    def get_seller_name_ar(self, obj):
        return obj.nameAR


class VariantValuesMinSerializer(serializers.ModelSerializer):
    variant_name = serializers.SerializerMethodField()
    variant_id = serializers.SerializerMethodField()

    class Meta:
        model = VariantValues
        fields = ('id', 'value', 'variant_name', 'variant_id')

    def get_value(self, obj):
        lang_code = self.context.get("lang_code")
        if lang_code == "ar":
            return obj.valueAR
        return obj.value

    def get_variant_name(self, obj):
        lang_code = self.context.get("lang_code")
        if lang_code == "ar":
            return obj.variant.nameAR
        return obj.variant.name

    def get_variant_id(self, obj):
        return obj.variant.id


class ProductInvListSerializer(serializers.ModelSerializer):

    class Meta:
        model = EcommProduct
        fields = (
            "id", "name",
        )


class InventoryListSerializer(serializers.ModelSerializer):
    variant_values = serializers.SerializerMethodField()
    brand = serializers.SerializerMethodField()
    seller = serializers.SerializerMethodField()
    stock_status = serializers.SerializerMethodField()
    available_qty = serializers.SerializerMethodField()
    sku = serializers.SerializerMethodField()
    prod_image = serializers.SerializerMethodField()
    product = serializers.SerializerMethodField()

    class Meta:
        model = InventoryProduct
        fields = ('id', 'product', 'variant_values', 'sku', 'brand',
                  'seller', 'stock_status', 'available_qty',
                  'prod_image')

    def get_product(self, obj):
        return ProductInvListSerializer(obj.product).data

    def get_prod_image(self, obj):
        if obj.product:
            product = obj.product
            if product.medias.exists():
                return product.medias.first().file_data.url
            return None
        return None

    def get_variant_values(self, obj):
        lang_code = self.context.get("lang_code")

        var_vals = VariantValues.objects.filter(
            pk__in=obj.product.variant_value_ids()
        )
        return VariantValuesMinSerializer(
            var_vals, many=True,
            context={'product': obj.product,
                     'lang_code': lang_code}).data

    def get_brand(self, obj):
        return BrandSerializer(obj.product.brand).data

    def get_sku(self, obj):
        return obj.product.sku

    def get_seller(self, obj):
        if obj.product.store:
            return SellerInfoSerializer(obj.product.store).data
        return None

    def get_stock_status(self, obj):
        inv_prods = InventoryProduct.objects.filter(
            product=obj.product, inventory=obj.inventory
        )
        inv_prod = inv_prods.latest('id')
        if inv_prod:
            if inv_prod.quantity > 0:
                return "In Stock"
            return "Out of Stock"
        return "Out of Stock"

    def get_available_qty(self, obj):
        inv_prods = InventoryProduct.objects.filter(
            product=obj.product, inventory=obj.inventory
        )
        inv_prod = inv_prods.latest('id')
        if inv_prod:
            return inv_prod.quantity
        return 0


class CustomerListSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    shipping_area = serializers.SerializerMethodField()
    wishlist_count = serializers.SerializerMethodField()
    cart_count = serializers.SerializerMethodField()
    order_count = serializers.SerializerMethodField()
    total_purchase = serializers.SerializerMethodField()
    recent_order = serializers.SerializerMethodField()
    device_types = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    shipping_areas = serializers.SerializerMethodField()

    class Meta:
        model = Member
        fields = (
            "id", "full_name", "email", "created_at", "updated_at",
            "is_email_verified", "phone", "shipping_area",
            "wishlist_count", "cart_count", "order_count",
            "total_purchase", "recent_order", "device_types",
            "status", "shipping_areas"
        )

    def get_status(self, obj):
        return obj.get_status_display()

    def get_shipping_areas(self, obj):
        if not obj.orders.exists():
            return ""
        shipping_areas = obj.orders.filter(
            address__area__name__isnull=False
        ).values(
            'address__area__id',
            'address__area__name').distinct()
        return shipping_areas

    def get_full_name(self, obj):
        if obj.full_name and obj.full_name == "":
            return obj.get_full_name()
        return obj.full_name

    def get_phone(self, obj):
        if obj.phone != "" and obj.phone is not None:
            phone_string = "-".join([
                str(obj.phone.country_code),
                str(national_significant_number(obj.phone))
            ])
            return "+" + phone_string
        return ""

    def get_shipping_area(self, obj):
        if obj.orders.exists():
            latest_order = obj.orders.latest('id')
            if latest_order.address:
                if latest_order.address.area:
                    return latest_order.address.area.name
            return ""
        return ""

    def get_wishlist_count(self, obj):
        return obj.wishlishted_products.all().count()

    def get_cart_count(self, obj):
        if obj.cart.exists():
            cart_prods = CartProduct.objects.filter(
                cart=obj.cart.latest('id')
            )
            return cart_prods.count()
        return 0

    def get_order_count(self, obj):
        orders = obj.orders.filter(payments__status='SU')
        if orders.exists():
            order_prod_filter = filter(
                lambda x: x.order_prods_has_prod() is True, orders)
            qs = orders.filter(id__in=list([x.id for x in order_prod_filter]))
            return qs.count()
        return 0

    def get_total_purchase(self, obj):
        orders = obj.orders.filter(payments__status='SU')
        total_sum = sum(order.get_totalPrice_float()
                        for order in orders if order.get_totalPrice_float())
        rounded_sum = round(total_sum, ndigits=3)
        return "{0:.3f}".format(rounded_sum)

    def get_recent_order(self, obj):
        if obj.orders.exists():
            latest_order = obj.orders.latest('id')
            if latest_order.created_at:
                return latest_order.created_at
            return None
            # kuwait_date = convert_date_time_to_kuwait_string(latest_order.created_at)
            # return humanize.naturalday(latest_order.created_at).capitalize()
            # return humanize.naturalday(kuwait_date).capitalize()
        return ""

    def get_device_types(self, obj):
        return FCMDevice.objects.filter(
            user=obj, active=True
        ).order_by('type').distinct('type').values_list(
            'type', flat=True)


class CustomerDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    shipping_areas = serializers.SerializerMethodField()
    device_types = serializers.SerializerMethodField()
    devices_technical_info = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    company = serializers.SerializerMethodField()

    class Meta:
        model = Member
        fields = (
            "id", "full_name", "email", "phone", "shipping_areas",
            "device_types", "devices_technical_info",
            "first_name", "last_name",
            "full_name", "company",
            "last_login", "designation",
            "is_super_admin", "is_seller", "status",
            "has_full_access", "permissions"
        )

    def get_company(self, obj):
        if obj.is_seller:
            try:
                store = obj.stores
                return store.name
            except ObjectDoesNotExist:
                sub_admins = obj.seller_sub_admins.all()
                if sub_admins.exists():
                    sub_admin = sub_admins.latest('id')
                    return sub_admin.store.name
                return ""
        elif obj.company and obj.company != "":
            return obj.company
        return ""

    def get_full_name(self, obj):
        return obj.get_full_name()

    def get_phone(self, obj):
        if obj.phone != "" and obj.phone is not None:
            phone_string = "-".join([
                str(obj.phone.country_code),
                str(national_significant_number(obj.phone))
            ])
            return "+" + phone_string
        return ""

    def get_shipping_areas(self, obj):
        if obj.addresses.exists():
            return AddressDetailSerializer(obj.addresses, many=True).data
        return None

    def get_device_types(self, obj):
        return FCMDevice.objects.filter(
            user=obj, active=True
        ).order_by('type').distinct('type').values_list(
            'type', flat=True)

    def get_devices_technical_info(self, obj):
        fcm_devices = FCMDevice.objects.filter(
            user=obj, active=True
        ).distinct()
        return FCMDeviceListSerializer(fcm_devices, many=True).data

    def get_status(self, obj):
        return obj.get_status_display()

    def get_permissions(self, obj):
        perms = obj.ecomm_member_permissions_for.all()
        return EcommPermissionDetailSerializer(perms, many=True).data

    def get_last_login(self, obj):
        if obj.last_login:
            return obj.last_login
            # kuwait_date = convert_date_time_to_kuwait_string(obj.last_login)
            # return humanize.naturalday(obj.last_login).capitalize()
            # return humanize.naturalday(kuwait_date).capitalize()
        return None


class CustomerEditSerializer(serializers.ModelSerializer):
    email = serializers.CharField(required=False)
    phone = PhoneNumberField(required=True)
    full_name = serializers.CharField(required=True)
    shipping_areas = AddressSerializer(many=True, required=False)

    class Meta:
        model = Member
        fields = (
            "id",  "full_name", "email", "phone", "shipping_areas"
        )

    def validate_phone(self, value):
        if value and value != "":
            if self.instance.phone == value:
                return value
            try:
                m = Member.objects.get(phone=value)
            except Member.DoesNotExist:
                m = None
            if m is not None:
                raise ValidationError("Entered phone number already exists.")
            else:
                return value
        raise ValidationError("Phone number is required.")

    def validate_email(self, value):
        if value and value != "":
            if self.instance.email == value:
                return value
            if is_email_valid(value):
                try:
                    m = Member.objects.get(email=value)
                except Member.DoesNotExist:
                    m = None
                if m is not None:
                    raise ValidationError("Email provided already exists.")
                else:
                    return value
            raise ValidationError("Email provided is invalid")
        raise ValidationError("Kindly enter your email.")

    def update(self, instance, validated_data):
        shipping_areas = validated_data.pop('shipping_areas', None)
        instance.full_name = validated_data.get(
            "full_name", instance.full_name)
        instance.phone = validated_data.get("phone", instance.phone)
        instance.email = validated_data.get(
            "email", instance.email)

        if shipping_areas:
            for shipping_area in shipping_areas:
                Address.objects.get_or_create(customer=instance, **shipping_area)

        instance.save()
        return instance


class GuestListSerializer(serializers.ModelSerializer):

    class Meta:
        model = FCMDevice
        fields = (
            "id", "name", "device_id", "type", "registration_id",
            "nationality_code", "latitude", "longitude",
            "date_created", "ip_address", "last_visited"
        )


class FCMDeviceListSerializer(serializers.ModelSerializer):

    class Meta:
        model = FCMDevice
        fields = (
            "id", "name", "device_id", "type", "registration_id",
            "nationality_code", "latitude", "longitude", "ip_address",
            "last_visited"
        )


class AddEditAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ('title', 'area_name', 'block', 'street', 'house',
                  'phone', 'country_code', 'state', 'jadda',
                  'floor', 'apartment', 'extra_directions',
                  'lon', 'lat', 'customer', 'customer_default',
                  'country_name', 'area')

    def create(self, validated_data):
        address = Address.objects.create(**validated_data)
        return address


class ChangePasswordSerializer(SetCustomErrorMessagesMixin, serializers.Serializer):
    member = serializers.PrimaryKeyRelatedField(queryset=Member.objects.all())
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def __init__(self, *args, **kwargs):
        super(ChangePasswordSerializer, self).__init__(*args, **kwargs)  # call the super()
        for field in self.fields:  # iterate over the serializer fields
            if field == "current_password":
                self.fields[field].error_messages['required'] = 'Current password cant be blank'
            if field == "new_password":
                self.fields[field].error_messages['required'] = 'New password cant be blank'

    def validate(self, data):
        user = data.get("member")
        current_password = data.get("current_password")
        new_password = data.get("new_password")

        user = authenticate(username=user.email, password=current_password)
        if user is None:
            raise serializers.ValidationError("Current password is incorrect")

        if len(new_password) < 8:
            raise serializers.ValidationError(
                "Minimum 8 characters required for password")

        if current_password == new_password:
            raise serializers.ValidationError(
                "Current and new password cannot be same")
        return data

    def reset(self):
        user = self.validated_data.get("member")
        new_password = self.validated_data.get("new_password")
        user.set_password(new_password)
        user.save()


class EcommPermissionSerializer(serializers.ModelSerializer):
    module = serializers.CharField(write_only=True)
    has_view_access = serializers.BooleanField(default=False)
    has_edit_access = serializers.BooleanField(default=False)
    has_delete_access = serializers.BooleanField(default=False)
    has_add_access = serializers.BooleanField(default=False)

    class Meta:
        model = EcommMemberPermission
        fields = ('module', 'has_view_access', 'has_delete_access',
                  'has_add_access', 'has_edit_access')

    def create(self, validated_data):
        permission = EcommMemberPermission.objects.create(**validated_data)
        return permission


class EditEcommPermissionSerializer(serializers.ModelSerializer):
    module = serializers.CharField(write_only=True)
    has_view_access = serializers.BooleanField(default=False)
    has_edit_access = serializers.BooleanField(default=False)
    has_delete_access = serializers.BooleanField(default=False)
    has_add_access = serializers.BooleanField(default=False)
    id = serializers.IntegerField(required=True)

    class Meta:
        model = EcommMemberPermission
        fields = ('id', 'module', 'has_view_access', 'has_delete_access',
                  'has_add_access', 'has_edit_access')


class EcommPermissionDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = EcommMemberPermission
        fields = ('id', 'module', 'has_view_access', 'has_delete_access',
                  'has_add_access', 'has_edit_access')


class AddSuperAdminSerializer(serializers.ModelSerializer):
    permissions = EcommPermissionSerializer(many=True, required=False)
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Member
        fields = ('first_name', 'last_name', 'designation', 'company',
                  'email', 'has_full_access', 'password', 'permissions',
                  'is_super_admin', 'is_seller')

    def validate_email(self, value):
        if value and value != "":
            if is_email_valid(value):
                try:
                    m = Member.objects.get(
                        email=value)
                except Member.DoesNotExist:
                    m = None
                if m is not None:
                    raise ValidationError("Email provided already exists.")
                else:
                    return value
            raise ValidationError("Email provided is invalid")
        raise ValidationError("Kindly enter your email.")

    def validate_password(self, value):
        if value and value != "":
            if len(value) < 8:
                raise ValidationError("Minimum 8 characters required for password")
            return value
        raise ValidationError("Kindly enter a password.")

    # def validate(self, attrs):
    #     is_seller = attrs.get("is_seller")
    #     if is_seller:
    #         try:
    #             store = self.request.user.stores
    #         except ObjectDoesNotExist:
    #             raise ValidationError("No store exists for user")
    #     return attrs

    def create(self, validated_data):
        permissions = validated_data.pop("permissions", None)
        member = Member.objects.create(**validated_data)

        full_name = " ".join([
            member.first_name,
            member.last_name
        ])
        member.full_name = full_name
        member.save()

        if permissions:
            for permission in permissions:
                EcommMemberPermission.objects.create(
                    member=member, **permission)
        return member


class EditSuperAdminSerializer(serializers.ModelSerializer):
    permissions = EditEcommPermissionSerializer(many=True, required=False)
    password = serializers.CharField(write_only=True, required=False)
    permissions_to_delete = serializers.ListField(required=False)

    class Meta:
        model = Member
        fields = ('id', 'first_name', 'last_name', 'designation', 'company',
                  'email', 'has_full_access', 'password', 'permissions', 'status',
                  'permissions_to_delete')

    def validate_email(self, value):
        if value and value != "":
            if self.instance.email == value:
                return value
            if is_email_valid(value):
                try:
                    m = Member.objects.get(
                        email=value)
                except Member.DoesNotExist:
                    m = None
                if m is not None:
                    raise ValidationError("Email provided already exists.")
                else:
                    return value
            raise ValidationError("Email provided is invalid")
        raise ValidationError("Kindly enter your email.")

    def validate_password(self, value):
        if value and value != "":
            if len(value) < 8:
                raise ValidationError("Minimum 8 characters required for password")
            return value
        raise ValidationError("Kindly enter a password.")

    def update_or_add_permissions(self, instance, permissions):
        for permission_data in permissions:
            if permission_data.get("id") != 0:
                permission = get_object_or_404(
                    EcommMemberPermission, pk=permission_data.get("id"))
                permission.has_view_access = permission_data.get("has_view_access")
                permission.has_edit_access = permission_data.get("has_edit_access")
                permission.has_add_access = permission_data.get("has_add_access")
                permission.has_delete_access = permission_data.get("has_delete_access")
                permission.save()
            else:
                EcommMemberPermission.objects.update_or_create(
                    module=permission_data.get("module"),
                    member=instance,
                    defaults={
                        'has_view_access': permission_data.get("has_view_access"),
                        'has_edit_access': permission_data.get("has_edit_access"),
                        'has_add_access': permission_data.get("has_add_access"),
                        'has_delete_access': permission_data.get("has_delete_access")
                    })

    def update(self, instance, validated_data):
        permissions = validated_data.pop('permissions', None)
        permissions_to_delete = validated_data.get("permissions_to_delete", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if permissions:
            self.update_or_add_permissions(instance, permissions)

        if permissions_to_delete:
            EcommMemberPermission.objects.filter(
                pk__in=permissions_to_delete).delete()

        instance.save()
        return instance
