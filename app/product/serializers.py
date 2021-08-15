import os
import sys
from datetime import timedelta
from io import BytesIO

import boto3
from PIL import Image
from django.conf import settings
from django.contrib.humanize.templatetags import humanize
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.images import get_image_dimensions
from django.core.validators import FileExtensionValidator
from django.db.models import F, Sum, Count, Q, Avg
from django.shortcuts import get_object_or_404
from django.utils.timezone import now
from rest_framework import serializers
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import ValidationError

from app.authentication.models import Member
from app.product.models import Brand, Category, EcommProduct, ProductSpecification, Variant, VariantValues, \
    EcommProductMedia, ProductVariantValue, SearchKeyWord, SearchKeyWordAR, EcommProductRatingandReview, \
    ProductCollection, ProductCollectionCond, Coupon, Discount
from app.product.utils import rating_string
from app.store.models import Store, InventoryProduct, Inventory
from app.utilities.helpers import get_ecomm_prod_media_key_and_path, get_presigned_url, report_to_developer, str2bool, \
    convert_date_time_to_kuwait_string, datetime_from_utc_to_local_new


class NestedCollectionSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=True)

    class Meta:
        model = ProductCollection
        fields = ('id', )


class BrandListSerializer(serializers.ModelSerializer):
    seller_names = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    brand_status = serializers.SerializerMethodField()
    prods_linked = serializers.SerializerMethodField()

    class Meta:
        model = Brand
        fields = (
            "id", "name", "image",
            "seller_names", "brand_status",
            "prods_linked"
        )

    def get_name(self, obj):
        lang_code = self.context.get("lang_code")
        if lang_code == "ar":
            return obj.nameAR
        return obj.name

    def get_seller_names(self, obj):
        lang_code = self.context.get("lang_code")
        if obj.products.exists():
            if lang_code == "ar":
                store_names = obj.products.all().values_list(
                    'store__nameAR').order_by(
                    'store__nameAR').distinct('store__nameAR')
                return store_names
            store_names = obj.products.all().values_list(
                'store__name').order_by(
                'store__name').distinct('store__name')
            return store_names
        return None

    def get_brand_status(self, obj):
        lang_code = self.context.get("lang_code")
        if obj.is_top_brand:
            return "Top Brand"
        return "Other"

    def get_prods_linked(self, obj):
        prod_count = obj.products.all().annotate(
            variant_count=Count('productVariantValue', distinct=True)).exclude(
            Q(variant_count=0, parent__isnull=False)
            | Q(parent=None, children__isnull=False)).count()
        return prod_count
        # if obj.products.all().filter(
        #         parent__isnull=False).exists():
        #     return obj.products.all().filter(
        #         parent__isnull=False).count()
        # return 0


class BrandListFilterSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = Brand
        fields = (
            "id", "name",
        )

    def get_name(self, obj):
        lang_code = self.context.get("lang_code")
        if lang_code == "ar":
            return obj.nameAR
        return obj.name


class AddEditBrandSerializer(serializers.ModelSerializer):
    logo = serializers.ImageField(
        source='image', use_url=True,
        required=True, validators=[
            FileExtensionValidator(allowed_extensions=["png", "jpeg", "jpg"])
        ])
    cover = serializers.ImageField(
        use_url=True, required=True, validators=[
            FileExtensionValidator(allowed_extensions=["png", "jpeg", "jpg"])
        ])

    class Meta:
        model = Brand
        fields = (
            "name", "nameAR", "is_top_brand", "logo", "cover",
        )

    def validate_name(self, value):
        try:
            brand = Brand.objects.get(name=value)
        except Brand.DoesNotExist:
            return value
        if brand:
            raise ValidationError("Brand with name already exists")

    def validate_nameAR(self, value):
        try:
            brand = Brand.objects.get(nameAR=value)
        except Brand.DoesNotExist:
            return value
        if brand:
            raise ValidationError("Brand with arabic name already exists")

    def validate_logo(self, value):
        if settings.SITE_CODE != 1:
            if value == "":
                raise ValidationError("Please upload an image ")
            w, h = get_image_dimensions(value)
            if w != 512:
                raise ValidationError("Image is not as per the required size")
            if h != 512:
                raise ValidationError("Image is not as per the required size")
        return value

    def validate_cover(self, value):
        if settings.SITE_CODE != 1:
            if value == "":
                raise ValidationError("Please upload an image ")
            w, h = get_image_dimensions(value)
            if w != 246:
                raise ValidationError("Image is not as per the required size")
            if h != 110:
                raise ValidationError("Image is not as per the required size")
        return value

    def create(self, validated_data):
        return Brand.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.name = validated_data.get(
            "name", instance.name)
        instance.nameAR = validated_data.get(
            "nameAR", instance.name)
        instance.name = validated_data.get(
            "name", instance.name)
        instance.is_top_brand = validated_data.get(
            "is_top_brand", instance.is_top_brand)
        instance.save()
        return instance


class EditBrandSerializer(serializers.ModelSerializer):
    logo = serializers.ImageField(
        source='image', use_url=True,
        required=True, validators=[
            FileExtensionValidator(allowed_extensions=["png", "jpeg", "jpg"])
        ])
    cover = serializers.ImageField(
        use_url=True, required=True, validators=[
            FileExtensionValidator(allowed_extensions=["png", "jpeg", "jpg"])
        ])

    class Meta:
        model = Brand
        fields = (
            "name", "nameAR", "is_top_brand", "logo", "cover",
        )

    def validate_name(self, value):
        if self.instance.name == value:
            return value
        if Brand.objects.filter(name__exact=value).exists():
            raise ValidationError("Brand with name already exists")
        return value

    def validate_nameAR(self, value):
        if self.instance.nameAR == value:
            return value
        if Brand.objects.filter(nameAR__exact=value).exists():
            raise ValidationError("Brand with arabic name already exists")
        return value

    def validate_logo(self, value):
        if settings.SITE_CODE != 1:
            if value == "":
                raise ValidationError("Please upload an image ")
            w, h = get_image_dimensions(value)
            if w != 512:
                raise ValidationError("Image is not as per the required size")
            if h != 512:
                raise ValidationError("Image is not as per the required size")
        return value

    def validate_cover(self, value):
        if settings.SITE_CODE != 1:
            if value == "":
                raise ValidationError("Please upload an image ")
            w, h = get_image_dimensions(value)
            if w != 246:
                raise ValidationError("Image is not as per the required size")
            if h != 110:
                raise ValidationError("Image is not as per the required size")
        return value

    def update(self, instance, validated_data):
        instance.name = validated_data.get(
            "name", instance.name)
        instance.nameAR = validated_data.get(
            "nameAR", instance.nameAR)
        instance.is_top_brand = validated_data.get(
            "is_top_brand", instance.is_top_brand)
        instance.save()
        return instance


class BrandSerializer(serializers.ModelSerializer):
    logo = serializers.SerializerMethodField()
    prods_linked = serializers.SerializerMethodField()

    class Meta:
        model = Brand
        fields = (
            "id", "name", "nameAR", "logo",
            "is_top_brand", "cover", "prods_linked"
        )

    def get_logo(self, obj):
        if obj.image:
            return obj.image.url
        return None

    def get_prods_linked(self, obj):
        prod_count = obj.products.all().annotate(
            variant_count=Count('productVariantValue', distinct=True)).exclude(
            Q(variant_count=0, parent__isnull=False)
            | Q(parent=None, children__isnull=False)).count()
        return prod_count

        # if obj.products.all().filter(
        #         parent__isnull=False).exists():
        #     return obj.products.all().filter(
        #         parent__isnull=False).count()
        # return 0


class CategoryListSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()
    prods_linked = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    parent_name_chain = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = (
            "id", "name", "image", "status",
            "type", "prods_linked", "parent_name_chain"
        )

    def get_status(self, obj):
        return obj.get_status_display()

    def get_parent_name_chain(self, obj):
        if obj.parent:
            return '>'.join(
                [obj.name, obj.parent.get_parent_name_chain()]
            )
        else:
            return '>'.join(
                [obj.name]
            )

    def get_name(self, obj):
        lang_code = self.context.get("lang_code")
        if lang_code == "ar":
            return obj.nameAR
        return obj.name

    def get_prods_linked(self, obj):
        descendants = Category.objects.descendants(obj)
        sum = 0
        for category in descendants:
            prod_count = category.products.all().annotate(
                variant_count=Count('productVariantValue', distinct=True)).exclude(
                Q(variant_count=0, parent__isnull=False)
                | Q(parent=None, children__isnull=False)).count()
            sum += prod_count
        return sum

        # cat_desc_prod_count = Category.objects.descendants(obj).annotate(
        #     prod_count=Count('products__children')
        # ).values_list('prod_count', flat=True).aggregate(
        #     Sum('prod_count')).get('prod_count__sum')
        # if cat_desc_prod_count:
        #     return cat_desc_prod_count
        # return None

    def get_type(self, obj):
        if not obj.parent:
            return "Main Category"
        ancestors_count = Category.objects.ancestors(obj).exclude(
            id=obj.id).count()

        if ancestors_count == 1:
            return "Sub Category"
        elif ancestors_count == 2:
            return "Product Type"
        elif ancestors_count == 3:
            return "Sub Product Type"

    def get_image(self, obj):
        if obj.medias.exists():
            return obj.medias.filter(
                type='im2'
            ).first().media.url
        return None


class AddEditCategorySerializer(serializers.Serializer):
    home_page_thumbnail = serializers.ImageField(
        use_url=True,
        required=True, validators=[
            FileExtensionValidator(allowed_extensions=["png", "jpeg", "jpg"])
        ])
    home_page_thumbnail_ar = serializers.ImageField(
        use_url=True,
        required=True, validators=[
            FileExtensionValidator(allowed_extensions=["png", "jpeg", "jpg"])
        ])
    image_1 = serializers.ImageField(
        use_url=True, required=True, validators=[
            FileExtensionValidator(allowed_extensions=["png", "jpeg", "jpg"])
        ])
    image_2 = serializers.ImageField(
        use_url=True, required=True, validators=[
            FileExtensionValidator(allowed_extensions=["png", "jpeg", "jpg"])
        ])
    image_3 = serializers.ImageField(
        use_url=True, required=True, validators=[
            FileExtensionValidator(allowed_extensions=["png", "jpeg", "jpg"])
        ])
    name = serializers.CharField(required=True)
    nameAR = serializers.CharField(required=True)

    class Meta:
        model = Category
        fields = (
            "name", "nameAR", "home_page_thumbnail",
            "home_page_thumbnail_ar",
            "image_1", "image_2", "image_3"
        )

    def validate_home_page_thumbnail(self, value):
        if settings.SITE_CODE != 1:
            if value == "":
                raise ValidationError("Please upload an image ")
            w, h = get_image_dimensions(value)
            if w != 304:
                raise ValidationError("Image is not as per the required size")
            if h != 120:
                raise ValidationError("Image is not as per the required size")
        return value

    def validate_home_page_thumbnail_ar(self, value):
        if settings.SITE_CODE != 1:
            if value == "":
                raise ValidationError("Please upload an image ")
            w, h = get_image_dimensions(value)
            if w != 304:
                raise ValidationError("Image is not as per the required size")
            if h != 120:
                raise ValidationError("Image is not as per the required size")
        return value

    def validate_image_1(self, value):
        if settings.SITE_CODE != 1:
            if value == "":
                raise ValidationError("Please upload an image ")
            w, h = get_image_dimensions(value)
            if w != 764:
                raise ValidationError("Image is not as per the required size")
            if h != 366:
                raise ValidationError("Image is not as per the required size")
        return value

    def validate_image_2(self, value):
        if settings.SITE_CODE != 1:
            if value == "":
                raise ValidationError("Please upload an image ")
            w, h = get_image_dimensions(value)
            if w != 366:
                raise ValidationError("Image is not as per the required size")
            if h != 366:
                raise ValidationError("Image is not as per the required size")
        return value

    def validate_image_3(self, value):
        if settings.SITE_CODE != 1:
            if value == "":
                raise ValidationError("Please upload an image ")
            w, h = get_image_dimensions(value)
            if w != 366:
                raise ValidationError("Image is not as per the required size")
            if h != 488:
                raise ValidationError("Image is not as per the required size")
        return value

    def create(self, validated_data):
        image_1 = validated_data.pop("image_1")
        image_2 = validated_data.pop("image_2")
        image_3 = validated_data.pop("image_3")
        return Category.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.name = validated_data.get("name", instance.name)
        instance.nameAR = validated_data.get("nameAR", instance.nameAR)
        instance.save()
        return instance


class CategorySerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()
    prods_linked = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    image_1 = serializers.SerializerMethodField()
    image_2 = serializers.SerializerMethodField()
    image_3 = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = (
            "id", "name", "nameAR", "image_1",
            "image_2", "image_3", "status",
            "type", "prods_linked", "home_page_thumbnail",
            "home_page_thumbnail_ar"
        )

    def get_status(self, obj):
        return obj.get_status_display()

    def get_image_1(self, obj):
        if obj.medias.filter(type='im1').exists():
            im1_media = obj.medias.filter(
                type='im1'
            ).latest('id')
            if im1_media.media:
                return im1_media.media.url
            return None
        return None

    def get_image_2(self, obj):
        if obj.medias.filter(type='im2').exists():
            im2_media = obj.medias.filter(
                type='im2'
            ).latest('id')
            if im2_media.media:
                return im2_media.media.url
            return None
        return None

    def get_image_3(self, obj):
        if obj.medias.filter(type='im3').exists():
            im3_media = obj.medias.filter(
                type='im3'
            ).latest('id')
            if im3_media.media:
                return im3_media.media.url
            return None
        return None

    def get_prods_linked(self, obj):
        descendants = Category.objects.descendants(obj)
        sum = 0
        for category in descendants:
            prod_count = category.products.all().annotate(
                variant_count=Count('productVariantValue', distinct=True)).exclude(
                Q(variant_count=0, parent__isnull=False)
                | Q(parent=None, children__isnull=False)).count()
            sum += prod_count
        return sum

        # cat_desc_prod_count = Category.objects.descendants(obj).annotate(
        #     prod_count=Count('products__children')
        # ).values_list('prod_count', flat=True).aggregate(
        #     Sum('prod_count')).get('prod_count__sum')
        # if cat_desc_prod_count:
        #     return cat_desc_prod_count
        # return None

    def get_type(self, obj):
        if not obj.parent:
            return "Main Category"
        ancestors_count = Category.objects.ancestors(obj).exclude(
            id=obj.id).count()

        if ancestors_count == 1:
            return "Sub Category"
        elif ancestors_count == 2:
            return "Product Type"
        elif ancestors_count == 3:
            return "Sub Product Type"


class CategoryCommissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = (
            "id", "name", "nameAR",
        )


class CategoryNotificationSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()
    prods_linked = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    image_1 = serializers.SerializerMethodField()
    image_2 = serializers.SerializerMethodField()
    image_3 = serializers.SerializerMethodField()
    parent = serializers.SerializerMethodField()
    parent_name_chain = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = (
            "id", "name", "nameAR", "image_1",
            "image_2", "image_3", "status",
            "type", "prods_linked", "home_page_thumbnail",
            "home_page_thumbnail_ar", "parent", "parent_name_chain"
        )

    def get_parent_name_chain(self, obj):
        if obj.parent:
            return '>'.join(
                [obj.name, obj.parent.get_parent_name_chain(), ]
            )
        else:
            return '>'.join(
                [obj.name]
            )

    def get_status(self, obj):
        return obj.get_status_display()

    def get_image_1(self, obj):
        if obj.medias.filter(type='im1').exists():
            im1_media = obj.medias.filter(
                type='im1'
            ).latest('id')
            if im1_media.media:
                return im1_media.media.url
            return None
        return None

    def get_image_2(self, obj):
        if obj.medias.filter(type='im2').exists():
            im2_media = obj.medias.filter(
                type='im2'
            ).latest('id')
            if im2_media.media:
                return im2_media.media.url
            return None
        return None

    def get_image_3(self, obj):
        if obj.medias.filter(type='im3').exists():
            im3_media = obj.medias.filter(
                type='im3'
            ).latest('id')
            if im3_media.media:
                return im3_media.media.url
            return None
        return None

    def get_prods_linked(self, obj):
        descendants = Category.objects.descendants(obj)
        sum = 0
        for category in descendants:
            prod_count = category.products.all().annotate(
                variant_count=Count('productVariantValue', distinct=True)).exclude(
                Q(variant_count=0, parent__isnull=False)
                | Q(parent=None, children__isnull=False)).count()
            sum += prod_count
        return sum

    def get_type(self, obj):
        if not obj.parent:
            return "Main Category"
        ancestors_count = Category.objects.ancestors(obj).exclude(
            id=obj.id).count()

        if ancestors_count == 1:
            return "Sub Category"
        elif ancestors_count == 2:
            return "Product Type"
        elif ancestors_count == 3:
            return "Sub Product Type"

    def get_parent(self, obj):
        if obj.parent:
            return CategoryListSerializer(obj.parent).data
        return None


class AddSubCategorySerializer(serializers.Serializer):
    name = serializers.CharField(required=True)
    nameAR = serializers.CharField(required=True)

    class Meta:
        model = Category
        fields = (
            "name", "nameAR"
        )

    def create(self, validated_data):
        return Category.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.name = validated_data.get("name", instance.name)
        instance.nameAR = validated_data.get("nameAR", instance.nameAR)
        instance.save()
        return instance


class CategorySuggestionSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    parent = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = (
            "id", "name", "parent",
        )

    def get_name(self, obj):
        lang_code = self.context.get("lang_code")
        if lang_code == "ar":
            return obj.nameAR
        return obj.name

    def get_parent(self, obj):
        if obj.parent:
            return CategorySuggestionSerializer(obj.parent).data
        return None


class ProductListSerializer(serializers.ModelSerializer):
    seller_name = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    inventory_count = serializers.SerializerMethodField()
    variant_count = serializers.SerializerMethodField()
    category = CategorySuggestionSerializer()
    brand = BrandSerializer()

    class Meta:
        model = EcommProduct
        fields = (
            "id", "name", "image",
            "seller_name", "status", "brand",
            "inventory_count", "variant_count", "base_price",
            "category", "created_at", "updated_at",
            "is_media_uploaded"
        )

    def get_name(self, obj):
        lang_code = self.context.get("lang_code")

        if lang_code == "ar":
            var_vals_list = VariantValues.objects.filter(
                pk__in=obj.variant_value_ids()
            ).values_list('valueAR', flat=True)
            var_string = ",".join(list(var_vals_list))
            if obj.nameAR and obj.nameAR != "":
                return "".join([obj.nameAR, "-", var_string])
            return var_string

        var_vals_list = VariantValues.objects.filter(
            pk__in=obj.variant_value_ids()
        ).values_list('value', flat=True)
        var_string = ",".join(list(var_vals_list))
        if obj.name and obj.name != "":
            return "".join([obj.name, "-", var_string])
        return var_string

    def get_seller_name(self, obj):
        lang_code = self.context.get("lang_code")
        if obj.store:
            if lang_code == "ar":
                return obj.store.nameAR
            return obj.store.name
        return None

    def get_status(self, obj):
        return obj.get_status_display()

    def get_image(self, obj):
        if obj.medias.exists():
            return obj.medias.first().file_data.url
        elif obj.children.exists():
            child_prod = obj.children.all().first()
            if child_prod.medias.exists():
                return child_prod.medias.first().file_data.url
            return None
        return None

    def get_inventory_count(self, obj):
        if obj.children.exists():
            child_qty = InventoryProduct.objects.filter(
                product__pk__in=obj.children.values_list('id')
            ).aggregate(quantity_count=Sum(F('quantity'))).get(
                'quantity_count')
            if child_qty:
                return child_qty
            return 0
        return obj.get_avail_qty()

    def get_variant_count(self, obj):
        return obj.children.all().annotate(
            variant_count=Count('productVariantValue', distinct=True)).exclude(
            Q(variant_count=0, parent=None)).count()


class SpecificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductSpecification
        fields = ('specification', 'specificationAR',
                  'value', 'valueAR')

    def create(self, validated_data):
        prod_spec = ProductSpecification.objects.create(**validated_data)
        return prod_spec


class SpecificationEditSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=True)

    class Meta:
        model = ProductSpecification
        fields = ('id', 'specification', 'specificationAR',
                  'value', 'valueAR')


class SpecificationEditDraftSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    specification = serializers.CharField(
        required=False, allow_null=True, allow_blank=True)
    specificationAR = serializers.CharField(
        required=False, allow_null=True, allow_blank=True)
    value = serializers.CharField(
        required=False, allow_null=True, allow_blank=True)
    valueAR = serializers.CharField(
        required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = ProductSpecification
        fields = ('id', 'specification', 'specificationAR',
                  'value', 'valueAR')


class SpecificationDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductSpecification
        fields = ('id', 'specification', 'specificationAR',
                  'value', 'valueAR')


class VariantValueSerializer(serializers.ModelSerializer):
    class Meta:
        model = VariantValues
        fields = ('value', 'valueAR')


class VariantValueEditSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=True)

    class Meta:
        model = VariantValues
        fields = ('id', 'value', 'valueAR')


class VariantSerializer(serializers.ModelSerializer):
    variant_values = VariantValueSerializer(many=True)

    class Meta:
        model = Variant
        fields = ('name', 'nameAR', 'variant_values')


class VariantEditSerializer(serializers.ModelSerializer):
    variant_values = VariantValueEditSerializer(many=True)
    id = serializers.IntegerField(required=True)

    class Meta:
        model = Variant
        fields = ('id', 'name', 'nameAR', 'variant_values')


class VariantDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Variant
        fields = ('id', 'name', 'nameAR',)


class VariantValueDetailSerializer(serializers.ModelSerializer):
    variant = VariantDetailSerializer()

    class Meta:
        model = VariantValues
        fields = ('id', 'value', 'valueAR', 'variant')


class EcommProductMediaSerializer(serializers.ModelSerializer):

    class Meta:
        model = EcommProductMedia
        fields = ('file_data', )


class ProductMediaDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = EcommProductMedia
        fields = ('id', 'file_data', 'order')


class ChildProductSerializer(serializers.ModelSerializer):
    overview = serializers.CharField(
        source='description', required=False,
        allow_blank=True,
        allow_null=True
    )
    overviewAR = serializers.CharField(
        source='descriptionAR', required=False,
        allow_blank=True,
        allow_null=True
    )
    specifications = SpecificationSerializer(many=True, required=False)
    variants = VariantSerializer(many=True)
    media = serializers.JSONField(required=True)
    quantity = serializers.IntegerField(required=True)
    barCode = serializers.CharField(
        required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = EcommProduct
        fields = ('overview', 'overviewAR', 'specifications',
                  'variants', 'base_price', 'discounted_price',
                  'sku', 'media', 'quantity', 'barCode')


class ChildProductDraftSerializer(serializers.ModelSerializer):
    overview = serializers.CharField(
        source='description', required=False,
        allow_blank=True,
        allow_null=True
    )
    overviewAR = serializers.CharField(
        source='descriptionAR', required=False,
        allow_blank=True,
        allow_null=True
    )
    specifications = SpecificationSerializer(many=True, required=False)
    variants = VariantSerializer(many=True)
    media = serializers.JSONField(required=True)
    quantity = serializers.IntegerField(required=True)
    barCode = serializers.CharField(
        required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = EcommProduct
        fields = ('overview', 'overviewAR', 'specifications',
                  'variants', 'base_price', 'discounted_price',
                  'sku', 'media', 'quantity', 'barCode')


class ChildProductEditSerializer(serializers.ModelSerializer):
    overview = serializers.CharField(
        required=False, allow_blank=True, allow_null=True)
    overviewAR = serializers.CharField(
        required=False, allow_blank=True, allow_null=True)
    specifications = SpecificationEditSerializer(many=True, required=False)
    variants = VariantEditSerializer(many=True)
    media = serializers.JSONField(required=False)
    quantity = serializers.IntegerField(required=True)
    id = serializers.IntegerField(required=True)
    barCode = serializers.CharField(
        required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = EcommProduct
        fields = ('id', 'overview', 'overviewAR', 'specifications',
                  'variants', 'base_price', 'discounted_price',
                  'sku', 'media', 'quantity', 'barCode')

    def validate_barCode(self, value):
        if self.instance and self.instance.barCode:
            if self.instance.barCode == value:
                return value
            prods = EcommProduct.objects.filter(
                barCode=value
            )
            if prods.exists():
                raise ValidationError("BarCode must be unique")
            return value
        return value


class ChildProductEditDraftSerializer(serializers.ModelSerializer):
    overview = serializers.CharField(
        required=False, allow_blank=True,
        allow_null=True)
    overviewAR = serializers.CharField(
        required=False, allow_blank=True,
        allow_null=True)
    specifications = SpecificationEditDraftSerializer(many=True, required=False)
    variants = VariantEditSerializer(many=True)
    media = serializers.JSONField(required=False)
    quantity = serializers.IntegerField(required=False)
    id = serializers.IntegerField(required=False)
    barCode = serializers.CharField(
        required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = EcommProduct
        fields = ('id', 'overview', 'overviewAR', 'specifications',
                  'variants', 'base_price', 'discounted_price',
                  'sku', 'media', 'quantity', 'barCode')

    def validate_barCode(self, value):
        if self.instance and self.instance.barCode:
            if self.instance.barCode == value:
                return value
            prods = EcommProduct.objects.filter(
                barCode=value
            )
            if prods.exists():
                raise ValidationError("BarCode must be unique")
            return value
        return value


class SearchKeywordDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchKeyWord
        fields = ('id', 'keyword', )


class SearchKeywordARDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchKeyWordAR
        fields = ('id', 'keyword_ar', )


class ProductSearchKeywordSerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchKeyWord
        fields = ('keyword', )
        extra_kwargs = {
            'keyword': {'validators': []},
        }

    def create(self, validated_data):
        search_key = SearchKeyWord.objects.get_or_create(
            searched_for='product', **validated_data)
        return search_key


class ProductSearchKeywordEditSerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchKeyWord
        fields = ('keyword', 'id')
        extra_kwargs = {
            'keyword': {'validators': []},
        }


class ProductSearchKeywordARSerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchKeyWordAR
        fields = ('keyword_ar', )
        extra_kwargs = {
            'keyword_ar': {'validators': []},
        }

    def create(self, validated_data):
        search_key_ar = SearchKeyWordAR.objects.get_or_create(
            searched_for='product', **validated_data)
        return search_key_ar


class ProductSearchKeywordAREditSerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchKeyWordAR
        fields = ('keyword_ar', 'id' )
        extra_kwargs = {
            'keyword_ar': {'validators': []},
        }

    def create(self, validated_data):
        search_key_ar = SearchKeyWordAR.objects.get_or_create(
            searched_for='product', **validated_data)
        return search_key_ar


class AddEditProductSerializer(serializers.ModelSerializer):
    name = serializers.CharField(required=False)
    nameAR = serializers.CharField(required=False)
    overview = serializers.CharField(
        source='description', required=False,
        allow_blank=True,
        allow_null=True
    )
    overviewAR = serializers.CharField(
        source='descriptionAR', required=False,
        allow_blank=True,
        allow_null=True
    )
    seller = serializers.IntegerField(source='store', required=True)
    category = serializers.IntegerField(required=True)
    quantity = serializers.IntegerField(required=True)
    specifications = SpecificationSerializer(many=True, required=False)
    child_variants = ChildProductSerializer(many=True, required=False)
    media = serializers.JSONField(required=True)
    available_from = serializers.DateTimeField(
        required=False, format="%Y-%m-%d %H:%M:%S")
    search_keys = ProductSearchKeywordSerializer(
        source='additional_search_keywords', many=True, required=False)
    search_keys_ar = ProductSearchKeywordARSerializer(
        source='additional_search_keywords_ar', many=True, required=False)
    collections = NestedCollectionSerializer(required=False, many=True)
    barCode = serializers.CharField(required=False)

    class Meta:
        model = EcommProduct
        fields = ('name', 'nameAR', 'overview', 'overviewAR',
                  'quantity', 'specifications', 'size_guide', 'size_guide_ar',
                  'child_variants', 'category', 'seller', 'status',
                  'is_out_of_stock', 'is_new_arrival', 'media',
                  'brand', 'base_price', 'discounted_price', 'sku',
                  'available_from', 'search_keys', 'search_keys_ar',
                  'collections', 'barCode')

    def validate_seller(self, value):
        try:
            store = Store.objects.get(
                id=value
            )
        except Store.DoesNotExist:
            raise ValidationError("Seller does not exist ")
        return store

    def validate_barCode(self, value):
        prods = EcommProduct.objects.filter(
            barCode=value
        )
        if prods.exists():
            raise ValidationError("BarCode must be unique")
        return value

    def validate_category(self, value):
        try:
            cat = Category.objects.get(
                id=value
            )
        except Category.DoesNotExist:
            raise ValidationError("Category does not exist ")
        return cat

    def validate(self, attrs):
        seller = attrs.get("store")
        category = attrs.get("category")

        if category and seller:
            if category.parent:
                category_ancestor = Category.objects.ancestors(category).exclude(
                    Q(id=category.id) | Q(parent__isnull=False)).first()
                if category_ancestor not in seller.selling_categories.all():
                    raise ValidationError("Selected main category is not applicable")
            else:
                if category not in seller.selling_categories.all():
                    raise ValidationError("Selected main category is not applicable")
        return attrs

    def add_search_keys(self, search_keys, product):
        for search_key in search_keys:
            keyword = search_key.get('keyword')
            search_key = SearchKeyWord.objects.get_or_create(
                keyword=keyword, searched_for='product')[0]
            product.additional_search_keywords.add(search_key)

    def add_search_keys_ar(self, search_keys_ar, product):
        for search_key_ar in search_keys_ar:
            keyword_ar = search_key_ar.get('keyword_ar')
            search_key_ar = SearchKeyWordAR.objects.get_or_create(
                keyword_ar=keyword_ar, searched_for='product')[0]
            product.additional_search_keywords_ar.add(search_key_ar)

    def add_resized_thumbnail_image(self, product):
        if not product.medias.filter(is_thumbnail=True).exists():
            media_url = product.get_media_url()
            if media_url != "":
                file_name = ""
                basewidth = 200

                if "png" in media_url:
                    file_name = media_url.split("/")[-1].split(".png")[0]
                elif "jpeg" in media_url:
                    file_name = media_url.split("/")[-1].split(".jpeg")[0]
                elif "jpg" in media_url:
                    file_name = media_url.split("/")[-1].split(".jpg")[0]

                if file_name != "":
                    outfile = "%s_resized" % file_name
                    new_key_value = "media/ecomm_products/medias/%s.jpeg" % outfile
                    original_key = "/".join(media_url.split("/")[3:])

                    if product.medias.exists():
                        latest_order = product.medias.latest('id').order
                        order = latest_order + 1
                    else:
                        order = 1
                    EcommProductMedia.objects.update_or_create(
                        product=product,
                        is_thumbnail=True,
                        defaults={
                            "file_data": "/".join(new_key_value.split("/")[1:]),
                            "order": order
                        },
                    )

                    s3_client = boto3.client(
                        "s3",
                        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                        region_name=settings.AWS_S3_REGION
                    )
                    bucket = settings.AWS_STORAGE_BUCKET_NAME
                    print("original_key")
                    print(original_key)
                    print("product_id")
                    print(product.id)
                    try:
                        response = s3_client.get_object(Bucket=bucket, Key=original_key)
                    except Exception as e:
                        response = None
                    if response:
                        body = response['Body']
                        image = Image.open(body)
                        rgb_im = image.convert('RGB')
                        wpercent = (basewidth / float(rgb_im.size[0]))
                        hsize = int((float(rgb_im.size[1]) * float(wpercent)))
                        img = rgb_im.resize((basewidth, hsize), Image.ANTIALIAS)

                        with BytesIO() as output:
                            img.save(output, format="jpeg", quality=75)
                            output.seek(0)

                            s3_client.put_object(
                                ACL="public-read",
                                Bucket=bucket, Key=new_key_value,
                                Body=output, ContentType="images/jpeg"
                            )

    def add_media(self, media, url_list, product):
        for media in media:
            file_name = media.get("file_name")
            file_type = media.get("file_type")
            order = media.get("order")

            key, path = get_ecomm_prod_media_key_and_path(file_name, file_type)
            url_list.append(get_presigned_url(key, file_type))
            EcommProductMedia.objects.create(
                product=product, file_data=path,
                order=order,
                is_thumbnail=False
            )
        if settings.SITE_CODE == 2 or settings.SITE_CODE == 3:
            self.add_resized_thumbnail_image(product)
        return url_list

    def update_quantity(self, product, quantity):
        if product.parent:
            store = product.parent.store
        else:
            store = product.store
        if store:
            if store.inventories.exists():
                inventory = store.inventories.first()
                InventoryProduct.objects.update_or_create(
                    product=product,
                    inventory=inventory,
                    defaults={'quantity': quantity}
                )
            else:
                inv = Inventory.objects.create(
                    name=store.name,
                    nameAR=store.nameAR,
                    store=store
                )
                InventoryProduct.objects.create(
                    product=product, quantity=quantity,
                    inventory=inv
                )

    def remove_prod_quantity(self, product):
        product.inventoryProducts.filter(
            inventory__store=product.store
        ).delete()

    def update_discounted_price(self, product):
        if int(product.discounted_price) == 0:
            try:
                product.discount
                Discount.objects.filter(
                    product=product
                ).delete()
            except ObjectDoesNotExist:
                pass
        elif int(product.discounted_price) > 0 and int(product.base_price) > 0:
            reduction = product.base_price - product.discounted_price
            percentage = (reduction * 100) / product.base_price
            Discount.objects.update_or_create(
                product=product,
                defaults={'percentage': percentage}
            )

    def add_child_variants_and_get_url_list(self, product, child_variants, url_list):
        for index, child_variant in enumerate(child_variants):
            overview = child_variant.get('description')
            overviewAR = child_variant.get('descriptionAR')
            sku = child_variant.get('sku')
            barCode = child_variant.get('barCode', None)
            quantity = child_variant.get('quantity')
            variants = child_variant.get('variants')
            media = child_variant.get('media')
            base_price = child_variant.get('base_price')
            discounted_price = child_variant.get('discounted_price', None)
            specifications = child_variant.pop('specifications', None)

            variant_value_ids = []

            for variant in variants:
                name = variant.get('name')
                nameAR = variant.get('nameAR')
                variant_cr = Variant.objects.get_or_create(
                    category=product.category, name=name,
                    nameAR=nameAR)[0]
                variant_values = variant.get('variant_values')
                for variant_value in variant_values:
                    value = variant_value.get('value')
                    valueAR = variant_value.get('valueAR')
                    variant_value = VariantValues.objects.get_or_create(
                        variant=variant_cr,
                        value=value,
                        valueAR=valueAR)[0]
                    variant_value_ids.append(variant_value.id)

            child_pr = EcommProduct.objects.create(
                parent=product, name=product.name,
                nameAR=product.nameAR,
                description=overview,
                descriptionAR=overviewAR,
                category=product.category,
                brand=product.brand,
                store=product.store, sku=sku,
                barCode=barCode,
                base_price=base_price,
                discounted_price=discounted_price,
                available_from=product.available_from,
                status=product.status)

            self.update_discounted_price(child_pr)

            self.add_media(media, url_list, child_pr)

            if specifications:
                for specification in specifications:
                    ProductSpecification.objects.create(
                        product=child_pr, **specification)

            if quantity and quantity > 0:
                self.update_quantity(child_pr, quantity)
            elif child_pr.is_out_of_stock:
                self.remove_prod_quantity(child_pr)

            for variant_value in variant_value_ids:
                ProductVariantValue.objects.get_or_create(
                    product=child_pr,
                    variant_value_id=variant_value
                )
        return url_list

    def create(self, validated_data):
        child_variants = validated_data.pop('child_variants', None)
        specifications = validated_data.pop('specifications', None)
        category = validated_data.get('category')
        quantity = validated_data.pop('quantity')
        media = validated_data.pop('media', None)
        search_keys = validated_data.pop('additional_search_keywords', None)
        search_keys_ar = validated_data.pop('additional_search_keywords_ar', None)
        collections = validated_data.pop('collections', None)

        url_list = []

        product = EcommProduct.objects.create(**validated_data)

        try:
            self.add_media(media, url_list, product)

            self.update_discounted_price(product)

            if quantity and quantity > 0:
                self.update_quantity(product, quantity)
            elif product.is_out_of_stock:
                self.remove_prod_quantity(product)

            if specifications:
                for specification in specifications:
                    ProductSpecification.objects.create(
                        product=product, **specification)

            if search_keys:
                self.add_search_keys(search_keys, product)

            if search_keys_ar:
                self.add_search_keys_ar(search_keys_ar, product)

            if child_variants:
                url_list = self.add_child_variants_and_get_url_list(
                    product, child_variants, url_list)

            if collections:
                for collections_data in collections:
                    collection_id = collections_data.pop('id', None)
                    collection = get_object_or_404(ProductCollection, pk=collection_id)
                    collection.products.add(product)
                    child_var_prods = product.children.all()
                    collection.products.add(*child_var_prods)

            return url_list, product, "Success"
        except Exception as e:
            product.delete()

            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            report_to_developer("Issue in add product", str(e)
                                + "at %s, line number %s" % (fname, exc_tb.tb_lineno))
            return None, None, str(e)


class AddProductDraftSerializer(serializers.ModelSerializer):
    overview = serializers.CharField(
        source='description', required=False,
        allow_blank=True,
        allow_null=True)
    overviewAR = serializers.CharField(
        source='descriptionAR', required=False,
        allow_blank=True,
        allow_null=True
    )
    seller = serializers.IntegerField(source='store', required=False)
    quantity = serializers.IntegerField(required=False)
    specifications = SpecificationSerializer(many=True, required=False)
    child_variants = ChildProductDraftSerializer(many=True, required=False)
    media = serializers.JSONField(required=False)
    available_from = serializers.DateTimeField(
        required=False, format="%Y-%m-%d %H:%M:%S")
    search_keys = ProductSearchKeywordSerializer(
        source='additional_search_keywords', many=True, required=False)
    search_keys_ar = ProductSearchKeywordARSerializer(
        source='additional_search_keywords_ar', many=True, required=False)
    collections = NestedCollectionSerializer(required=False, many=True)
    barCode = serializers.CharField(required=False)

    class Meta:
        model = EcommProduct
        fields = ('name', 'nameAR', 'overview', 'overviewAR',
                  'quantity', 'specifications', 'size_guide', 'size_guide_ar',
                  'child_variants', 'category', 'seller', 'status',
                  'is_out_of_stock', 'is_new_arrival', 'media',
                  'brand', 'base_price', 'discounted_price', 'sku',
                  'available_from', 'search_keys', 'search_keys_ar',
                  'collections', 'barCode')

    def validate_seller(self, value):
        try:
            store = Store.objects.get(
                id=value
            )
        except Store.DoesNotExist:
            raise ValidationError("Seller does not exist ")
        return store

    def validate_barCode(self, value):
        prods = EcommProduct.objects.filter(
            barCode=value
        )
        if prods.exists():
            raise ValidationError("BarCode must be unique")
        return value

    def validate(self, attrs):
        seller = attrs.get("store")
        category = attrs.get("category")

        if category and seller:
            if category.parent:
                category_ancestor = Category.objects.ancestors(category).exclude(
                    Q(id=category.id) | Q(parent__isnull=False)).first()
                if category_ancestor not in seller.selling_categories.all():
                    raise ValidationError("Selected main category is not applicable")
            else:
                if category not in seller.selling_categories.all():
                    raise ValidationError("Selected main category is not applicable")
        return attrs

    def add_search_keys(self, search_keys, product):
        for search_key in search_keys:
            keyword = search_key.get('keyword')
            search_key = SearchKeyWord.objects.get_or_create(
                keyword=keyword, searched_for='product')[0]
            product.additional_search_keywords.add(search_key)

    def add_search_keys_ar(self, search_keys_ar, product):
        for search_key_ar in search_keys_ar:
            keyword_ar = search_key_ar.get('keyword_ar')
            search_key_ar = SearchKeyWordAR.objects.get_or_create(
                keyword_ar=keyword_ar, searched_for='product')[0]
            product.additional_search_keywords_ar.add(search_key_ar)

    def add_resized_thumbnail_image(self, product):
        if not product.medias.filter(is_thumbnail=True).exists():
            media_url = product.get_media_url()
            if media_url != "":
                file_name = ""
                basewidth = 200

                if "png" in media_url:
                    file_name = media_url.split("/")[-1].split(".png")[0]
                elif "jpeg" in media_url:
                    file_name = media_url.split("/")[-1].split(".jpeg")[0]
                elif "jpg" in media_url:
                    file_name = media_url.split("/")[-1].split(".jpg")[0]

                if file_name != "":
                    outfile = "%s_resized" % file_name
                    new_key_value = "media/ecomm_products/medias/%s.jpeg" % outfile
                    original_key = "/".join(media_url.split("/")[3:])

                    if product.medias.exists():
                        latest_order = product.medias.latest('id').order
                        order = latest_order + 1
                    else:
                        order = 1
                    EcommProductMedia.objects.update_or_create(
                        product=product,
                        is_thumbnail=True,
                        defaults={
                            "file_data": "/".join(new_key_value.split("/")[1:]),
                            "order": order
                        },
                    )

                    s3_client = boto3.client(
                        "s3",
                        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                        region_name=settings.AWS_S3_REGION
                    )
                    bucket = settings.AWS_STORAGE_BUCKET_NAME
                    print("original_key")
                    print(original_key)
                    print("product_id")
                    print(product.id)
                    try:
                        response = s3_client.get_object(Bucket=bucket, Key=original_key)
                    except Exception as e:
                        response = None
                    if response:
                        body = response['Body']
                        image = Image.open(body)
                        rgb_im = image.convert('RGB')
                        wpercent = (basewidth / float(rgb_im.size[0]))
                        hsize = int((float(rgb_im.size[1]) * float(wpercent)))
                        img = rgb_im.resize((basewidth, hsize), Image.ANTIALIAS)

                        with BytesIO() as output:
                            img.save(output, format="jpeg", quality=75)
                            output.seek(0)

                            s3_client.put_object(
                                ACL="public-read",
                                Bucket=bucket, Key=new_key_value,
                                Body=output, ContentType="images/jpeg"
                            )

    def add_media(self, media, url_list, product):
        for media in media:
            file_name = media.get("file_name")
            file_type = media.get("file_type")
            order = media.get("order")

            key, path = get_ecomm_prod_media_key_and_path(file_name, file_type)
            url_list.append(get_presigned_url(key, file_type))
            EcommProductMedia.objects.create(
                product=product, file_data=path,
                order=order,
                is_thumbnail=False
            )
        if settings.SITE_CODE == 2 or settings.SITE_CODE == 3:
            self.add_resized_thumbnail_image(product)
        return url_list

    def update_quantity(self, product, quantity):
        if product.store:
            if product.store.inventories.exists():
                inventory = product.store.inventories.first()
                InventoryProduct.objects.update_or_create(
                    product=product,
                    inventory=inventory,
                    defaults={'quantity': quantity}
                )
            else:
                inv = Inventory.objects.create(
                    name=product.store.name,
                    nameAR=product.store.nameAR,
                    store=product.store
                )
                InventoryProduct.objects.create(
                    product=product, quantity=quantity,
                    inventory=inv
                )

    def remove_prod_quantity(self, product):
        product.inventoryProducts.filter(
            inventory__store=product.store
        ).delete()

    def update_discounted_price(self, product):
        if int(product.discounted_price) == 0:
            try:
                product.discount
                Discount.objects.filter(
                    product=product
                ).delete()
            except ObjectDoesNotExist:
                pass
        elif int(product.discounted_price) > 0 and int(product.base_price) > 0:
            reduction = product.base_price - product.discounted_price
            percentage = (reduction * 100) / product.base_price
            Discount.objects.update_or_create(
                product=product,
                defaults={'percentage': percentage}
            )

    def add_child_variants_and_get_url_list(self, product, child_variants, url_list):
        for index, child_variant in enumerate(child_variants):
            overview = child_variant.get('description')
            overviewAR = child_variant.get('descriptionAR')
            sku = child_variant.get('sku')
            barCode = child_variant.get('barCode', None)
            quantity = child_variant.get('quantity')
            variants = child_variant.get('variants')
            media = child_variant.get('media')
            base_price = child_variant.get('base_price')
            discounted_price = child_variant.get('discounted_price', None)
            specifications = child_variant.pop('specifications', None)

            variant_value_ids = []

            for variant in variants:
                name = variant.get('name')
                nameAR = variant.get('nameAR')
                variant_cr = Variant.objects.get_or_create(
                    category=product.category, name=name,
                    nameAR=nameAR)[0]
                variant_values = variant.get('variant_values')
                for variant_value in variant_values:
                    value = variant_value.get('value')
                    valueAR = variant_value.get('valueAR')
                    variant_value = VariantValues.objects.get_or_create(
                        variant=variant_cr,
                        value=value,
                        valueAR=valueAR)[0]
                    variant_value_ids.append(variant_value.id)

            child_pr = EcommProduct.objects.create(
                parent=product, name=product.name,
                nameAR=product.nameAR,
                description=overview,
                descriptionAR=overviewAR,
                category=product.category,
                brand=product.brand,
                store=product.store, sku=sku,
                barCode=barCode,
                base_price=base_price,
                discounted_price=discounted_price,
                available_from=product.available_from,
                status=product.status)

            self.update_discounted_price(child_pr)

            self.add_media(media, url_list, child_pr)

            if specifications:
                for specification in specifications:
                    ProductSpecification.objects.create(
                        product=child_pr, **specification)

            if quantity and quantity > 0:
                self.update_quantity(child_pr, quantity)
            elif child_pr.is_out_of_stock:
                self.remove_prod_quantity(child_pr)

            for variant_value in variant_value_ids:
                ProductVariantValue.objects.get_or_create(
                    product=child_pr,
                    variant_value_id=variant_value
                )
        return url_list

    def create(self, validated_data):
        child_variants = validated_data.pop('child_variants', None)
        specifications = validated_data.pop('specifications', None)
        category = validated_data.get('category', None)
        quantity = validated_data.pop('quantity', None)
        media = validated_data.pop('media', None)
        search_keys = validated_data.pop('additional_search_keywords', None)
        search_keys_ar = validated_data.pop('additional_search_keywords_ar', None)
        collections = validated_data.pop('collections', None)

        url_list = []

        product = EcommProduct.objects.create(**validated_data)

        try:
            if media:
                self.add_media(media, url_list, product)

            self.update_discounted_price(product)

            if quantity and quantity > 0:
                self.update_quantity(product, quantity)
            elif product.is_out_of_stock:
                self.remove_prod_quantity(product)

            if specifications:
                for specification in specifications:
                    ProductSpecification.objects.create(
                        product=product, **specification)

            if search_keys:
                self.add_search_keys(search_keys, product)

            if search_keys_ar:
                self.add_search_keys_ar(search_keys_ar, product)

            if child_variants:
                url_list = self.add_child_variants_and_get_url_list(
                    product, child_variants, url_list)

            if collections:
                for collections_data in collections:
                    collection_id = collections_data.pop('id', None)
                    collection = get_object_or_404(ProductCollection, pk=collection_id)
                    collection.products.add(product)
                    child_var_prods = product.children.all()
                    collection.products.add(*child_var_prods)

            return url_list, product, "Success"
        except Exception as e:
            product.delete()
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            report_to_developer("Issue in add product", str(e)
                                + "at %s, line number %s" % (fname, exc_tb.tb_lineno))
            return None, None, str(e)


class EditProductDraftSerializer(serializers.ModelSerializer):
    overview = serializers.CharField(
        required=False, allow_blank=True,
        allow_null=True)
    overviewAR = serializers.CharField(
        required=False, allow_blank=True,
        allow_null=True)
    media = serializers.JSONField(required=False)
    seller = serializers.IntegerField(required=False)
    specifications = SpecificationEditDraftSerializer(many=True, required=False)
    child_variants = ChildProductEditDraftSerializer(many=True, required=False)
    available_from = serializers.DateTimeField(
        required=False, format="%Y-%m-%d %H:%M:%S")
    search_keys = ProductSearchKeywordEditSerializer(many=True, required=False)
    search_keys_ar = ProductSearchKeywordAREditSerializer(many=True, required=False)
    quantity = serializers.IntegerField(required=False)
    collections = NestedCollectionSerializer(required=False, many=True)

    class Meta:
        model = EcommProduct
        fields = ('name', 'nameAR', 'overview', 'overviewAR',
                  'specifications', 'size_guide', 'size_guide_ar',
                  'child_variants', 'category', 'seller', 'brand',
                  'status', 'is_out_of_stock', 'is_new_arrival', 'media',
                  'base_price', 'discounted_price', 'sku',
                  'available_from', 'search_keys', 'search_keys_ar',
                  'decline_reason', 'quantity', 'collections', 'barCode')

    def validate_seller(self, value):
        try:
            store = Store.objects.get(
                id=value
            )
        except Store.DoesNotExist:
            raise ValidationError("Seller does not exist ")
        return store

    def validate_barCode(self, value):
        if self.instance and self.instance.barCode:
            if self.instance.barCode == value:
                return value
            prods = EcommProduct.objects.filter(
                barCode=value
            )
            if prods.exists():
                raise ValidationError("BarCode must be unique")
            return value
        return value

    def validate(self, attrs):
        seller = attrs.get("seller")
        category = attrs.get("category")
        print("edit-prod")
        print(seller)
        print(category)

        if category and seller:
            if category.parent:
                category_ancestor = Category.objects.ancestors(category).exclude(
                    Q(id=category.id) | Q(parent__isnull=False)).first()
                print("ancestor")
                print(category_ancestor)
                if category_ancestor not in seller.selling_categories.all():
                    raise ValidationError("Selected main category is not applicable")
            else:
                if category not in seller.selling_categories.all():
                    raise ValidationError("Selected main category is not applicable")
        return attrs

    def remove_prod_quantity(self, product):
        product.inventoryProducts.filter(
            inventory__store=product.store
        ).delete()

    def update_discounted_price(self, product):
        if int(product.discounted_price) == 0:
            try:
                product.discount
                Discount.objects.filter(
                    product=product
                ).delete()
            except ObjectDoesNotExist:
                pass
        elif int(product.discounted_price) > 0 and int(product.base_price) > 0:
            reduction = product.base_price - product.discounted_price
            percentage = (reduction * 100) / product.base_price
            Discount.objects.update_or_create(
                product=product,
                defaults={'percentage': percentage}
            )

    def update_existing_child(self, category, child_variant):
        overview = child_variant.get('overview')
        overviewAR = child_variant.get('overviewAR')
        base_price = child_variant.get('base_price')
        discounted_price = child_variant.get('discounted_price')
        barCode = child_variant.get('barCode')
        sku = child_variant.get('sku')
        id = child_variant.get('id')
        variants = child_variant.get('variants', None)

        child_pr = get_object_or_404(
            EcommProduct, pk=id)
        child_pr.description = overview
        child_pr.descriptionAR = overviewAR
        child_pr.sku = sku
        child_pr.base_price = base_price
        child_pr.discounted_price = discounted_price
        child_pr.barCode = barCode

        child_pr.category = category
        child_pr.brand = child_pr.parent.brand
        child_pr.status = child_pr.parent.status
        child_pr.available_from = child_pr.parent.available_from
        child_pr.store = child_pr.parent.store
        child_pr.save()

        self.update_discounted_price(child_pr)

        if variants:
            for variant in variants:
                id = variant.get('id')
                name = variant.get('name')
                nameAR = variant.get('nameAR')
                variant_values = variant.get('variant_values')

                if id != 0:
                    variant = get_object_or_404(
                        Variant, pk=id)
                    variant.name = name
                    variant.nameAR = nameAR
                    variant.save()
                else:
                    variant = Variant.objects.get_or_create(
                        category=category, name=name,
                        nameAR=nameAR)[0]

                for variant_value in variant_values:
                    id = variant_value.get('id')
                    value = variant_value.get('value')
                    valueAR = variant_value.get('valueAR')

                    if id != 0:
                        variant_value = get_object_or_404(
                            VariantValues, pk=id)
                        variant_value.value = value
                        variant_value.valueAR = nameAR
                        variant.save()
                    else:
                        variant_value = VariantValues.objects.get_or_create(
                            variant=variant,
                            value=value,
                            valueAR=valueAR)[0]

                        ProductVariantValue.objects.get_or_create(
                            product=child_pr,
                            variant_value=variant_value
                        )

        return child_pr

    def add_new_child(self, instance, category, child_variant):
        overview = child_variant.get('overview')
        overviewAR = child_variant.get('overviewAR')
        base_price = child_variant.get('base_price')
        discounted_price = child_variant.get('discounted_price')
        sku = child_variant.get('sku')
        barCode = child_variant.get('barCode')
        variants = child_variant.get('variants')

        child_pr = EcommProduct.objects.create(
            parent=instance, name=instance.name,
            nameAR=instance.nameAR,
            description=overview,
            descriptionAR=overviewAR,
            category=category,
            brand=instance.brand,
            store=instance.store, sku=sku,
            base_price=base_price,
            discounted_price=discounted_price,
            status=instance.status,
            available_from=instance.available_from,
            barCode=barCode)

        self.update_discounted_price(child_pr)

        for variant in variants:
            id = variant.get('id')
            name = variant.get('name')
            nameAR = variant.get('nameAR')
            variant_values = variant.get('variant_values')

            if id != 0:
                variant = get_object_or_404(
                    Variant, pk=id)
                variant.name = name
                variant.nameAR = nameAR
                variant.save()
            else:
                variant = Variant.objects.get_or_create(
                    category=category, name=name,
                    nameAR=nameAR)[0]

            for variant_value in variant_values:
                id = variant_value.get('id')
                value = variant_value.get('value')
                valueAR = variant_value.get('valueAR')

                if id != 0:
                    variant_value = get_object_or_404(
                        VariantValues, pk=id)
                    variant_value.value = value
                    variant_value.valueAR = nameAR
                    variant.save()
                else:
                    variant_value = VariantValues.objects.get_or_create(
                        variant=variant,
                        value=value,
                        valueAR=valueAR)[0]

                    ProductVariantValue.objects.get_or_create(
                        product=child_pr,
                        variant_value=variant_value
                    )

        return child_pr

    def add_child_variants_and_get_url_list(
            self, category, instance, child_variants, url_list):

        for child_variant in child_variants:
            id = child_variant.get('id')
            quantity = child_variant.get('quantity')
            media = child_variant.get('media')
            specifications = child_variant.get('specifications', None)

            if id != 0:
                child_prod = self.update_existing_child(category, child_variant)
                if quantity and quantity > 0:
                    self.update_quantity(child_prod, quantity)
                elif child_prod.is_out_of_stock:
                    self.remove_prod_quantity(child_prod)

                if specifications:
                    self.update_or_add_specifications(child_prod, specifications)
                if media and len(media) > 0:
                    url_list = self.add_media(media, url_list, child_prod)
            else:
                child_prod = self.add_new_child(
                    instance, category, child_variant)
                if quantity and quantity > 0:
                    self.update_quantity(child_prod, quantity)
                elif child_prod.is_out_of_stock:
                    self.remove_prod_quantity(child_prod)

                if specifications:
                    self.update_or_add_specifications(child_prod, specifications)
                if media and len(media) > 0:
                    url_list = self.add_media(media, url_list, child_prod)

        return url_list

    def add_resized_thumbnail_image(self, product):
        if not product.medias.filter(is_thumbnail=True).exists():
            media_url = product.get_media_url()
            if media_url != "":
                file_name = ""
                basewidth = 200

                if "png" in media_url:
                    file_name = media_url.split("/")[-1].split(".png")[0]
                elif "jpeg" in media_url:
                    file_name = media_url.split("/")[-1].split(".jpeg")[0]
                elif "jpg" in media_url:
                    file_name = media_url.split("/")[-1].split(".jpg")[0]

                if file_name != "":
                    outfile = "%s_resized" % file_name
                    new_key_value = "media/ecomm_products/medias/%s.jpeg" % outfile
                    original_key = "/".join(media_url.split("/")[3:])

                    if product.medias.exists():
                        latest_order = product.medias.latest('id').order
                        order = latest_order + 1
                    else:
                        order = 1
                    EcommProductMedia.objects.update_or_create(
                        product=product,
                        is_thumbnail=True,
                        defaults={
                            "file_data": "/".join(new_key_value.split("/")[1:]),
                            "order": order
                        },
                    )

                    s3_client = boto3.client(
                        "s3",
                        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                        region_name=settings.AWS_S3_REGION
                    )
                    bucket = settings.AWS_STORAGE_BUCKET_NAME
                    print("original_key")
                    print(original_key)
                    print("product_id")
                    print(product.id)
                    try:
                        response = s3_client.get_object(Bucket=bucket, Key=original_key)
                    except Exception as e:
                        response = None
                    if response:
                        body = response['Body']
                        image = Image.open(body)
                        rgb_im = image.convert('RGB')
                        wpercent = (basewidth / float(rgb_im.size[0]))
                        hsize = int((float(rgb_im.size[1]) * float(wpercent)))
                        img = rgb_im.resize((basewidth, hsize), Image.ANTIALIAS)

                        with BytesIO() as output:
                            img.save(output, format="jpeg", quality=75)
                            output.seek(0)

                            s3_client.put_object(
                                ACL="public-read",
                                Bucket=bucket, Key=new_key_value,
                                Body=output, ContentType="images/jpeg"
                            )

    def add_media(self, media, url_list, product):
        for media in media:
            file_name = media.get("file_name")
            file_type = media.get("file_type")
            order = media.get("order")

            key, path = get_ecomm_prod_media_key_and_path(
                file_name, file_type)
            url_list.append(get_presigned_url(key, file_type))
            EcommProductMedia.objects.create(
                product=product, file_data=path,
                order=order,
                is_thumbnail=False
            )
        if settings.SITE_CODE == 2 or settings.SITE_CODE == 3:
            self.add_resized_thumbnail_image(product)
        return url_list

    def update_quantity(self, product, quantity):
        if product.parent:
            store = product.parent.store
        else:
            store = product.store
        if store:
            if store.inventories.exists():
                inventory = store.inventories.first()
                InventoryProduct.objects.update_or_create(
                    product=product,
                    inventory=inventory,
                    defaults={'quantity': quantity}
                )
            else:
                inv = Inventory.objects.create(
                    name=store.name,
                    nameAR=store.nameAR,
                    store=store
                )
                InventoryProduct.objects.create(
                    product=product, quantity=quantity,
                    inventory=inv
                )

    def update_or_add_specifications(self, instance, specifications):
        for specification_data in specifications:
            if specification_data.get("id") != 0:
                specification = get_object_or_404(
                    ProductSpecification, pk=specification_data.get("id"))
                specification.value = specification_data.get("value")
                specification.valueAR = specification_data.get("valueAR")
                specification.specification = specification_data.get("specification")
                specification.specificationAR = specification_data.get("specificationAR")
                specification.save()
            else:
                ProductSpecification.objects.create(
                    value=specification_data.get("value"),
                    valueAR=specification_data.get("valueAR"),
                    specification=specification_data.get("specification"),
                    specificationAR=specification_data.get("specificationAR"),
                    product=instance)

    def add_search_keys(self, search_keys, product):
        for search_key_data in search_keys:
            keyword = search_key_data.get('keyword')
            search_key = SearchKeyWord.objects.get_or_create(
                keyword=keyword, searched_for='product')[0]
            product.additional_search_keywords.add(search_key)

    def add_search_keys_ar(self, search_keys_ar, product):
        for search_key_ar_data in search_keys_ar:
            keyword_ar = search_key_ar_data.get('keyword_ar')
            search_key_ar = SearchKeyWordAR.objects.get_or_create(
                keyword_ar=keyword_ar, searched_for='product')[0]
            product.additional_search_keywords_ar.add(search_key_ar)

    def update_product_fields(self, product, validated_data):
        product.name = validated_data.get(
            "name", product.name)
        product.nameAR = validated_data.get(
            "nameAR", product.nameAR)
        product.description = validated_data.get(
            "overview", product.description)
        product.descriptionAR = validated_data.get(
            "overviewAR", product.descriptionAR)
        product.size_guide = validated_data.get(
            "size_guide", product.size_guide)
        product.size_guide_ar = validated_data.get(
            "size_guide_ar", product.size_guide_ar)
        product.decline_reason = validated_data.get(
            "decline_reason", product.decline_reason)
        product.sku = validated_data.get(
            "sku", product.sku)
        product.base_price = validated_data.get(
            "base_price", product.base_price)
        product.discounted_price = validated_data.get(
            "discounted_price", product.discounted_price)
        product.available_from = validated_data.get(
            "available_from", product.available_from)
        product.barCode = validated_data.get(
            "barCode", product.barCode)

        self.update_discounted_price(product)

        product.category = validated_data.get(
            "category", product.category)
        product.store = validated_data.get(
            "seller", product.store)
        product.brand = validated_data.get(
            "brand", product.brand)
        product.status = validated_data.get(
            "status", product.status)
        product.is_out_of_stock = validated_data.get(
            "is_out_of_stock", product.is_out_of_stock)
        product.is_new_arrival = validated_data.get(
            "is_new_arrival", product.is_new_arrival)

        product.save()
        return product

    def update(self, instance, validated_data):
        try:
            instance = self.update_product_fields(instance, validated_data)

            child_variants = validated_data.pop('child_variants', None)
            specifications = validated_data.pop('specifications', None)
            category = validated_data.get('category')
            media = validated_data.pop('media', None)
            search_keys = validated_data.pop('search_keys', None)
            search_keys_ar = validated_data.pop('search_keys_ar', None)
            collections = validated_data.pop('collections', None)

            url_list = []

            if media and len(media) > 0:
                url_list = self.add_media(media, url_list, instance)

            quantity = validated_data.pop('quantity', None)

            if quantity and quantity > 0:
                self.update_quantity(instance, quantity)
            elif instance.is_out_of_stock:
                self.remove_prod_quantity(instance)

            if specifications:
                self.update_or_add_specifications(instance, specifications)

            if search_keys:
                self.add_search_keys(search_keys, instance)

            if search_keys_ar:
                self.add_search_keys_ar(search_keys_ar, instance)

            if child_variants:
                url_list = self.add_child_variants_and_get_url_list(
                    category, instance, child_variants, url_list)

            if collections:
                for collections_data in collections:
                    collection_id = collections_data.pop('id', None)
                    collection = get_object_or_404(ProductCollection, pk=collection_id)
                    collection.products.add(instance)
                    child_var_prods = instance.children.all()
                    collection.products.add(*child_var_prods)

            instance.save()
            return url_list, instance, "Success"
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            report_to_developer("Issue in edit product", str(e)
                                + "at %s, line number %s" % (fname, exc_tb.tb_lineno))
            return None, None, str(e)


class EditProductSerializer(serializers.ModelSerializer):
    overview = serializers.CharField(
        required=False, allow_blank=True,
        allow_null=True)
    overviewAR = serializers.CharField(
        required=False, allow_blank=True,
        allow_null=True)
    media = serializers.JSONField(required=False)
    seller = serializers.IntegerField(required=True)
    specifications = SpecificationEditSerializer(many=True, required=False)
    child_variants = ChildProductEditSerializer(many=True, required=False)
    available_from = serializers.DateTimeField(
        required=False, format="%Y-%m-%d %H:%M:%S")
    search_keys = ProductSearchKeywordEditSerializer(many=True, required=False)
    search_keys_ar = ProductSearchKeywordAREditSerializer(many=True, required=False)
    quantity = serializers.IntegerField(required=True)
    collections = NestedCollectionSerializer(required=False, many=True)
    barCode = serializers.CharField(required=False)

    class Meta:
        model = EcommProduct
        fields = ('name', 'nameAR', 'overview', 'overviewAR',
                  'specifications', 'size_guide', 'size_guide_ar',
                  'child_variants', 'category', 'seller', 'brand',
                  'status', 'is_out_of_stock', 'is_new_arrival', 'media',
                  'base_price', 'discounted_price', 'sku',
                  'available_from', 'search_keys', 'search_keys_ar',
                  'decline_reason', 'quantity', 'barCode', 'collections')

    def validate_seller(self, value):
        try:
            store = Store.objects.get(
                id=value
            )
        except Store.DoesNotExist:
            raise ValidationError("Seller does not exist ")
        return store

    def validate_barCode(self, value):
        if self.instance and self.instance.barCode:
            if self.instance.barCode == value:
                return value
            prods = EcommProduct.objects.filter(
                barCode=value
            )
            if prods.exists():
                raise ValidationError("BarCode must be unique")
            return value
        return value

    def validate(self, attrs):
        seller = attrs.get("seller")
        category = attrs.get("category")

        if category and seller:
            if category.parent:
                category_ancestor = Category.objects.ancestors(category).exclude(
                    Q(id=category.id) | Q(parent__isnull=False)).first()
                if category_ancestor not in seller.selling_categories.all():
                    raise ValidationError("Selected main category is not applicable")
            else:
                if category not in seller.selling_categories.all():
                    raise ValidationError("Selected main category is not applicable")
        return attrs

    def remove_prod_quantity(self, product):
        product.inventoryProducts.filter(
            inventory__store=product.store
        ).delete()

    def update_discounted_price(self, product):
        if int(product.discounted_price) == 0:
            try:
                product.discount
                Discount.objects.filter(
                    product=product
                ).delete()
            except ObjectDoesNotExist:
                pass
        elif int(product.discounted_price) > 0 and int(product.base_price) > 0:
            reduction = product.base_price - product.discounted_price
            percentage = (reduction * 100) / product.base_price
            Discount.objects.update_or_create(
                product=product,
                defaults={'percentage': percentage}
            )

    def update_existing_child(self, category, child_variant):
        overview = child_variant.get('overview')
        overviewAR = child_variant.get('overviewAR')
        base_price = child_variant.get('base_price')
        discounted_price = child_variant.get('discounted_price')
        barCode = child_variant.get('barCode')
        sku = child_variant.get('sku')
        id = child_variant.get('id')
        variants = child_variant.get('variants')

        child_pr = get_object_or_404(
            EcommProduct, pk=id)
        child_pr.description = overview
        child_pr.descriptionAR = overviewAR
        child_pr.sku = sku
        child_pr.base_price = base_price
        child_pr.discounted_price = discounted_price
        child_pr.category = category
        child_pr.barCode = barCode

        child_pr.brand = child_pr.parent.brand
        child_pr.status = child_pr.parent.status
        child_pr.available_from = child_pr.parent.available_from
        child_pr.store = child_pr.parent.store
        child_pr.save()

        self.update_discounted_price(child_pr)

        for variant in variants:
            id = variant.get('id')
            name = variant.get('name')
            nameAR = variant.get('nameAR')
            variant_values = variant.get('variant_values')

            if id != 0:
                variant = get_object_or_404(
                    Variant, pk=id)
                variant.name = name
                variant.nameAR = nameAR
                variant.save()
            else:
                variant = Variant.objects.get_or_create(
                    category=category, name=name,
                    nameAR=nameAR)[0]

            for variant_value in variant_values:
                variant_value_id = variant_value.get('id')
                value = variant_value.get('value')
                valueAR = variant_value.get('valueAR')

                print("variant_value")
                print(variant_value)
                print(variant_value_id)
                print(value)
                print(valueAR)
                if variant_value_id != 0:
                    print("vvvvv")
                    print(variant_value_id)
                    variant_value = get_object_or_404(
                        VariantValues, pk=variant_value_id)
                    print(variant_value)
                    variant_value.value = value
                    variant_value.valueAR = nameAR
                    variant.save()
                else:
                    variant_value = VariantValues.objects.get_or_create(
                        variant=variant,
                        value=value,
                        valueAR=valueAR)[0]

                    ProductVariantValue.objects.get_or_create(
                        product=child_pr,
                        variant_value=variant_value
                    )

        return child_pr

    def add_new_child(self, instance, category, child_variant):
        overview = child_variant.get('overview')
        overviewAR = child_variant.get('overviewAR')
        base_price = child_variant.get('base_price')
        discounted_price = child_variant.get('discounted_price')
        sku = child_variant.get('sku')
        barCode = child_variant.get('barCode')
        variants = child_variant.get('variants')

        child_pr = EcommProduct.objects.create(
            parent=instance, name=instance.name,
            nameAR=instance.nameAR,
            description=overview,
            descriptionAR=overviewAR,
            category=category,
            brand=instance.brand,
            store=instance.store, sku=sku,
            base_price=base_price,
            discounted_price=discounted_price,
            status=instance.status,
            available_from=instance.available_from,
            barCode=barCode
        )

        self.update_discounted_price(child_pr)

        for variant in variants:
            id = variant.get('id')
            name = variant.get('name')
            nameAR = variant.get('nameAR')
            variant_values = variant.get('variant_values')

            if id != 0:
                variant = get_object_or_404(
                    Variant, pk=id)
                variant.name = name
                variant.nameAR = nameAR
                variant.save()
            else:
                variant = Variant.objects.get_or_create(
                    category=category, name=name,
                    nameAR=nameAR)[0]

            for variant_value in variant_values:
                id = variant_value.get('id')
                value = variant_value.get('value')
                valueAR = variant_value.get('valueAR')

                if id != 0:
                    variant_value = get_object_or_404(
                        VariantValues, pk=id)
                    variant_value.value = value
                    variant_value.valueAR = nameAR
                    variant.save()
                else:
                    variant_value = VariantValues.objects.get_or_create(
                        variant=variant,
                        value=value,
                        valueAR=valueAR)[0]

                    ProductVariantValue.objects.get_or_create(
                        product=child_pr,
                        variant_value=variant_value
                    )

        return child_pr

    def add_child_variants_and_get_url_list(
            self, category, instance, child_variants, url_list):

        for child_variant in child_variants:
            id = child_variant.get('id')
            quantity = child_variant.get('quantity')
            media = child_variant.get('media')
            specifications = child_variant.get('specifications', None)

            if id != 0:
                child_prod = self.update_existing_child(category, child_variant)
                if quantity and quantity > 0:
                    self.update_quantity(child_prod, quantity)
                elif child_prod.is_out_of_stock:
                    self.remove_prod_quantity(child_prod)

                if specifications:
                    self.update_or_add_specifications(child_prod, specifications)
                if media and len(media) > 0:
                    url_list = self.add_media(media, url_list, child_prod)
            else:
                child_prod = self.add_new_child(
                    instance, category, child_variant)
                if quantity and quantity > 0:
                    self.update_quantity(child_prod, quantity)
                elif child_prod.is_out_of_stock:
                    self.remove_prod_quantity(child_prod)
                if specifications:
                    self.update_or_add_specifications(child_prod, specifications)
                if media and len(media) > 0:
                    url_list = self.add_media(media, url_list, child_prod)

        return url_list

    def add_resized_thumbnail_image(self, product):
        if not product.medias.filter(is_thumbnail=True).exists():
            media_url = product.get_media_url()
            if media_url != "":
                file_name = ""
                basewidth = 200

                if "png" in media_url:
                    file_name = media_url.split("/")[-1].split(".png")[0]
                elif "jpeg" in media_url:
                    file_name = media_url.split("/")[-1].split(".jpeg")[0]
                elif "jpg" in media_url:
                    file_name = media_url.split("/")[-1].split(".jpg")[0]

                if file_name != "":
                    outfile = "%s_resized" % file_name
                    new_key_value = "media/ecomm_products/medias/%s.jpeg" % outfile
                    original_key = "/".join(media_url.split("/")[3:])

                    if product.medias.exists():
                        latest_order = product.medias.latest('id').order
                        order = latest_order + 1
                    else:
                        order = 1
                    EcommProductMedia.objects.update_or_create(
                        product=product,
                        is_thumbnail=True,
                        defaults={
                            "file_data": "/".join(new_key_value.split("/")[1:]),
                            "order": order
                        },
                    )

                    s3_client = boto3.client(
                        "s3",
                        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                        region_name=settings.AWS_S3_REGION
                    )
                    bucket = settings.AWS_STORAGE_BUCKET_NAME
                    print("original_key")
                    print(original_key)
                    print("product_id")
                    print(product.id)
                    try:
                        response = s3_client.get_object(Bucket=bucket, Key=original_key)
                    except Exception as e:
                        response = None
                    if response:
                        body = response['Body']
                        image = Image.open(body)
                        rgb_im = image.convert('RGB')
                        wpercent = (basewidth / float(rgb_im.size[0]))
                        hsize = int((float(rgb_im.size[1]) * float(wpercent)))
                        img = rgb_im.resize((basewidth, hsize), Image.ANTIALIAS)

                        with BytesIO() as output:
                            img.save(output, format="jpeg", quality=75)
                            output.seek(0)

                            s3_client.put_object(
                                ACL="public-read",
                                Bucket=bucket, Key=new_key_value,
                                Body=output, ContentType="images/jpeg"
                            )

    def add_media(self, media, url_list, product):
        for media in media:
            file_name = media.get("file_name")
            file_type = media.get("file_type")
            order = media.get("order")

            key, path = get_ecomm_prod_media_key_and_path(
                file_name, file_type)
            url_list.append(get_presigned_url(key, file_type))
            EcommProductMedia.objects.create(
                product=product, file_data=path,
                order=order,
                is_thumbnail=False
            )
        if settings.SITE_CODE == 2 or settings.SITE_CODE == 3:
            self.add_resized_thumbnail_image(product)
        return url_list

    def update_quantity(self, product, quantity):
        print("update_qty")
        print(product)
        if product.parent:
            store = product.parent.store
        else:
            store = product.store
        print("Stpre")
        print(store)
        if store:
            if store.inventories.exists():
                print("inv-xist")
                inventory = store.inventories.all().first()
                print("inventory")
                print(inventory)
                print(quantity)
                InventoryProduct.objects.update_or_create(
                    product=product,
                    inventory=inventory,
                    defaults={'quantity': quantity}
                )
            else:
                inv = Inventory.objects.create(
                    name=store.name,
                    nameAR=store.nameAR,
                    store=store
                )
                InventoryProduct.objects.create(
                    product=product, quantity=quantity,
                    inventory=inv
                )

    def update_or_add_specifications(self, instance, specifications):
        for specification_data in specifications:
            if specification_data.get("id") != 0:
                specification = get_object_or_404(
                    ProductSpecification, pk=specification_data.get("id"))
                specification.value = specification_data.get("value")
                specification.valueAR = specification_data.get("valueAR")
                specification.specification = specification_data.get("specification")
                specification.specificationAR = specification_data.get("specificationAR")
                specification.save()
            else:
                ProductSpecification.objects.create(
                    value=specification_data.get("value"),
                    valueAR=specification_data.get("valueAR"),
                    specification=specification_data.get("specification"),
                    specificationAR=specification_data.get("specificationAR"),
                    product=instance)

    def add_search_keys(self, search_keys, product):
        for search_key_data in search_keys:
            keyword = search_key_data.get('keyword')
            search_key = SearchKeyWord.objects.get_or_create(
                keyword=keyword, searched_for='product')[0]
            product.additional_search_keywords.add(search_key)

    def add_search_keys_ar(self, search_keys_ar, product):
        for search_key_ar_data in search_keys_ar:
            keyword_ar = search_key_ar_data.get('keyword_ar')
            search_key_ar = SearchKeyWordAR.objects.get_or_create(
                keyword_ar=keyword_ar, searched_for='product')[0]
            product.additional_search_keywords_ar.add(search_key_ar)

    def update_product_fields(self, product, validated_data):
        product.name = validated_data.get(
            "name", product.name)
        product.nameAR = validated_data.get(
            "nameAR", product.nameAR)
        product.description = validated_data.get(
            "overview", product.description)
        product.descriptionAR = validated_data.get(
            "overviewAR", product.descriptionAR)
        product.size_guide = validated_data.get(
            "size_guide", product.size_guide)
        product.size_guide_ar = validated_data.get(
            "size_guide_ar", product.size_guide_ar)
        product.decline_reason = validated_data.get(
            "decline_reason", product.decline_reason)
        product.sku = validated_data.get(
            "sku", product.sku)
        product.base_price = validated_data.get(
            "base_price", product.base_price)
        product.discounted_price = validated_data.get(
            "discounted_price", product.discounted_price)
        product.available_from = validated_data.get(
            "available_from", product.available_from)
        product.barCode = validated_data.get(
            "barCode", product.barCode)

        product.category = validated_data.get(
            "category", product.category)
        product.store = validated_data.get(
            "seller", product.store)
        product.brand = validated_data.get(
            "brand", product.brand)
        product.status = validated_data.get(
            "status", product.status)
        product.is_out_of_stock = validated_data.get(
            "is_out_of_stock", product.is_out_of_stock)
        product.is_new_arrival = validated_data.get(
            "is_new_arrival", product.is_new_arrival)

        self.update_discounted_price(product)

        product.save()
        return product

    def update(self, instance, validated_data):
        try:
            instance = self.update_product_fields(instance, validated_data)

            child_variants = validated_data.pop('child_variants', None)
            specifications = validated_data.pop('specifications', None)
            category = validated_data.get('category')
            media = validated_data.pop('media', None)
            search_keys = validated_data.pop('search_keys', None)
            search_keys_ar = validated_data.pop('search_keys_ar', None)
            collections = validated_data.pop('collections', None)

            url_list = []

            if media and len(media) > 0:
                url_list = self.add_media(media, url_list, instance)

            quantity = validated_data.pop('quantity', None)

            if quantity and quantity > 0:
                self.update_quantity(instance, quantity)
            elif instance.is_out_of_stock:
                self.remove_prod_quantity(instance)

            if specifications:
                self.update_or_add_specifications(instance, specifications)

            if search_keys:
                self.add_search_keys(search_keys, instance)

            if search_keys_ar:
                self.add_search_keys_ar(search_keys_ar, instance)

            if child_variants:
                url_list = self.add_child_variants_and_get_url_list(
                    category, instance, child_variants, url_list)

            if collections:
                for collections_data in collections:
                    collection_id = collections_data.pop('id', None)
                    collection = get_object_or_404(ProductCollection, pk=collection_id)
                    collection.products.add(instance)
                    child_var_prods = instance.children.all()
                    collection.products.add(*child_var_prods)

            instance.save()
            return url_list, instance, "Success"
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            report_to_developer("Issue in edit product", str(e)
                                + "at %s, line number %s" % (fname, exc_tb.tb_lineno))
            return None, None, str(e)


class ChildProdSerializer(serializers.ModelSerializer):
    variant_values = serializers.SerializerMethodField()
    overview = serializers.SerializerMethodField()
    overviewAR = serializers.SerializerMethodField()
    media = serializers.SerializerMethodField()
    quantity = serializers.SerializerMethodField()
    specifications = serializers.SerializerMethodField()

    class Meta:
        model = EcommProduct
        fields = ('id', 'overview', 'overviewAR',
                  'specifications', 'size_guide', 'size_guide_ar',
                  'status', 'is_out_of_stock', 'is_new_arrival', 'media',
                  'base_price', 'discounted_price', 'sku',
                  'variant_values', 'quantity', 'barCode')

    def get_overview(self, obj):
        return obj.description

    def get_overviewAR(self, obj):
        return obj.descriptionAR

    def get_quantity(self, obj):
        if obj.inventoryProducts.filter(
                inventory__store=obj.store).exists():
            inv_prod = obj.inventoryProducts.all().filter(
                inventory__store=obj.store
            ).first()
            return inv_prod.quantity
        return 0

    def get_variant_values(self, obj):
        variant_value_ids = obj.productVariantValue.all().values_list(
            "variant_value", flat=True).distinct()
        variant_values = VariantValues.objects.filter(
            pk__in=variant_value_ids
        )
        return VariantValueDetailSerializer(
            variant_values, many=True, context=obj).data

    def get_media(self, obj):
        medias = obj.medias.filter(is_thumbnail=False)
        return ProductMediaDetailSerializer(
            medias, many=True).data

    def get_specifications(self, obj):
        return SpecificationDetailSerializer(
            obj.specifications.all(), many=True).data


class SellerInfoSerializer(serializers.ModelSerializer):

    class Meta:
        model = Store
        fields = (
            "id", "name", "nameAR", "image", "phone", "address",
            "contact_email"
        )


class ProductDetailSerializer(serializers.ModelSerializer):
    overview = serializers.SerializerMethodField()
    overviewAR = serializers.SerializerMethodField()
    media = serializers.SerializerMethodField()
    child_variants = serializers.SerializerMethodField()
    search_keys = serializers.SerializerMethodField()
    search_keys_ar = serializers.SerializerMethodField()
    seller = serializers.SerializerMethodField()
    specifications = serializers.SerializerMethodField()
    quantity = serializers.SerializerMethodField()
    category = CategorySuggestionSerializer()
    collections = serializers.SerializerMethodField()
    brand = serializers.SerializerMethodField()
    available_from = serializers.SerializerMethodField()
    child_collections = serializers.SerializerMethodField()

    class Meta:
        model = EcommProduct
        fields = ('id', 'name', 'nameAR', 'overview', 'overviewAR',
                  'specifications', 'size_guide', 'size_guide_ar',
                  'child_variants', 'category', 'seller', 'status',
                  'is_out_of_stock', 'is_new_arrival', 'media',
                  'base_price', 'discounted_price', 'sku',
                  'available_from', 'search_keys', 'search_keys_ar',
                  'quantity', 'collections', 'brand',
                  'child_collections', 'barCode', 'decline_reason')

    def get_overview(self, obj):
        return obj.description

    def get_overviewAR(self, obj):
        return obj.descriptionAR

    def get_brand(self, obj):
        if obj.brand:
            return BrandSerializer(obj.brand).data
        return None

    def get_seller(self, obj):
        return SellerInfoSerializer(obj.store).data

    def get_specifications(self, obj):
        return SpecificationDetailSerializer(
            obj.specifications.all(), many=True).data

    def get_quantity(self, obj):
        if obj.inventoryProducts.filter(
                inventory__store=obj.store).exists():
            inv_prod = obj.inventoryProducts.all().filter(
                inventory__store=obj.store
            ).first()
            return inv_prod.quantity
        return 0

    def get_child_variants(self, obj):
        children = obj.children.all()
        return ChildProdSerializer(children, many=True).data

    def get_media(self, obj):
        medias = obj.medias.filter(is_thumbnail=False)
        return ProductMediaDetailSerializer(
            medias, many=True).data

    def get_search_keys(self, obj):
        search_keys = obj.additional_search_keywords.all()
        return SearchKeywordDetailSerializer(
            search_keys, many=True).data

    def get_search_keys_ar(self, obj):
        search_keys_ar = obj.additional_search_keywords_ar.all()
        return SearchKeywordARDetailSerializer(
            search_keys_ar, many=True).data

    def get_collections(self, obj):
        if obj.prod_collections.exists():
            collections = obj.prod_collections.all()
            return CollectionDetailSerializer(
                collections, many=True).data
        return None

    def get_child_collections(self, obj):
        if obj.children.exists():
            children = obj.children.all()
            collections = ProductCollection.objects.filter(
                products__in=children
            ).exclude(products__pk=obj.pk)
            return CollectionDetailSerializer(
                collections, many=True).data
        return None

    def get_available_from(self, obj):
        if obj.available_from:
            kuwait_date = datetime_from_utc_to_local_new(obj.available_from)
            return obj.available_from
            # return kuwait_date
        return ""


class ProductInReviewListSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    brand = BrandSerializer()
    seller = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()

    class Meta:
        model = EcommProduct
        fields = (
            "id", "name", "image",
            "brand", "sku", "seller",
            "base_price", "discounted_price",
            "barCode"
        )

    def get_name(self, obj):
        var_vals_list = VariantValues.objects.filter(
            pk__in=obj.variant_value_ids()
        ).values_list('value', flat=True)
        var_string = ",".join(list(var_vals_list))
        if obj.name and obj.name != "":
            return "".join([obj.name, "-", var_string])
        return var_string

    def get_image(self, obj):
        if obj.medias.exists():
            return obj.medias.first().file_data.url
        return None

    def get_seller(self, obj):
        if obj.store:
            return SellerInfoSerializer(obj.store).data
        return None


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


class ProductInReviewDetailSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    brand = BrandSerializer()
    seller = serializers.SerializerMethodField()
    variant_with_value = serializers.SerializerMethodField()

    class Meta:
        model = EcommProduct
        fields = (
            "id", "name", "image",
            "brand", "seller", "variant_with_value",
            "barCode"
        )

    def get_image(self, obj):
        if obj.medias.exists():
            return obj.medias.first().file_data.url
        return None

    def get_seller(self, obj):
        return SellerInfoSerializer(obj.store).data

    def get_variant_with_value(self, obj):
        var_vals = VariantValues.objects.filter(
            pk__in=obj.product.variant_value_ids()
        )
        return VariantValuesMinSerializer(
            var_vals, many=True, context=self.context).data


class EcommProductRatingSerializer(serializers.ModelSerializer):
    seller_info = serializers.SerializerMethodField()
    product = serializers.SerializerMethodField()
    reviews_count = serializers.SerializerMethodField()
    users_count = serializers.SerializerMethodField()
    overall_rating = serializers.SerializerMethodField()
    remark = serializers.SerializerMethodField()
    last_added_date = serializers.SerializerMethodField()

    class Meta:
        model = EcommProductRatingandReview
        fields = ('id', 'product', 'seller_info', 'reviews_count',
                  'users_count', 'overall_rating', 'remark',
                  'last_added_date')

    def get_seller_info(self, obj):
        from app.order.serializers import SellerListByCategorySerializer
        if obj.product.store:
            return SellerListByCategorySerializer(obj.product.store).data
        return None

    def get_product(self, obj):
        return ProductInReviewListSerializer(obj.product).data

    def get_reviews_count(self, obj):
        if obj.product.prod_ratings.exists():
            reviews_count = obj.product.prod_ratings.all().count()
            return reviews_count
        return 0

    def get_users_count(self, obj):
        if obj.product.prod_ratings.exists():
            users_count = obj.product.prod_ratings.all().order_by(
                'member_id').distinct('member_id').count()
            return users_count
        return 0

    def get_overall_rating(self, obj):
        return obj.product.get_overall_rating()

    def get_remark(self, obj):
        return rating_string(obj.product.get_overall_rating(), "en")

    def get_last_added_date(self, obj):
        if obj.product.prod_ratings.exists():
            latest_rating = obj.product.prod_ratings.latest('id')
            if latest_rating.updated_at:
                return latest_rating.updated_at
            return None
            # kuwait_date = convert_date_time_to_kuwait_string(latest_rating.updated_at)
            # return humanize.naturalday(latest_rating.updated_at).capitalize()
            # return humanize.naturalday(kuwait_date).capitalize()
        return ""


class EcommProdRatingListSerializer(serializers.ModelSerializer):
    reviews_count = serializers.SerializerMethodField()
    remark = serializers.SerializerMethodField()
    customer = serializers.SerializerMethodField()
    order_status = serializers.SerializerMethodField()

    class Meta:
        model = EcommProductRatingandReview
        fields = ('id', 'reviews_count', 'order_status',
                  'review', 'star', 'remark',
                  'created_at', 'customer')

    def get_customer(self, obj):
        from app.order.serializers import CustomerSerializer
        return CustomerSerializer(obj.member).data

    def get_reviews_count(self, obj):
        if obj.product.prod_ratings.exists():
            reviews_count = obj.product.prod_ratings.all().count()
            return reviews_count
        return 0

    def get_order_status(self, obj):
        if obj.member.orders.exists():
            prod_with_order = obj.member.orders.filter(
                orderProducts__product=obj.product
            )
            if prod_with_order.exists():
                return "Ordered"
        return "Not Ordered"

    def get_remark(self, obj):
        print("remark_from_rating")
        print(obj.product.overall_rating)
        return rating_string(obj.product.overall_rating, "en")


class EcommProductRatingDetailSerializer(serializers.ModelSerializer):
    review_list = serializers.SerializerMethodField()
    product = serializers.SerializerMethodField()
    reviews_count = serializers.SerializerMethodField()

    class Meta:
        model = EcommProductRatingandReview
        fields = ('id', 'product', 'review_list', 'reviews_count')

    def search(self, qs, search_string):
        for qstring in search_string.split(" "):
            qs = qs.filter(
                Q(member__first_name__icontains=qstring)
                | Q(member__last_name__icontains=qstring)
                | Q(member__full_name__icontains=qstring)
            ).order_by('id').distinct()
        return qs

    def get_review_list(self, obj):
        qs = obj.product.prod_ratings.all()
        search_string = self.context.get("search_string", "")
        remark = self.context.get("remark", "")
        sort_by = self.context.get("sort_by", "")
        order_status = self.context.get("order_status", "")
        days = self.context.get("days", None)
        from_date = self.context.get("from_date", None)
        to_date = self.context.get("to_date", None)

        if sort_by != "":
            if sort_by == "CUSTNAMEATOZ":
                qs = qs.order_by('member__full_name')
            if sort_by == "CUSTNAMEZTOA":
                qs = qs.order_by('-member__full_name')

            if sort_by == "ORATHIGHTOLOW":
                qs = qs.order_by('-star')
            if sort_by == "ORATLOWTOHIGH":
                qs = qs.order_by('star')

            if sort_by == "DATENEWFIRST":
                qs = qs.order_by('-updated_at')
            if sort_by == "DATEOLDFIRST":
                qs = qs.order_by('updated_at')

        if search_string != "":
            qs = self.search(qs, search_string)

        if days:
            date_selected = now() - timedelta(days=int(days))
            qs = qs.filter(updated_at__date__gte=date_selected.date())

        if from_date and to_date:
            qs = qs.filter(
                updated_at__date__gte=from_date,
                updated_at__date__lte=to_date)

        if remark != "":
            if remark == "Excellent":
                qs = qs.filter(
                    product__overall_rating__gte=4,
                    product__overall_rating__lte=5)
            if remark == "Very Good":
                qs = qs.filter(
                    product__overall_rating__gte=3,
                    product__overall_rating__lt=4)
            if remark == "Good":
                qs = qs.filter(
                    product__overall_rating__gte=2,
                    product__overall_rating__lt=3)
            if remark == "Bad":
                qs = qs.filter(
                    product__overall_rating__gte=1,
                    product__overall_rating__lt=2)

        if order_status != "":
            qs = [x for x in qs if x.get_order_status() == order_status]

        return EcommProdRatingListSerializer(qs, many=True).data

    def get_product(self, obj):
        return ProductInReviewListSerializer(obj.product).data

    def get_reviews_count(self, obj):
        if obj.product.prod_ratings.exists():
            reviews_count = obj.product.prod_ratings.all().count()
            return reviews_count
        return 0


class CollectionConditionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCollectionCond
        fields = ('field', 'operator', 'value')


class CollectionConditionDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCollectionCond
        fields = ('id', 'field', 'operator', 'value')


class AddCollectionSerializer(serializers.ModelSerializer):
    conditions = CollectionConditionSerializer(many=True, required=False)
    status_start_date = serializers.DateTimeField(
        required=False, format="%Y-%m-%d %H:%M:%S")
    status_end_date = serializers.DateTimeField(
        required=False, format="%Y-%m-%d %H:%M:%S")

    class Meta:
        model = ProductCollection
        fields = ('name', 'nameAR', 'type', 'status', 'status_start_date',
                  'status_end_date', 'all_cond_match', 'conditions',
                  'seller')

    def create(self, validated_data):
        conditions = validated_data.pop('conditions', None)
        collection = ProductCollection.objects.create(**validated_data)
        if conditions:
            for condition in conditions:
                field = condition.get('field')
                operator = condition.get('operator')
                value = condition.get('value')
                ProductCollectionCond.objects.create(
                    field=field, operator=operator,
                    value=value, collections=collection
                )
        return collection


class EditCollectionSerializer(serializers.ModelSerializer):
    conditions = CollectionConditionSerializer(many=True, required=False)
    status_start_date = serializers.DateTimeField(
        required=False, format="%Y-%m-%d %H:%M:%S")
    status_end_date = serializers.DateTimeField(
        required=False, format="%Y-%m-%d %H:%M:%S")

    class Meta:
        model = ProductCollection
        fields = ('name', 'nameAR', 'type', 'status', 'status_start_date',
                  'status_end_date', 'all_cond_match', 'conditions',
                  'seller')

    def update(self, instance, validated_data):
        instance.name = validated_data.get(
            "name", instance.name)
        instance.nameAR = validated_data.get(
            "nameAR", instance.name)
        instance.type = validated_data.get(
            "type", instance.type)
        instance.status = validated_data.get(
            "status", instance.status)
        instance.status_start_date = validated_data.get(
            "status_start_date", instance.status_start_date)
        instance.status_end_date = validated_data.get(
            "status_end_date", instance.status_end_date)
        instance.all_cond_match = validated_data.get(
            "all_cond_match", instance.all_cond_match)
        instance.seller = validated_data.get(
            "seller", instance.seller)
        instance.save()

        conditions = validated_data.pop('conditions', None)
        if conditions:
            for condition in conditions:
                id = condition.get('id')
                field = condition.get('field')
                operator = condition.get('operator')
                value = condition.get('value')

                if id == 0:
                    ProductCollectionCond.objects.create(
                        field=field, operator=operator,
                        value=value, collections=instance
                    )
                else:
                    prod_collection = get_object_or_404(ProductCollectionCond, pk=id)
                    prod_collection.field = field
                    prod_collection.operator = operator
                    prod_collection.value = value
                    prod_collection.save()
        return instance


class CollectionListSerializer(serializers.ModelSerializer):
    conditions = serializers.SerializerMethodField()
    prods_linked = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = ProductCollection
        fields = ('id', 'name', 'nameAR', 'type', 'status',
                  'status_start_date', 'status_end_date',
                  'conditions', 'prods_linked', 'created_by',
                  'all_cond_match')

    def get_status(self, obj):
        return obj.get_status_display()

    def get_prods_linked(self, obj):
        return obj.products.all().count()
        # return obj.products.all().filter(
        #     Q(available_from__lte=now())
        #     | Q(available_from=None),
        #     status='AC',
        #     isHiddenFromOrder=False).annotate(
        #     variant_count=Count('productVariantValue', distinct=True)).exclude(
        #     Q(variant_count=0, parent__isnull=False) |
        #     Q(parent=None, children__isnull=False, important=False) |
        #     Q(parent__important=True, important=False)).count()

    def get_conditions(self, obj):
        if obj.collection_conds.exists():
            conds = obj.collection_conds.all().distinct()
            return CollectionConditionDetailSerializer(conds, many=True).data
        return None

    def get_status_start_date(self, obj):
        if obj.status_start_date:
            return obj.status_start_date
        return None
        # kuwait_date = convert_date_time_to_kuwait_string(obj.status_start_date)
        # return humanize.naturalday(obj.status_start_date).capitalize()
        # return humanize.naturalday(kuwait_date).capitalize()

    def get_status_end_date(self, obj):
        if obj.status_end_date:
            return obj.status_end_date
        return None
        # kuwait_date = convert_date_time_to_kuwait_string(obj.status_end_date)
        # return humanize.naturalday(obj.status_end_date).capitalize()
        # return humanize.naturalday(kuwait_date).capitalize()

    def get_created_by(self, obj):
        from app.authentication.serializers import SellerMinSerializer
        if obj.seller:
            return SellerMinSerializer(obj.seller).data
        return None


class CollectionDetailSerializer(serializers.ModelSerializer):
    conditions = serializers.SerializerMethodField()
    prods_linked = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    prods = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = ProductCollection
        fields = ('id', 'name', 'nameAR', 'type', 'status',
                  'status_start_date', 'status_end_date',
                  'conditions', 'prods_linked', 'created_by',
                  'prods', 'all_cond_match')

    def get_status(self, obj):
        return obj.get_status_display()

    def get_prods_linked(self, obj):
        return obj.products.all().count()
        # return obj.products.all().filter(
        #     Q(available_from__lte=now())
        #     | Q(available_from=None),
        #     status='AC',
        #     isHiddenFromOrder=False).annotate(
        #     variant_count=Count('productVariantValue', distinct=True)).exclude(
        #     Q(variant_count=0, parent__isnull=False) |
        #     Q(parent=None, children__isnull=False, important=False) |
        #     Q(parent__important=True, important=False)).count()

    def get_prods(self, obj):
        return ProductMinNewSerializer(obj.products.all().filter(
            Q(available_from__lte=now())
            | Q(available_from=None),
            status='AC',
            isHiddenFromOrder=False).annotate(
            variant_count=Count('productVariantValue', distinct=True)).exclude(
            Q(variant_count=0, parent__isnull=False) |
            Q(parent=None, children__isnull=False, important=False) |
            Q(parent__important=True, important=False)), many=True).data

    def get_conditions(self, obj):
        if obj.collection_conds.exists():
            conds = obj.collection_conds.all().distinct()
            return CollectionConditionDetailSerializer(conds, many=True).data
        return None

    def get_status_start_date(self, obj):
        if obj.status_start_date:
            return obj.status_start_date
        return None
        # kuwait_date = convert_date_time_to_kuwait_string(obj.status_start_date)
        # return humanize.naturalday(obj.status_start_date).capitalize()
        # return humanize.naturalday(kuwait_date).capitalize()

    def get_status_end_date(self, obj):
        if obj.status_end_date:
            return obj.status_end_date
        return None
        # kuwait_date = convert_date_time_to_kuwait_string(obj.status_end_date)
        # return humanize.naturalday(obj.status_end_date).capitalize()
        # return humanize.naturalday(kuwait_date).capitalize()

    def get_created_by(self, obj):
        from app.authentication.serializers import SellerMinSerializer
        if obj.seller:
            return SellerMinSerializer(obj.seller).data
        return None


class CollectionDetailMinSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCollection
        fields = ('id', 'name', 'nameAR', 'type', 'status',
                  'status_start_date', 'status_end_date')

    def get_status_start_date(self, obj):
        if obj.status_start_date:
            return obj.status_start_date
        return None
        # kuwait_date = convert_date_time_to_kuwait_string(obj.status_start_date)
        # return humanize.naturalday(obj.status_start_date).capitalize()
        # return humanize.naturalday(kuwait_date).capitalize()

    def get_status_end_date(self, obj):
        if obj.status_end_date:
            return obj.status_end_date
        return None
        # kuwait_date = convert_date_time_to_kuwait_string(obj.status_end_date)
        # return humanize.naturalday(obj.status_end_date).capitalize()
        # return humanize.naturalday(kuwait_date).capitalize()


class ProductMinNewSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = EcommProduct
        fields = (
            "id", "name", "barCode"
        )

    def get_name(self, obj):
        lang_code = self.context.get("lang_code")

        if lang_code == "ar":
            var_vals_list = VariantValues.objects.filter(
                pk__in=obj.variant_value_ids()
            ).values_list('valueAR', flat=True)
            var_string = ",".join(list(var_vals_list))
            if obj.nameAR and obj.nameAR != "" and var_string != "":
                return "".join([obj.nameAR, "-", var_string])
            elif var_string == "":
                return obj.nameAR
            return var_string

        var_vals_list = VariantValues.objects.filter(
            pk__in=obj.variant_value_ids()
        ).values_list('value', flat=True)
        var_string = ",".join(list(var_vals_list))
        if obj.name and obj.name != "" and var_string != "":
            return "".join([obj.name, "-", var_string])
        elif var_string == "":
            return obj.name
        return var_string


class ProductMinNotificationSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = EcommProduct
        fields = (
            "id", "name", "barCode"
        )

    def get_name(self, obj):
        lang_code = self.context.get("lang_code")

        if lang_code == "ar":
            var_vals_list = VariantValues.objects.filter(
                pk__in=obj.variant_value_ids()
            ).values_list('valueAR', flat=True)
            var_string = "-".join(list(var_vals_list))
            if obj.nameAR and obj.nameAR != "" and var_string != "":
                return "".join([obj.nameAR, "-", var_string])
            elif var_string == "":
                return obj.nameAR
            return var_string

        var_vals_list = VariantValues.objects.filter(
            pk__in=obj.variant_value_ids()
        ).values_list('value', flat=True)
        var_string = "-".join(list(var_vals_list))
        if obj.name and obj.name != "" and var_string != "":
            return "".join([obj.name, "-", var_string])
        elif var_string == "":
            return obj.name
        return var_string


class CouponListSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()
    active_start_date = serializers.SerializerMethodField()
    active_end_date = serializers.SerializerMethodField()
    prod_count = serializers.SerializerMethodField()
    customer_count = serializers.SerializerMethodField()
    collection_count = serializers.SerializerMethodField()
    added_date = serializers.SerializerMethodField()

    class Meta:
        model = Coupon
        fields = (
            "id", "code", "type", "status", "no_of_times_used",
            "active_start_date", "active_end_date", "added_date",
            "deductable_percentage", "deductable_amount",
            "is_for_all_products", "is_for_all_customers",
            "prod_count", "customer_count", "collection_count"
        )

    def get_type(self, obj):
        return obj.get_type_display()

    def get_status(self, obj):
        return obj.get_status_display()

    def get_active_start_date(self, obj):
        if obj.active_start_date:
            return obj.active_start_date
            # kuwait_date = datetime_from_utc_to_local_new(obj.active_start_date)
            # formatted_date = obj.active_start_date.strftime("%b %d, %Y")
            # formatted_time = obj.active_start_date.strftime("%H:%M %p")
            # return f"{formatted_date} at {formatted_time}"
        return None

    def get_active_end_date(self, obj):
        if obj.active_end_date:
            return obj.active_end_date
            # kuwait_date = datetime_from_utc_to_local_new(obj.active_end_date)
            # formatted_date = obj.active_end_date.strftime("%b %d, %Y")
            # formatted_time = obj.active_end_date.strftime("%H:%M %p")
            # return f"{formatted_date} at {formatted_time}"
        return None

    def get_added_date(self, obj):
        if obj.created_at:
            return obj.created_at
            # kuwait_date = datetime_from_utc_to_local_new(obj.created_at)
            # formatted_date = obj.created_at.strftime("%b %d, %Y")
            # formatted_time = obj.created_at.strftime("%H:%M %p")
            # return f"{formatted_date} at {formatted_time}"
        return None

    def get_prod_count(self, obj):
        return obj.products.all().count()

    def get_customer_count(self, obj):
        return obj.customers.all().count()

    def get_collection_count(self, obj):
        return obj.collections.all().count()


class CouponDetailSerializer(serializers.ModelSerializer):
    collections = serializers.SerializerMethodField()
    products = serializers.SerializerMethodField()
    customers = serializers.SerializerMethodField()

    class Meta:
        model = Coupon
        fields = (
            "id", "code", "type", "status", "deductable_percentage",
            "deductable_amount", "is_for_all_products", "min_required_purchase_amt",
            "min_qty_items", "is_for_all_customers", "is_for_customers_with_no_orders",
            "no_of_times_usable", "one_use_per_customer", "active_start_date",
            "active_end_date", "collections", "products", "customers",
            "is_for_specific_customers", "send_push_immediately",
            "push_notification_schedule_date",
            "reason"
        )

    def get_collections(self, obj):
        return CollectionDetailMinSerializer(obj.collections.all(), many=True).data

    def get_products(self, obj):
        return ProductMinNewSerializer(obj.products.all(), many=True).data

    def get_customers(self, obj):
        from app.order.serializers import CustomerSerializer
        return CustomerSerializer(obj.customers.all(), many=True).data


class NestedProdSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=True)

    class Meta:
        model = EcommProduct
        fields = ('id', )


class NestedCustomerSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=True)

    class Meta:
        model = Member
        fields = ('id', )


class AddCouponSerializer(serializers.ModelSerializer):
    active_start_date = serializers.DateTimeField(
        required=False, format="%Y-%m-%d %H:%M:%S")
    active_end_date = serializers.DateTimeField(
        required=False, format="%Y-%m-%d %H:%M:%S")
    collections = NestedCollectionSerializer(required=False, many=True)
    products = NestedProdSerializer(required=False, many=True)
    customers = NestedCustomerSerializer(required=False, many=True)
    push_notification_schedule_date = serializers.DateTimeField(
        required=False, format="%Y-%m-%d %H:%M:%S")

    class Meta:
        model = Coupon
        fields = (
            "code", "type", "status", "deductable_percentage",
            "deductable_amount", "is_for_all_products", "min_required_purchase_amt",
            "min_qty_items", "is_for_all_customers", "is_for_customers_with_no_orders",
            "no_of_times_usable", "one_use_per_customer", "active_start_date",
            "active_end_date", "collections", "products", "customers",
            "is_for_specific_customers", "send_push_immediately",
            "push_notification_schedule_date",
            "reason", "is_for_specific_products", "is_for_specific_collections"
        )

    def validate(self, attrs):
        is_for_specific_customers = attrs.get("is_for_specific_customers")
        is_for_specific_products = attrs.get("is_for_specific_products")
        is_for_specific_collections = attrs.get("is_for_specific_collections")

        if str2bool(is_for_specific_customers):
            customers = attrs.get("customers")
            if len(customers) == 0:
                raise ValidationError("Please select at least one customer")

        if str2bool(is_for_specific_products):
            products = attrs.get("products")
            if len(products) == 0:
                raise ValidationError("Please select at least one product")

        if str2bool(is_for_specific_collections):
            collections = attrs.get("collections")
            if len(collections) == 0:
                raise ValidationError("Please select at least one collection")

        return attrs

    def create(self, validated_data):
        collections = validated_data.pop('collections', None)
        products = validated_data.pop('products', None)
        customers = validated_data.pop('customers', None)
        coupon = Coupon.objects.create(**validated_data)

        if products:
            for products_data in products:
                prod_id = products_data.pop('id', None)
                prod = get_object_or_404(EcommProduct, pk=prod_id)
                coupon.products.add(prod)

        if collections:
            for collections_data in collections:
                collection_id = collections_data.pop('id', None)
                collection = get_object_or_404(ProductCollection, pk=collection_id)
                coupon.collections.add(collection)

        if customers:
            for customers_data in customers:
                customer_id = customers_data.pop('id', None)
                customer = get_object_or_404(Member, pk=customer_id)
                coupon.customers.add(customer)
        return coupon


class EditCouponSerializer(serializers.ModelSerializer):
    collections = NestedCollectionSerializer(required=False, many=True)
    products = NestedProdSerializer(required=False, many=True)
    customers = NestedCustomerSerializer(required=False, many=True)
    push_notification_schedule_date = serializers.DateTimeField(
        required=False, format="%Y-%m-%d %H:%M:%S")
    active_start_date = serializers.DateTimeField(
        required=False, format="%Y-%m-%d %H:%M:%S")
    active_end_date = serializers.DateTimeField(
        required=False, format="%Y-%m-%d %H:%M:%S")

    class Meta:
        model = Coupon
        fields = (
            "code", "type", "status", "deductable_percentage",
            "deductable_amount", "is_for_all_products", "min_required_purchase_amt",
            "min_qty_items", "is_for_all_customers", "is_for_customers_with_no_orders",
            "no_of_times_usable", "one_use_per_customer", "active_start_date",
            "active_end_date", "collections", "products", "customers",
            "is_for_specific_customers", "send_push_immediately",
            "push_notification_schedule_date",
            "reason"
        )

    def validate_code(self, value):
        if self.instance.code == value:
            return value
        if Coupon.objects.filter(code=value).exists():
            raise ValidationError("Coupon code already exists")
        return value

    def update(self, instance, validated_data):
        collections = validated_data.pop('collections', None)
        products = validated_data.pop('products', None)
        customers = validated_data.pop('customers', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if validated_data.get("no_of_times_usable"):
            instance.no_of_times_usable = validated_data.get(
                "no_of_times_usable",
                instance.no_of_times_usable)
        else:
            instance.no_of_times_usable = 0

        if validated_data.get("min_required_purchase_amt"):
            instance.min_required_purchase_amt = validated_data.get(
                "min_required_purchase_amt",
                instance.min_required_purchase_amt)
        else:
            instance.min_required_purchase_amt = 0.0

        if validated_data.get("min_qty_items"):
            instance.min_qty_items = validated_data.get(
                "min_qty_items",
                instance.min_qty_items)
        else:
            instance.min_qty_items = 0

        if validated_data.get("deductable_percentage"):
            instance.deductable_percentage = validated_data.get(
                "deductable_percentage",
                instance.deductable_percentage)
        else:
            instance.deductable_percentage = 0.0

        if validated_data.get("deductable_amount"):
            instance.deductable_amount = validated_data.get(
                "deductable_amount",
                instance.deductable_amount)
        else:
            instance.deductable_amount = 0.0

        if validated_data.get("active_end_date"):
            instance.active_end_date = validated_data.get(
                "active_end_date",
                instance.active_end_date)
        else:
            instance.active_end_date = None

        if collections and len(collections) > 0:
            instance.collections.clear()
            instance.products.clear()

            for collections_data in collections:
                collection_id = collections_data.pop('id', None)
                collection = get_object_or_404(ProductCollection, pk=collection_id)
                instance.collections.add(collection)

        if products and len(products) > 0:
            instance.products.clear()
            instance.collections.clear()

            for products_data in products:
                product_id = products_data.pop('id', None)
                prod = get_object_or_404(EcommProduct, pk=product_id)
                instance.products.add(prod)

        if customers and len(customers) > 0:
            instance.customers.clear()

            for customers_data in customers:
                customer_id = customers_data.pop('id', None)
                customer = get_object_or_404(Member, pk=customer_id)
                instance.customers.add(customer)
        instance.save()
        return instance
