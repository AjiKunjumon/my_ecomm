import os
import sys

from django.conf import settings
from django.contrib.humanize.templatetags import humanize
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.images import get_image_dimensions
from django.core.validators import FileExtensionValidator
from django.db.models import F, Sum, Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import ValidationError

from app.authentication.serializers import SellerMinSerializer
from app.ecommnotification.serializers import CollectionSerializer
from app.order.serializers import SellerListByCategorySerializer
from app.product.serializers import ProductMinNewSerializer, CategorySuggestionSerializer
from app.store.models import Banner, TopDealsBanner
from app.utilities.helpers import convert_date_time_to_kuwait_string, datetime_from_utc_to_local_new, \
    datetime_from_utc_to_local


class BannerListSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    link = serializers.SerializerMethodField()
    seller = serializers.SerializerMethodField()
    product = serializers.SerializerMethodField()
    collection = serializers.SerializerMethodField()
    status_start_date = serializers.SerializerMethodField()
    status_end_date = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()

    class Meta:
        model = Banner
        fields = ('id', 'name', 'nameAR', 'status', 'status_start_date',
                  'status_end_date', 'type', 'link', 'banner_image',
                  'banner_image_ar', 'seller', 'product', 'collection', 'url',
                  'ordering_id', 'clicks', 'parent', 'category')

    def get_status(self, obj):
        return obj.get_status_display()

    def get_link(self, obj):
        return obj.get_link_display()

    def get_banner_image(self, obj):
        if obj.banner_image:
            return obj.banner_image.url
        return ""

    def get_banner_image_ar(self, obj):
        if obj.banner_image_ar:
            return obj.banner_image_ar.url
        return ""

    def get_seller(self, obj):
        if obj.seller:
            return SellerListByCategorySerializer(obj.seller).data
        return ""

    def get_product(self, obj):
        if obj.product:
            return ProductMinNewSerializer(obj.product).data
        return None

    def get_collection(self, obj):
        if obj.collection:
            return CollectionSerializer(obj.collection).data
        return None

    def get_category(self, obj):
        if obj.category:
            return CategorySuggestionSerializer(obj.category).data
        return None

    def get_status_start_date(self, obj):
        if obj.status_start_date:
            return obj.status_start_date
            # kuwait_date = datetime_from_utc_to_local(obj.status_start_date)
            # formatted_date = obj.status_start_date.strftime("%b %d, %Y")
            # formatted_time = obj.status_start_date.strftime("%H:%M %p")
            # return f"{formatted_date} at {formatted_time}"
        return None

    def get_status_end_date(self, obj):
        if obj.status_end_date:
            return obj.status_end_date
            # kuwait_date = datetime_from_utc_to_local(obj.status_end_date)
            # formatted_date = obj.status_end_date.strftime("%b %d, %Y")
            # formatted_time = obj.status_end_date.strftime("%H:%M %p")
            # return f"{formatted_date} at {formatted_time}"
        return None


class AddBannerSerializer(serializers.ModelSerializer):
    status_start_date = serializers.DateTimeField(
        required=True, format="%Y-%m-%d %H:%M:%S")
    status_end_date = serializers.DateTimeField(
        required=False, format="%Y-%m-%d %H:%M:%S")
    banner_image = serializers.ImageField(
        use_url=True,
        required=True, validators=[
            FileExtensionValidator(allowed_extensions=["png", "jpeg", "jpg"])
        ])
    banner_image_ar = serializers.ImageField(
        use_url=True,
        required=True, validators=[
            FileExtensionValidator(allowed_extensions=["png", "jpeg", "jpg"])
        ])

    class Meta:
        model = Banner
        fields = (
            "status", "status_start_date", "status_end_date", "type", "link",
            "banner_image", "banner_image_ar", "seller", "product", "collection",
            "url", "ordering_id"
        )

    def get_unique_together_validators(self):
        """Overriding method to disable unique together checks"""
        return []

    def check_image_dimensions(self, banner_type, banner_image, banner_image_ar):
        if banner_type == "APP":
            if settings.SITE_CODE != 1:
                if banner_image == "":
                    raise ValidationError("Please upload a banner image ")
                w1, h1 = get_image_dimensions(banner_image)
                if w1 != 764 or h1 != 330:
                    raise ValidationError(
                        {'banner_image': "Banner(English) image is not as per the required size"})

                if banner_image_ar == "":
                    raise ValidationError("Please upload a banner image arabic ")
                w2, h2 = get_image_dimensions(banner_image_ar)
                if w2 != 764 or h2 != 330:
                    raise ValidationError(
                        {'banner_image_ar': "Banner(Arabic) image is not as per the required size"})

        elif banner_type == "WEB":
            if settings.SITE_CODE != 1:
                if banner_image == "":
                    raise ValidationError("Please upload a banner image ")
                w3, h3 = get_image_dimensions(banner_image)
                if w3 != 1640 or h3 != 400:
                    raise ValidationError(
                        {'banner_image': "Banner(English) image is not as per the required size"})

                if banner_image_ar == "":
                    raise ValidationError("Please upload a banner image arabic ")
                w4, h4 = get_image_dimensions(banner_image_ar)
                if w4 != 1640 or h4 != 400:
                    raise ValidationError(
                        {'banner_image_ar': "Banner(Arabic) image is not as per the required size"})

    def validate(self, attrs):
        banner_image = attrs.get("banner_image")
        banner_image_ar = attrs.get("banner_image_ar")
        type = attrs.get("type")
        status = attrs.get("status")
        seller = attrs.get("seller")
        ordering_id = attrs.get("ordering_id")

        status_choices = ["AC", "SCH"]

        if status in status_choices:
            banners = Banner.objects.filter(
                type=type, seller=seller,
                ordering_id=ordering_id,
                status__in=status_choices
            )
            if banners.exists():
                raise ValidationError("Ordering id should be unique for status, type, seller")
            else:
                self.check_image_dimensions(type, banner_image, banner_image_ar)
        elif status == "IN":
            banners = Banner.objects.filter(
                type=type, seller=seller,
                ordering_id=ordering_id,
                status="IN"
            )
            if banners.exists():
                raise ValidationError("Ordering id should be unique for status, type, seller")
            else:
                self.check_image_dimensions(type, banner_image, banner_image_ar)
        return attrs

    def create(self, validated_data):
        return Banner.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.name = validated_data.get(
            "name", instance.name)
        instance.nameAR = validated_data.get(
            "nameAR", instance.name)
        instance.save()
        return instance


class EditBannerSerializer(serializers.ModelSerializer):
    status_start_date = serializers.DateTimeField(
        required=True, format="%Y-%m-%d %H:%M:%S")
    status_end_date = serializers.DateTimeField(
        required=False, format="%Y-%m-%d %H:%M:%S")
    banner_image = serializers.ImageField(
        use_url=True,
        required=True, validators=[
            FileExtensionValidator(allowed_extensions=["png", "jpeg", "jpg"])
        ])
    banner_image_ar = serializers.ImageField(
        use_url=True,
        required=True, validators=[
            FileExtensionValidator(allowed_extensions=["png", "jpeg", "jpg"])
        ])

    class Meta:
        model = Banner
        fields = (
            "status", "status_start_date", "status_end_date", "type", "link",
            "banner_image", "banner_image_ar", "seller", "product", "collection",
            "url", "ordering_id"
        )

    def check_image_dimensions(self, banner_type, banner_image, banner_image_ar):
        if banner_type == "APP":
            if settings.SITE_CODE != 1:
                if banner_image == "":
                    raise ValidationError("Please upload a banner image ")
                w, h = get_image_dimensions(banner_image)
                if w != 764 or h != 330:
                    raise ValidationError(
                        {'banner_image': "Banner(English) image is not as per the required size"})

                if banner_image_ar == "":
                    raise ValidationError("Please upload a banner image arabic ")
                w, h = get_image_dimensions(banner_image_ar)
                if w != 764 or h != 330:
                    raise ValidationError(
                        {'banner_image_ar': "Banner(Arabic) image is not as per the required size"})

        elif banner_type == "WEB":
            if settings.SITE_CODE != 1:
                if banner_image == "":
                    raise ValidationError("Please upload a banner image ")
                w, h = get_image_dimensions(banner_image)
                if w != 1640 or h != 400:
                    raise ValidationError(
                        {'banner_image': "Banner(English) image is not as per the required size"})

                if banner_image_ar == "":
                    raise ValidationError("Please upload a banner image arabic ")
                w, h = get_image_dimensions(banner_image_ar)
                if w != 1640 or h != 400:
                    raise ValidationError(
                        {'banner_image_ar': "Banner(Arabic) image is not as per the required size"})

    def validate(self, attrs):
        banner_image = attrs.get("banner_image")
        banner_image_ar = attrs.get("banner_image_ar")
        type = attrs.get("type")
        status = attrs.get("status")
        seller = attrs.get("seller")
        ordering_id = attrs.get("ordering_id")

        status_choices = ["AC", "SCH"]

        if status in status_choices:
            banners = Banner.objects.filter(
                type=type, seller=seller,
                ordering_id=ordering_id,
                status__in=status_choices
            ).exclude(pk=self.instance.pk)
            if banners.exists():
                raise ValidationError("Ordering id should be unique for status, type, seller")
            else:
                self.check_image_dimensions(type, banner_image, banner_image_ar)

        elif status == "IN":
            banners = Banner.objects.filter(
                type=type, seller=seller,
                ordering_id=ordering_id,
                status="IN"
            ).exclude(pk=self.instance.pk)
            if banners.exists():
                raise ValidationError("Ordering id should be unique for status, type, seller")
            else:
                self.check_image_dimensions(type, banner_image, banner_image_ar)
        return attrs

    def create(self, validated_data):
        return Banner.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.name = validated_data.get(
            "name", instance.name)
        instance.nameAR = validated_data.get(
            "nameAR", instance.name)
        instance.status_start_date = validated_data.get(
            "status_start_date", instance.status_start_date)

        if validated_data.get("status_end_date"):
            instance.status_end_date = validated_data.get(
                "status_end_date", instance.status_end_date)
        else:
            instance.status_end_date = None

        instance.status = validated_data.get(
            "status", instance.status)
        instance.type = validated_data.get(
            "type", instance.type)
        instance.link = validated_data.get(
            "link", instance.link)
        instance.ordering_id = validated_data.get(
            "ordering_id", instance.ordering_id)
        instance.seller = validated_data.get(
            "seller", instance.seller)

        if validated_data.get("url"):
            instance.url = validated_data.get(
                "url", instance.url)
        else:
            instance.url = None

        if validated_data.get("product"):
            instance.product = validated_data.get(
                "product", instance.product)
        else:
            instance.product = None

        if validated_data.get("collection"):
            instance.collection = validated_data.get(
                "collection", instance.collection)
        else:
            instance.collection = None

        instance.save()
        return instance


class BannerDetailSerializer(serializers.ModelSerializer):
    category = CategorySuggestionSerializer()
    product = ProductMinNewSerializer()
    collection = CollectionSerializer()
    seller = SellerMinSerializer()
    status_start_date = serializers.SerializerMethodField()
    status_end_date = serializers.SerializerMethodField()

    class Meta:
        model = Banner
        fields = (
            "id", "name", "nameAR", "status", "status_start_date",
            "status_end_date", "type", "link",
            "banner_image", "banner_image_ar", "seller", "product", "collection",
            "url", "ordering_id", "category", "parent", "is_for_homepage",
            "is_for_seller"
        )

    def get_status_start_date(self, obj):
        if obj.status_start_date:
            kuwait_date = datetime_from_utc_to_local(obj.status_start_date)
            return obj.status_start_date
            # return kuwait_date
        return None

    def get_status_end_date(self, obj):
        if obj.status_end_date:
            kuwait_date = datetime_from_utc_to_local(obj.status_end_date)
            return obj.status_end_date
            # return kuwait_date
        return None


class TopDealsBannerListSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    link = serializers.SerializerMethodField()
    seller = serializers.SerializerMethodField()
    product = serializers.SerializerMethodField()
    collection = serializers.SerializerMethodField()
    status_start_date = serializers.SerializerMethodField()
    status_end_date = serializers.SerializerMethodField()
    category = CategorySuggestionSerializer()

    class Meta:
        model = TopDealsBanner
        fields = ('id', 'name', 'nameAR', 'status', 'status_start_date',
                  'status_end_date', 'type', 'link', 'banner_image',
                  'banner_image_ar', 'seller', 'product', 'collection', 'url',
                  'clicks', 'parent', 'category')

    def get_status(self, obj):
        return obj.get_status_display()

    def get_link(self, obj):
        return obj.get_link_display()

    def get_banner_image(self, obj):
        if obj.banner_image:
            return obj.banner_image.url
        return ""

    def get_banner_image_ar(self, obj):
        if obj.banner_image_ar:
            return obj.banner_image_ar.url
        return ""

    def get_seller(self, obj):
        if obj.seller:
            return SellerListByCategorySerializer(obj.seller).data
        return ""

    def get_product(self, obj):
        if obj.product:
            return ProductMinNewSerializer(obj.product).data
        return None

    def get_collection(self, obj):
        if obj.collection:
            return CollectionSerializer(obj.collection).data
        return None

    def get_status_start_date(self, obj):
        if obj.status_start_date:
            return obj.status_start_date
            # kuwait_date = datetime_from_utc_to_local_new(obj.status_start_date)
            # formatted_date = obj.status_start_date.strftime("%b %d, %Y")
            # formatted_time = obj.status_start_date.strftime("%H:%M %p")
            # return f"{formatted_date} at {formatted_time}"
        return None

    def get_status_end_date(self, obj):
        if obj.status_end_date:
            return obj.status_end_date
            # kuwait_date = datetime_from_utc_to_local_new(obj.status_end_date)
            # formatted_date = obj.status_end_date.strftime("%b %d, %Y")
            # formatted_time = obj.status_end_date.strftime("%H:%M %p")
            # return f"{formatted_date} at {formatted_time}"
        return None


class TopDealsBannerDetailSerializer(serializers.ModelSerializer):
    category = CategorySuggestionSerializer()
    product = ProductMinNewSerializer()
    collection = CollectionSerializer()

    class Meta:
        model = TopDealsBanner
        fields = (
            "id", "status", "status_start_date", "status_end_date", "type", "link",
            "banner_image", "banner_image_ar", "product", "collection",
            "url", "category", "parent"
        )


class AddHomePageBannerSerializer(serializers.ModelSerializer):
    status_start_date = serializers.DateTimeField(
        required=True, format="%Y-%m-%d %H:%M:%S")
    status_end_date = serializers.DateTimeField(
        required=False, format="%Y-%m-%d %H:%M:%S")
    banner_image = serializers.ImageField(
        use_url=True,
        required=True, validators=[
            FileExtensionValidator(allowed_extensions=["png", "jpeg", "jpg"])
        ])
    banner_image_ar = serializers.ImageField(
        use_url=True,
        required=True, validators=[
            FileExtensionValidator(allowed_extensions=["png", "jpeg", "jpg"])
        ])

    class Meta:
        model = Banner
        fields = (
            "name", "nameAR", "parent",
            "status", "status_start_date", "status_end_date", "type", "link",
            "banner_image", "banner_image_ar", "category", "product", "collection",
            "url", "ordering_id"
        )

    def check_image_dimensions(self, type, banner_image, banner_image_ar):
        if type == "APP":
            if settings.SITE_CODE != 1:
                if banner_image == "":
                    raise ValidationError("Please upload a banner image ")
                w, h = get_image_dimensions(banner_image)
                if w != 764 or h != 330:
                    raise ValidationError(
                        {'banner_image': "Banner(English) image is not as per the required size"})

                if banner_image_ar == "":
                    raise ValidationError("Please upload a banner image arabic ")
                w, h = get_image_dimensions(banner_image_ar)
                if w != 764 or h != 330:
                    raise ValidationError(
                        {'banner_image_ar': "Banner(Arabic) image is not as per the required size"})

        elif type == "WEB":
            if settings.SITE_CODE != 1:
                if banner_image == "":
                    raise ValidationError("Please upload a banner image ")
                w, h = get_image_dimensions(banner_image)
                if w != 1640 or h != 400:
                    raise ValidationError(
                        {'banner_image': "Banner(English) image is not as per the required size"})

                if banner_image_ar == "":
                    raise ValidationError("Please upload a banner image arabic ")
                w, h = get_image_dimensions(banner_image_ar)
                if w != 1640 or h != 400:
                    raise ValidationError(
                        {'banner_image_ar': "Banner(Arabic) image is not as per the required size"})

    def validate(self, attrs):
        parent = attrs.get("parent")
        banner_image = attrs.get("banner_image")
        banner_image_ar = attrs.get("banner_image_ar")
        type = attrs.get("type")
        status = attrs.get("status")
        ordering_id = attrs.get("ordering_id")

        status_choices = ["AC", "SCH"]

        if status in status_choices:
            banners = Banner.objects.filter(
                type=type, is_for_homepage=True,
                parent=parent,
                ordering_id=ordering_id,
                status__in=status_choices
            )
            if banners.exists():
                raise ValidationError("Ordering id should be unique for status, type")
            else:
                self.check_image_dimensions(type, banner_image, banner_image_ar)

        elif status == "IN":
            banners = Banner.objects.filter(
                type=type, is_for_homepage=True,
                parent=parent,
                ordering_id=ordering_id,
                status="IN"
            )
            if banners.exists():
                raise ValidationError("Ordering id should be unique for status, type")
            else:
                self.check_image_dimensions(type, banner_image, banner_image_ar)
        return attrs

    def create(self, validated_data):
        return Banner.objects.create(is_for_homepage=True, **validated_data)


class EditHomePageBannerSerializer(serializers.ModelSerializer):
    status_start_date = serializers.DateTimeField(
        required=True, format="%Y-%m-%d %H:%M:%S")
    status_end_date = serializers.DateTimeField(
        required=False, format="%Y-%m-%d %H:%M:%S")
    banner_image = serializers.ImageField(
        use_url=True,
        required=True, validators=[
            FileExtensionValidator(allowed_extensions=["png", "jpeg", "jpg"])
        ])
    banner_image_ar = serializers.ImageField(
        use_url=True,
        required=True, validators=[
            FileExtensionValidator(allowed_extensions=["png", "jpeg", "jpg"])
        ])

    class Meta:
        model = Banner
        fields = (
            "status", "status_start_date", "status_end_date", "type", "link",
            "banner_image", "banner_image_ar", "category", "product", "collection",
            "url", "ordering_id"
        )

    def check_image_dimensions(self, type, banner_image, banner_image_ar):
        if type == "APP":
            if settings.SITE_CODE != 1:
                if banner_image == "":
                    raise ValidationError("Please upload a banner image ")
                w, h = get_image_dimensions(banner_image)
                if w != 764 or h != 330:
                    raise ValidationError(
                        {'banner_image': "Banner(English) image is not as per the required size"})

                if banner_image_ar == "":
                    raise ValidationError("Please upload a banner image arabic ")
                w, h = get_image_dimensions(banner_image_ar)
                if w != 764 or h != 330:
                    raise ValidationError(
                        {'banner_image_ar': "Banner(Arabic) image is not as per the required size"})

        elif type == "WEB":
            if settings.SITE_CODE != 1:
                if banner_image == "":
                    raise ValidationError("Please upload a banner image ")
                w, h = get_image_dimensions(banner_image)
                if w != 1640 or h != 400:
                    raise ValidationError(
                        {'banner_image': "Banner(English) image is not as per the required size"})

                if banner_image_ar == "":
                    raise ValidationError("Please upload a banner image arabic ")
                w, h = get_image_dimensions(banner_image_ar)
                if w != 1640 or h != 400:
                    raise ValidationError(
                        {'banner_image_ar': "Banner(Arabic) image is not as per the required size"})

    def validate(self, attrs):
        banner_image = attrs.get("banner_image")
        banner_image_ar = attrs.get("banner_image_ar")
        type = attrs.get("type")
        status = attrs.get("status")
        ordering_id = attrs.get("ordering_id")

        status_choices = ["AC", "SCH"]

        if status in status_choices:
            banners = Banner.objects.filter(
                type=type, is_for_homepage=True,
                parent=self.instance.parent,
                ordering_id=ordering_id,
                status__in=status_choices
            ).exclude(pk=self.instance.pk)
            if banners.exists():
                raise ValidationError("Ordering id should be unique for status, type")
            else:
                self.check_image_dimensions(type, banner_image, banner_image_ar)

        elif status == "IN":
            banners = Banner.objects.filter(
                type=type, is_for_homepage=True,
                ordering_id=ordering_id,
                parent=self.instance.parent,
                status="IN"
            ).exclude(pk=self.instance.pk)
            if banners.exists():
                raise ValidationError("Ordering id should be unique for status, type")
            else:
                self.check_image_dimensions(type, banner_image, banner_image_ar)
        return attrs

    def update(self, instance, validated_data):
        instance.name = validated_data.get(
            "name", instance.name)
        instance.nameAR = validated_data.get(
            "nameAR", instance.name)
        instance.status_start_date = validated_data.get(
            "status_start_date", instance.status_start_date)
        if validated_data.get("status_end_date"):
            instance.status_end_date = validated_data.get(
                "status_end_date", instance.status_end_date)
        else:
            instance.status_end_date = None

        instance.status = validated_data.get(
            "status", instance.status)
        instance.type = validated_data.get(
            "type", instance.type)
        instance.link = validated_data.get(
            "link", instance.link)
        instance.ordering_id = validated_data.get(
            "ordering_id", instance.ordering_id)

        if validated_data.get("category"):
            instance.category = validated_data.get(
                "category", instance.category)
        else:
            instance.category = None

        if validated_data.get("product"):
            instance.product = validated_data.get(
                "product", instance.product)
        else:
            instance.product = None

        if validated_data.get("collection"):
            instance.collection = validated_data.get(
                "collection", instance.collection)
        else:
            instance.collection = None

        instance.save()
        return instance


class AddNewArrivalBannerSerializer(serializers.ModelSerializer):
    status_start_date = serializers.DateTimeField(
        required=True, format="%Y-%m-%d %H:%M:%S")
    status_end_date = serializers.DateTimeField(
        required=False, format="%Y-%m-%d %H:%M:%S")
    banner_image = serializers.ImageField(
        use_url=True,
        required=True, validators=[
            FileExtensionValidator(allowed_extensions=["png", "jpeg", "jpg"])
        ])
    banner_image_ar = serializers.ImageField(
        use_url=True,
        required=True, validators=[
            FileExtensionValidator(allowed_extensions=["png", "jpeg", "jpg"])
        ])

    class Meta:
        model = Banner
        fields = (
            "name", "nameAR", "parent",
            "status", "status_start_date", "status_end_date", "type", "link",
            "banner_image", "banner_image_ar", "category", "product", "collection",
            "url", "ordering_id"
        )

    def check_image_dimensions(self, type, banner_image, banner_image_ar):
        if type == "APP":
            if settings.SITE_CODE != 1:
                if banner_image == "":
                    raise ValidationError("Please upload a banner image ")
                w, h = get_image_dimensions(banner_image)
                if w != 426 or h != 604:
                    raise ValidationError(
                        {'banner_image': "Banner(English) image is not as per the required size"})

                if banner_image_ar == "":
                    raise ValidationError("Please upload a banner image arabic ")
                w, h = get_image_dimensions(banner_image_ar)
                if w != 426 or h != 604:
                    raise ValidationError(
                        {'banner_image_ar': "Banner(Arabic) image is not as per the required size"})

        elif type == "WEB":
            if settings.SITE_CODE != 1:
                if banner_image == "":
                    raise ValidationError("Please upload a banner image ")
                w, h = get_image_dimensions(banner_image)
                if w != 300 or h != 300:
                    raise ValidationError(
                        {'banner_image': "Banner(English) image is not as per the required size"})

                if banner_image_ar == "":
                    raise ValidationError("Please upload a banner image arabic ")
                w, h = get_image_dimensions(banner_image_ar)
                if w != 300 or h != 300:
                    raise ValidationError(
                        {'banner_image_ar': "Banner(Arabic) image is not as per the required size"})

    def validate(self, attrs):
        parent = attrs.get("parent")

        if parent.name != "New Arrivals":
            raise ValidationError("Parent banner should be New Arrivals")
        else:
            parent = attrs.get("parent")
            banner_image = attrs.get("banner_image")
            banner_image_ar = attrs.get("banner_image_ar")
            type = attrs.get("type")
            status = attrs.get("status")
            ordering_id = attrs.get("ordering_id")

            status_choices = ["AC", "SCH"]

            if status in status_choices:
                banners = Banner.objects.filter(
                    type=type, is_for_homepage=True,
                    parent=parent,
                    ordering_id=ordering_id,
                    status__in=status_choices
                )
                if banners.exists():
                    raise ValidationError("Ordering id should be unique for status, type")
                else:
                    self.check_image_dimensions(type, banner_image, banner_image_ar)

            elif status == "IN":
                banners = Banner.objects.filter(
                    type=type, is_for_homepage=True,
                    ordering_id=ordering_id,
                    parent=parent,
                    status="IN"
                )
                if banners.exists():
                    raise ValidationError("Ordering id should be unique for status, type")
                else:
                    self.check_image_dimensions(type, banner_image, banner_image_ar)
        return attrs

    def create(self, validated_data):
        return Banner.objects.create(**validated_data)


class EditNewArrivalBannerSerializer(serializers.ModelSerializer):
    status_start_date = serializers.DateTimeField(
        required=True, format="%Y-%m-%d %H:%M:%S")
    status_end_date = serializers.DateTimeField(
        required=False, format="%Y-%m-%d %H:%M:%S")
    banner_image = serializers.ImageField(
        use_url=True,
        required=True, validators=[
            FileExtensionValidator(allowed_extensions=["png", "jpeg", "jpg"])
        ])
    banner_image_ar = serializers.ImageField(
        use_url=True,
        required=True, validators=[
            FileExtensionValidator(allowed_extensions=["png", "jpeg", "jpg"])
        ])

    class Meta:
        model = Banner
        fields = (
            "status", "status_start_date", "status_end_date", "type", "link",
            "banner_image", "banner_image_ar", "category", "product", "collection",
            "url", "ordering_id"
        )

    def check_image_dimensions(self, type, banner_image, banner_image_ar):
        if type == "APP":
            if settings.SITE_CODE != 1:
                if banner_image == "":
                    raise ValidationError("Please upload a banner image ")
                w, h = get_image_dimensions(banner_image)
                if w != 426 or h != 604:
                    raise ValidationError(
                        {'banner_image': "Banner(English) image is not as per the required size"})

                if banner_image_ar == "":
                    raise ValidationError("Please upload a banner image arabic ")
                w, h = get_image_dimensions(banner_image_ar)
                if w != 426 or h != 604:
                    raise ValidationError(
                        {'banner_image_ar': "Banner(Arabic) image is not as per the required size"})

        elif type == "WEB":
            if settings.SITE_CODE != 1:
                if banner_image == "":
                    raise ValidationError("Please upload a banner image ")
                w, h = get_image_dimensions(banner_image)
                if w != 300 or h != 300:
                    raise ValidationError(
                        {'banner_image': "Banner(English) image is not as per the required size"})

                if banner_image_ar == "":
                    raise ValidationError("Please upload a banner image arabic ")
                w, h = get_image_dimensions(banner_image_ar)
                if w != 300 or h != 300:
                    raise ValidationError(
                        {'banner_image_ar': "Banner(Arabic) image is not as per the required size"})

    def validate(self, attrs):
        banner_image = attrs.get("banner_image")
        banner_image_ar = attrs.get("banner_image_ar")
        type = attrs.get("type")
        status = attrs.get("status")
        ordering_id = attrs.get("ordering_id")

        status_choices = ["AC", "SCH"]

        if status in status_choices:
            banners = Banner.objects.filter(
                type=type, is_for_homepage=True,
                parent__name='New Arrivals',
                ordering_id=ordering_id,
                status__in=status_choices
            ).exclude(pk=self.instance.pk)
            if banners.exists():
                raise ValidationError("Ordering id should be unique for status, type")
            else:
                self.check_image_dimensions(type, banner_image, banner_image_ar)

        elif status == "IN":
            banners = Banner.objects.filter(
                type=type, is_for_homepage=True,
                ordering_id=ordering_id,
                parent__name='New Arrivals',
                status="IN"
            ).exclude(pk=self.instance.pk)
            if banners.exists():
                raise ValidationError("Ordering id should be unique for status, type")
            else:
                self.check_image_dimensions(type, banner_image, banner_image_ar)
        return attrs

    def update(self, instance, validated_data):
        instance.status_start_date = validated_data.get(
            "status_start_date", instance.status_start_date)
        if validated_data.get("status_end_date"):
            instance.status_end_date = validated_data.get(
                "status_end_date", instance.status_end_date)
        else:
            instance.status_end_date = None

        instance.status = validated_data.get(
            "status", instance.status)
        instance.type = validated_data.get(
            "type", instance.type)
        instance.link = validated_data.get(
            "link", instance.link)
        instance.ordering_id = validated_data.get(
            "ordering_id", instance.ordering_id)

        if validated_data.get("category"):
            instance.category = validated_data.get(
                "category", instance.category)
        else:
            instance.category = None

        if validated_data.get("product"):
            instance.product = validated_data.get(
                "product", instance.product)
        else:
            instance.product = None

        if validated_data.get("collection"):
            instance.collection = validated_data.get(
                "collection", instance.collection)
        else:
            instance.collection = None

        instance.save()
        return instance


class AddTopDealsBannerSerializer(serializers.ModelSerializer):
    status_start_date = serializers.DateTimeField(
        required=True, format="%Y-%m-%d %H:%M:%S")
    status_end_date = serializers.DateTimeField(
        required=False, format="%Y-%m-%d %H:%M:%S")
    banner_image = serializers.ImageField(
        use_url=True,
        required=True, validators=[
            FileExtensionValidator(allowed_extensions=["png", "jpeg", "jpg"])
        ])
    banner_image_ar = serializers.ImageField(
        use_url=True,
        required=True, validators=[
            FileExtensionValidator(allowed_extensions=["png", "jpeg", "jpg"])
        ])

    class Meta:
        model = TopDealsBanner
        fields = (
            "name", "nameAR",
            "status", "status_start_date", "status_end_date", "type", "link",
            "banner_image", "banner_image_ar", "category", "product", "collection",
            "url"
        )

    def validate(self, attrs):
        banner_image = attrs.get("banner_image")
        banner_image_ar = attrs.get("banner_image_ar")
        type = attrs.get("type")

        if type == "APP":
            if settings.SITE_CODE != 1:
                if banner_image == "":
                    raise ValidationError("Please upload a banner image ")
                w, h = get_image_dimensions(banner_image)
                if w != 764 or h != 330:
                    raise ValidationError(
                        {'banner_image': "Banner(English) image is not as per the required size"})

                if banner_image_ar == "":
                    raise ValidationError("Please upload a banner image arabic ")
                w, h = get_image_dimensions(banner_image_ar)
                if w != 764 or h != 330:
                    raise ValidationError(
                        {'banner_image_ar': "Banner(Arabic) image is not as per the required size"})
                return attrs

        elif type == "WEB":
            if settings.SITE_CODE != 1:
                if banner_image == "":
                    raise ValidationError("Please upload a banner image ")
                w, h = get_image_dimensions(banner_image)
                if w != 1640 or h != 400:
                    raise ValidationError(
                        {'banner_image': "Banner(English) image is not as per the required size"})

                if banner_image_ar == "":
                    raise ValidationError("Please upload a banner image arabic ")
                w, h = get_image_dimensions(banner_image_ar)
                if w != 1640 or h != 400:
                    raise ValidationError(
                        {'banner_image_ar': "Banner(Arabic) image is not as per the required size"})
                return attrs

    def create(self, validated_data):
        return TopDealsBanner.objects.create(**validated_data)


class EditTopDealsBannerSerializer(serializers.ModelSerializer):
    status_start_date = serializers.DateTimeField(
        required=True, format="%Y-%m-%d %H:%M:%S")
    status_end_date = serializers.DateTimeField(
        required=False, format="%Y-%m-%d %H:%M:%S")
    banner_image = serializers.ImageField(
        use_url=True,
        required=True, validators=[
            FileExtensionValidator(allowed_extensions=["png", "jpeg", "jpg"])
        ])
    banner_image_ar = serializers.ImageField(
        use_url=True,
        required=True, validators=[
            FileExtensionValidator(allowed_extensions=["png", "jpeg", "jpg"])
        ])

    class Meta:
        model = TopDealsBanner
        fields = (
            "status", "status_start_date", "status_end_date", "type", "link",
            "banner_image", "banner_image_ar", "category", "product", "collection",
            "url"
        )

    def validate(self, attrs):
        banner_image = attrs.get("banner_image")
        banner_image_ar = attrs.get("banner_image_ar")
        type = attrs.get("type")

        if type == "APP":
            if settings.SITE_CODE != 1:
                if banner_image == "":
                    raise ValidationError("Please upload a banner image ")
                w, h = get_image_dimensions(banner_image)
                if w != 764 or h != 330:
                    raise ValidationError(
                        {'banner_image': "Banner(English) image is not as per the required size"})

                if banner_image_ar == "":
                    raise ValidationError("Please upload a banner image arabic ")
                w, h = get_image_dimensions(banner_image_ar)
                if w != 764 or h != 330:
                    raise ValidationError(
                        {'banner_image_ar': "Banner(Arabic) image is not as per the required size"})
                return attrs

        elif type == "WEB":
            if settings.SITE_CODE != 1:
                if banner_image == "":
                    raise ValidationError("Please upload a banner image ")
                w, h = get_image_dimensions(banner_image)
                if w != 1640 or h != 400:
                    raise ValidationError(
                        {'banner_image': "Banner(English) image is not as per the required size"})

                if banner_image_ar == "":
                    raise ValidationError("Please upload a banner image arabic ")
                w, h = get_image_dimensions(banner_image_ar)
                if w != 1640 or h != 400:
                    raise ValidationError(
                        {'banner_image_ar': "Banner(Arabic) image is not as per the required size"})
                return attrs

    def update(self, instance, validated_data):
        instance.name = validated_data.get(
            "name", instance.name)
        instance.nameAR = validated_data.get(
            "nameAR", instance.name)
        instance.status_start_date = validated_data.get(
            "status_start_date", instance.status_start_date)

        if validated_data.get("status_end_date"):
            instance.status_end_date = validated_data.get(
                "status_end_date", instance.status_end_date)
        else:
            instance.status_end_date = None

        instance.status = validated_data.get(
            "status", instance.status)
        instance.type = validated_data.get(
            "type", instance.type)
        instance.link = validated_data.get(
            "link", instance.link)

        instance.category = validated_data.get(
            "category", instance.category)
        instance.product = validated_data.get(
            "product", instance.product)
        instance.collection = validated_data.get(
            "collection", instance.collection)

        instance.save()
        return instance
