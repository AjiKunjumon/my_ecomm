import base64
import operator
import os
import sys
import urllib
from datetime import timedelta, datetime
from urllib.request import urlopen

import markdown as markdown
import xlrd as xlrd
from django.conf import settings
from django.contrib.auth import authenticate
from django.core.exceptions import ObjectDoesNotExist
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile
from django.db.models import Q, Count, F, Sum
from django.utils.timezone import now
from rest_framework import viewsets, status, generics
from rest_framework.authentication import TokenAuthentication
from rest_framework.generics import CreateAPIView, ListAPIView, get_object_or_404, UpdateAPIView, DestroyAPIView, \
    RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from app.authentication.models import Member
from app.authentication.permissions import IsSuperAdminOrSeller, IsSuperAdminOrObjectSeller, IsSuperAdmin
from app.product.models import Brand, Category, CategoryMedia, EcommProduct, EcommProductMedia, \
    EcommProductRatingandReview, ProductCollection, SearchKeyWord, SearchKeyWordAR, ProductVariantValue, VariantValues, \
    Variant, ProductSpecification, ProductCollectionCond, Coupon, Discount
from app.product.serializers import BrandListSerializer, BrandSerializer, AddEditBrandSerializer, \
    CategoryListSerializer, AddEditCategorySerializer, CategorySerializer, AddSubCategorySerializer, \
    ProductListSerializer, AddEditProductSerializer, ProductDetailSerializer, EditProductSerializer, \
    EcommProductRatingSerializer, EcommProductRatingDetailSerializer, AddCollectionSerializer, \
    CollectionDetailSerializer, EditBrandSerializer, AddProductDraftSerializer, EditCollectionSerializer, \
    CouponDetailSerializer, AddCouponSerializer, EditCouponSerializer, CouponListSerializer, EditProductDraftSerializer, \
    CollectionListSerializer, ProductMinNewSerializer, BrandListFilterSerializer
from app.product.utils import json_list, rating_string
from app.product.zappa_tasks import send_prod_approve_email
from app.store.models import InventoryProduct, Inventory, Store, Banner, HomePageItems
from app.store.zappa_tasks import assign_collections_to_home_page, assign_collections_to_seller_page, \
    assign_home_page_banner_item_values, assign_home_page_banner_item_values_test, edit_collections_to_home_page, \
    edit_collections_to_seller_page
from app.utilities.cache_invalidation import create_invalidation
from app.utilities.helpers import str2bool, report_to_developer


class BrandList(ListAPIView):
    permission_classes = [IsSuperAdminOrSeller]
    serializer_class = BrandListSerializer
    http_method_names = [u'get', u'post']

    def _allowed_methods(self):
        return [m.upper() for m in self.http_method_names if hasattr(self, m)]

    def search(self, qs, search_string):
        for qstring in search_string.split(" "):
            qs = qs.filter(
                Q(name__icontains=qstring)
                | Q(nameAR__icontains=qstring)
            ).order_by('id').distinct()
        return qs

    def get_serializer_context(self):
        return {"user": self.request.user,
                "lang_code": self.request.query_params.get("lang_code", "")}

    def get_queryset(self):
        search_string = self.request.query_params.get("search_string", "")
        brand_status = self.request.query_params.get("brand_status", "")
        sort_by = self.request.query_params.get("sort_by", "")
        seller_ids = self.request.data.get("seller_ids", "")
        category_id = self.request.query_params.get("category_id", "")

        qs = Brand.objects.all().order_by(
            '-created_at'
        )

        if category_id != "":
            qs = qs.filter(
                selling_categories__pk=int(category_id)
            ).distinct()

        if seller_ids != "" and json_list(seller_ids)[0]:
            qs = qs.filter(
                products__store__in=json_list(seller_ids)[1]
            ).distinct()

        if brand_status == "TopBrand":
            qs = qs.filter(is_top_brand=True)
        if brand_status == "Other":
            qs = qs.filter(is_top_brand=False)
        if search_string != "":
            qs = self.search(qs, search_string)

        if sort_by != "":
            if sort_by == "ATOZ":
                qs = qs.order_by('name')
            if sort_by == "ZTOA":
                qs = qs.order_by('-name')
            if sort_by == "prod_high_to_low":
                qs = qs.annotate(prod_count=Count(
                    'products')).order_by('-prod_count')
            if sort_by == "prod_low_to_high":
                qs = qs.annotate(prod_count=Count(
                    'products')).order_by('prod_count')
        return qs

    def post(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class BrandListFilter(ListAPIView):
    permission_classes = [IsSuperAdminOrSeller]
    serializer_class = BrandListFilterSerializer
    http_method_names = [u'get', u'post']

    def _allowed_methods(self):
        return [m.upper() for m in self.http_method_names if hasattr(self, m)]

    def search(self, qs, search_string):
        for qstring in search_string.split(" "):
            qs = qs.filter(
                Q(name__icontains=qstring)
                | Q(nameAR__icontains=qstring)
            ).order_by('id').distinct()
        return qs

    def get_serializer_context(self):
        return {"user": self.request.user,
                "lang_code": self.request.query_params.get("lang_code", "")}

    def get_queryset(self):
        search_string = self.request.query_params.get("search_string", "")
        brand_status = self.request.query_params.get("brand_status", "")
        sort_by = self.request.query_params.get("sort_by", "")
        seller_ids = self.request.data.get("seller_ids", "")
        category_id = self.request.query_params.get("category_id", "")

        qs = Brand.objects.all().order_by(
            '-created_at'
        )

        if category_id != "":
            qs = qs.filter(
                selling_categories__pk=int(category_id)
            ).distinct()

        if seller_ids != "" and json_list(seller_ids)[0]:
            qs = qs.filter(
                products__store__in=json_list(seller_ids)[1]
            ).distinct()

        if brand_status == "TopBrand":
            qs = qs.filter(is_top_brand=True)
        if brand_status == "Other":
            qs = qs.filter(is_top_brand=False)
        if search_string != "":
            qs = self.search(qs, search_string)

        if sort_by != "":
            if sort_by == "ATOZ":
                qs = qs.order_by('name')
            if sort_by == "ZTOA":
                qs = qs.order_by('-name')
            if sort_by == "prod_high_to_low":
                qs = qs.annotate(prod_count=Count(
                    'products')).order_by('-prod_count')
            if sort_by == "prod_low_to_high":
                qs = qs.annotate(prod_count=Count(
                    'products')).order_by('prod_count')
        return qs

    def post(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class BrandDetail(RetrieveAPIView):
    permission_classes = [IsSuperAdminOrSeller]
    serializer_class = BrandSerializer

    def get_object(self):
        obj = get_object_or_404(Brand, pk=self.kwargs.get("pk"))
        return obj

    def get_serializer_context(self):
        return {"user": self.request.user}


class AddBrand(CreateAPIView):
    permission_classes = [IsSuperAdmin]
    serializer_class = BrandSerializer
    queryset = Brand.objects.all()

    def set_logo(self, request, obj):
        for attach in request.FILES.getlist('logo'):
            obj.image = attach
            obj.save()

    def set_cover(self, request, obj):
        for attach in request.FILES.getlist('cover'):
            obj.cover = attach
            obj.save()

    def add_seller(self, request, brand):
        try:
            seller = request.user.stores
        except ObjectDoesNotExist:
            seller = None
        brand.seller = seller
        brand.save()

    def create(self, request, *args, **kwargs):
        serializer = AddEditBrandSerializer(data=request.data)
        if serializer.is_valid():
            brand = serializer.save()
            self.add_seller(request, brand)
            brand.save()
            self.set_logo(request, brand)
            self.set_cover(request, brand)
            create_invalidation()
            return Response(
                BrandSerializer(brand).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EditBrand(UpdateAPIView):
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsSuperAdmin,)
    serializer_class = BrandSerializer
    queryset = Brand.objects.all()

    def set_logo(self, request, obj):
        for attach in request.FILES.getlist('logo'):
            obj.image = attach
            obj.save()

    def set_cover(self, request, obj):
        for attach in request.FILES.getlist('cover'):
            obj.cover = attach
            obj.save()

    def get_object(self):
        obj = get_object_or_404(Brand, pk=self.kwargs.get("pk"))
        self.check_object_permissions(self.request, obj)
        return obj

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        print("edit brand")
        print(request.data)
        serializer = EditBrandSerializer(obj, data=request.data)
        if serializer.is_valid():
            brand = serializer.save()
            self.set_logo(request, brand)
            self.set_cover(request, brand)
            create_invalidation()
            return Response(
                BrandSerializer(brand).data,
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DeleteBrands(APIView):
    permission_classes = [IsSuperAdmin]

    def post(self, request):
        brand_ids = self.request.data.get("brand_ids", "")
        if brand_ids != "" and json_list(brand_ids)[0]:
            Brand.objects.filter(pk__in=json_list(brand_ids)[1]).delete()
            create_invalidation()
            return Response({"detail": "Brands deleted"})
        return Response({"detail": "Please select atleast one brand"},
                        status=status.HTTP_400_BAD_REQUEST)


class ChangeBrandStatus(APIView):
    permission_classes = [IsSuperAdmin]

    def post(self, request):
        brand_ids = self.request.data.get("brand_ids", "")
        is_top_brand = self.request.data.get("is_top_brand", False)

        if brand_ids != "" and json_list(brand_ids)[0]:
            Brand.objects.filter(
                pk__in=json_list(brand_ids)[1]
            ).update(is_top_brand=str2bool(is_top_brand))

            status_changed = "Other"
            if str2bool(is_top_brand):
                status_changed = "Top Brand"
            create_invalidation()
            return Response({"detail": f"Successfully added brands to {status_changed}"})
        return Response({"detail": "Please select atleast one brand"},
                        status=status.HTTP_400_BAD_REQUEST)


class CategoryList(ListAPIView):
    permission_classes = [IsSuperAdminOrSeller]
    serializer_class = CategorySerializer

    def get_serializer_context(self):
        return {"user": self.request.user,
                "lang_code": self.request.query_params.get("lang_code", "")}

    def get_queryset(self):
        if self.request.user.is_super_admin:
            qs = Category.objects.filter(
                parent__isnull=True)
        else:
            try:
                store = self.request.user.stores
                qs = Category.objects.filter(
                    parent__isnull=True,
                    pk__in=store.selling_categories.all())
            except ObjectDoesNotExist:
                sub_admins = self.request.user.seller_sub_admins.all()
                if sub_admins.exists():
                    sub_admin = sub_admins.latest('id')
                    store = sub_admin.store
                    qs = Category.objects.filter(
                        parent__isnull=True,
                        pk__in=store.selling_categories.all())
                else:
                    qs = Category.objects.none()
        return qs


class CategoryListUnPaginated(APIView):
    permission_classes = [IsSuperAdminOrSeller]

    def get(self, request):
        lang_code =  request.query_params.get("lang_code", "")

        if self.request.user.is_super_admin:
            qs = Category.objects.filter(
                parent__isnull=True)
        else:
            try:
                store = self.request.user.stores
                qs = Category.objects.filter(
                    parent__isnull=True,
                    pk__in=store.selling_categories.all())
            except ObjectDoesNotExist:
                sub_admins = self.request.user.seller_sub_admins.all()
                if sub_admins.exists():
                    sub_admin = sub_admins.latest('id')
                    store = sub_admin.store
                    qs = Category.objects.filter(
                        parent__isnull=True,
                        pk__in=store.selling_categories.all())
                else:
                    qs = Category.objects.none()
        return Response(CategorySerializer(
            qs, many=True, context={'user': self.request.user,
                                    'lang_code': lang_code}).data)


class SubCategoryList(ListAPIView):
    permission_classes = [IsSuperAdminOrSeller]
    serializer_class = CategorySerializer

    def get_serializer_context(self):
        return {"user": self.request.user,
                "lang_code": self.request.query_params.get("lang_code", "")}

    def get_queryset(self):
        qs = Category.objects.filter(parent__parent__isnull=True).exclude(
            parent__isnull=True
        )
        return qs


class ProductTypeList(ListAPIView):
    permission_classes = [IsSuperAdminOrSeller]
    serializer_class = CategorySerializer

    def get_serializer_context(self):
        return {"user": self.request.user,
                "lang_code": self.request.query_params.get("lang_code", "")}

    def get_queryset(self):
        qs = Category.objects.filter(parent__parent__parent__isnull=True).exclude(
            parent__parent__isnull=True
        )
        return qs


class SubProductTypeList(ListAPIView):
    permission_classes = [IsSuperAdminOrSeller]
    serializer_class = CategorySerializer

    def get_serializer_context(self):
        return {"user": self.request.user,
                "lang_code": self.request.query_params.get("lang_code", "")}

    def get_queryset(self):
        qs = Category.objects.filter(
            parent__parent__parent__parent__isnull=True).exclude(
            parent__parent__parent__isnull=True
        )
        return qs


class CategoryDetail(RetrieveAPIView):
    permission_classes = [IsSuperAdmin]
    serializer_class = CategorySerializer

    def get_object(self):
        obj = get_object_or_404(Category, pk=self.kwargs.get("pk"))
        return obj

    def get_serializer_context(self):
        return {"user": self.request.user}


class CategoryChildren(ListAPIView):
    permission_classes = [IsSuperAdminOrSeller]
    serializer_class = CategoryListSerializer
    http_method_names = [u'get', u'post']

    def _allowed_methods(self):
        return [m.upper() for m in self.http_method_names if hasattr(self, m)]

    def get_serializer_context(self):
        return {"user": self.request.user,
                "lang_code": self.request.query_params.get("lang_code", "")}

    def get_queryset(self):
        category_id = int(self.request.data.get("category_id", 0))
        qs = Category.objects.filter(parent__pk=category_id)
        return qs

    def post(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class AddCategory(CreateAPIView):
    permission_classes = [IsSuperAdmin]
    serializer_class = AddEditCategorySerializer
    queryset = Category.objects.all()

    def set_home_page_thumbnail(self, request, obj):
        for attach in request.FILES.getlist('home_page_thumbnail'):
            obj.home_page_thumbnail = attach
            obj.save()

    def set_home_page_thumbnail_ar(self, request, obj):
        for attach in request.FILES.getlist('home_page_thumbnail_ar'):
            obj.home_page_thumbnail_ar = attach
            obj.save()

    def set_image_1(self, request, obj):
        for attach in request.FILES.getlist('image_1'):
            CategoryMedia.objects.update_or_create(
                type='im1', image_width=764,
                image_height=366, category=obj,
                defaults={'media': attach}
            )

    def set_image_2(self, request, obj):
        for attach in request.FILES.getlist('image_2'):
            CategoryMedia.objects.update_or_create(
                type='im2', image_width=366,
                image_height=366, category=obj,
                defaults={'media': attach}
            )

    def set_image_3(self, request, obj):
        for attach in request.FILES.getlist('image_3'):
            CategoryMedia.objects.update_or_create(
                type='im3', image_width=366,
                image_height=488, category=obj,
                defaults={'media': attach}
            )

    def create(self, request, *args, **kwargs):
        serializer = AddEditCategorySerializer(data=request.data)
        if serializer.is_valid():
            category = serializer.save()
            self.set_image_1(request, category)
            self.set_image_2(request, category)
            self.set_image_3(request, category)
            self.set_home_page_thumbnail(request, category)
            self.set_home_page_thumbnail_ar(request, category)
            create_invalidation()
            return Response(
                CategorySerializer(category).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EditCategory(UpdateAPIView):
    permission_classes = [IsSuperAdmin]
    serializer_class = AddEditCategorySerializer
    queryset = Category.objects.all()

    def set_home_page_thumbnail(self, request, obj):
        for attach in request.FILES.getlist('home_page_thumbnail'):
            obj.home_page_thumbnail = attach
            obj.save()

    def set_home_page_thumbnail_ar(self, request, obj):
        for attach in request.FILES.getlist('home_page_thumbnail_ar'):
            obj.home_page_thumbnail_ar = attach
            obj.save()

    def set_image_1(self, request, obj):
        for attach in request.FILES.getlist('image_1'):
            CategoryMedia.objects.update_or_create(
                type='im1', image_width=764,
                image_height=366, category=obj,
                defaults={'media': attach}
            )

    def set_image_2(self, request, obj):
        for attach in request.FILES.getlist('image_2'):
            CategoryMedia.objects.update_or_create(
                type='im2', image_width=366,
                image_height=366, category=obj,
                defaults={'media': attach}
            )

    def set_image_3(self, request, obj):
        for attach in request.FILES.getlist('image_3'):
            CategoryMedia.objects.update_or_create(
                type='im3', image_width=366,
                image_height=488, category=obj,
                defaults={'media': attach}
            )

    def update(self, request, *args, **kwargs):
        obj = get_object_or_404(Category, pk=kwargs.get("pk"))
        serializer = AddEditCategorySerializer(
            instance=obj, data=request.data)
        if serializer.is_valid():
            category = serializer.save()
            self.set_image_1(request, category)
            self.set_image_2(request, category)
            self.set_image_3(request, category)
            self.set_home_page_thumbnail(request, category)
            self.set_home_page_thumbnail_ar(request, category)
            create_invalidation()
            return Response(
                CategorySerializer(category).data,
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DeleteCategory(DestroyAPIView):
    permission_classes = [IsSuperAdmin]

    def destroy(self, request, *args, **kwargs):
        obj = get_object_or_404(Category, pk=kwargs.get("pk"))
        obj.delete()
        create_invalidation()
        return Response({"detail": "Category deleted successfully"})


class AddSubCategory(CreateAPIView):
    permission_classes = [IsSuperAdmin]
    serializer_class = AddSubCategorySerializer
    queryset = Category.objects.all()

    def create(self, request, *args, **kwargs):
        parent = get_object_or_404(Category, pk=kwargs.get("pk"))
        serializer = AddSubCategorySerializer(data=request.data)
        if serializer.is_valid():
            category = serializer.save()
            category.parent = parent
            category.save()
            create_invalidation()
            return Response(
                CategorySerializer(category).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RenameSubCategory(UpdateAPIView):
    permission_classes = [IsSuperAdmin]
    serializer_class = AddSubCategorySerializer
    queryset = Category.objects.all()

    def update(self, request, *args, **kwargs):
        category = get_object_or_404(Category, pk=kwargs.get("pk"))
        serializer = AddSubCategorySerializer(
            instance=category, data=request.data)
        if serializer.is_valid():
            category = serializer.save()
            create_invalidation()
            return Response(
                CategorySerializer(category).data,
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChangeCatStatus(APIView):
    permission_classes = [IsSuperAdmin]

    def post(self, request, pk):
        category = get_object_or_404(Category, pk=pk)
        cat_status = self.request.data.get("status", "")

        if status != "":
            category.status = cat_status
            category.save()
            descendants = Category.objects.descendants(
                category
            )
            descendants.update(
                status=cat_status
            )
            create_invalidation()
            return Response(
                CategorySerializer(category).data,
                status=status.HTTP_200_OK
            )
        return Response(
            {"error": "Status cant be empty"},
            status=status.HTTP_400_BAD_REQUEST)


class ProductList(ListAPIView):
    permission_classes = [IsSuperAdminOrSeller]
    serializer_class = ProductListSerializer
    http_method_names = [u'get', u'post']

    def _allowed_methods(self):
        return [m.upper() for m in self.http_method_names if hasattr(self, m)]

    def search(self, qs, search_string):
        for qstring in search_string.split(" "):
            qs = qs.filter(
                Q(name__icontains=qstring)
                | Q(nameAR__icontains=qstring)
                | Q(store__name__icontains=qstring)
                | Q(store__nameAR__icontains=qstring)
                | Q(brand__name__icontains=qstring)
                | Q(brand__nameAR__icontains=qstring)
                | Q(category__name__icontains=qstring)
                | Q(category__nameAR__icontains=qstring)
            ).order_by('id').distinct()
        return qs

    def get_serializer_context(self):
        return {"user": self.request.user,
                "lang_code": self.request.query_params.get("lang_code", "")}

    def get_queryset(self):
        search_string = self.request.query_params.get("search_string", "")
        product_status = self.request.query_params.get("product_status", "")
        brand_id = self.request.query_params.get("brand_id", "")
        sort_by = self.request.query_params.get("sort_by", "")
        seller_ids = self.request.data.get("seller_ids", "")
        category_ids = self.request.data.get("category_ids", "")
        days = self.request.data.get("days", None)
        from_date = self.request.data.get("from_date", None)
        to_date = self.request.data.get("to_date", None)
        brand_ids = self.request.data.get("brand_ids", None)
        is_for_child = self.request.data.get("is_for_child", False)

        print("product_list_test")
        if self.request.user.is_seller:
            if str2bool(is_for_child):
                sub_admins = self.request.user.seller_sub_admins.all()
                if sub_admins.exists():
                    sub_admin = sub_admins.latest('id')
                    qs = EcommProduct.objects.filter(
                        store=sub_admin.store,
                        isHiddenFromOrder=False).annotate(
                        variant_count=Count('productVariantValue', distinct=True)).exclude(
                        Q(variant_count=0, parent__isnull=False) |
                        Q(parent=None, children__isnull=False, important=False) |
                        Q(parent__important=True, important=False))
                else:
                    qs = EcommProduct.objects.filter(
                        store__member=self.request.user,
                        isHiddenFromOrder=False).annotate(
                        variant_count=Count('productVariantValue', distinct=True)).exclude(
                        Q(variant_count=0, parent__isnull=False) |
                        Q(parent=None, children__isnull=False, important=False) |
                        Q(parent__important=True, important=False))

            else:
                sub_admins = self.request.user.seller_sub_admins.all()
                if sub_admins.exists():
                    sub_admin = sub_admins.latest('id')
                    qs = EcommProduct.objects.filter(
                        parent__isnull=True,
                        store=sub_admin.store)
                else:
                    qs = EcommProduct.objects.filter(
                        parent__isnull=True,
                        store__member=self.request.user)
        else:
            if str2bool(is_for_child):
                qs = EcommProduct.objects.filter(
                    isHiddenFromOrder=False).annotate(
                    variant_count=Count('productVariantValue', distinct=True)).exclude(
                        Q(variant_count=0, parent__isnull=False) |
                        Q(parent=None, children__isnull=False, important=False) |
                        Q(parent__important=True, important=False))
                # qs = qs.filter(parent__isnull=False)
            else:
                qs = EcommProduct.objects.filter(
                    isHiddenFromOrder=False, parent__isnull=True)

        if brand_id != "" and brand_id != 0:
            if self.request.user.is_seller:
                qs = qs.filter(
                    store__member=self.request.user,
                    brand__pk=brand_id).distinct()
            else:
                qs = qs(
                    brand__pk=brand_id).distinct()

        if brand_ids != "" and json_list(brand_ids)[0]:
            qs = qs.filter(
                brand__pk__in=json_list(brand_ids)[1]).distinct()

        if seller_ids != "" and json_list(seller_ids)[0]:
            if len(json_list(seller_ids)[1]) == 1:
                seller_id = json_list(seller_ids)[1][0]
                try:
                    seller = Store.objects.get(
                        pk=seller_id
                    )
                except Store.DoesNotExist:
                    seller = None
                if seller.name != "Becon (All products)":
                    qs = qs.filter(
                        store__in=json_list(seller_ids)[1]
                    ).distinct()
            else:
                qs = qs.filter(
                    store__in=json_list(seller_ids)[1]
                ).distinct()

        if category_ids != "" and json_list(category_ids)[0]:
            descendants_all = []
            for cat_id in json_list(category_ids)[1]:
                descendants = Category.objects.descendants(
                    get_object_or_404(Category, pk=cat_id)).values_list(
                    'id', flat=True).distinct()
                for descendant in descendants:
                    if descendant not in descendants_all:
                        descendants_all.append(descendant)

            qs = qs.filter(
                category__pk__in=descendants_all
            ).distinct()

        if days == 0 or days:
            date_selected = now() - timedelta(days=int(days))
            qs = qs.filter(created_at__date__gte=date_selected.date())

        if from_date and to_date:
            qs = qs.filter(
                created_at__date__gte=from_date,
                created_at__date__lte=to_date)

        if product_status == "InReview":
            qs = qs.filter(status='INR')
        if product_status == "Active":
            qs = qs.filter(status='AC')
        if product_status == "Draft":
            qs = qs.filter(status='DR')
        if product_status == "Declined":
            qs = qs.filter(status='DE')
        if search_string != "":
            qs = self.search(qs, search_string)

        if sort_by != "":
            if sort_by == "PRODUCTATOZ":
                qs = qs.order_by('name')
            if sort_by == "PRODUCTZTOA":
                qs = qs.order_by('-name')

            if sort_by == "SELLERZTOA":
                qs = qs.order_by('-store__name')
            if sort_by == "SELLERATOZ":
                qs = qs.order_by('store__name')

            if sort_by == "PRICEHIGHTOLOW":
                qs = qs.order_by('-base_price')
            if sort_by == "PRICELOWTOHIGH":
                qs = qs.order_by('base_price')

            if sort_by == "INVHIGHTOLOW":
                qs = sorted(
                    qs, key=lambda p: p.get_inventory_avail_count(),
                    reverse=True)
            if sort_by == "INVLOWTOHIGH":
                qs = sorted(
                    qs, key=lambda p: p.get_inventory_avail_count(),
                    reverse=False)

            if sort_by == "MODNEWFIRST":
                qs = qs.order_by('-updated_at')
            if sort_by == "MODOLDFIRST":
                qs = qs.order_by('updated_at')

            if sort_by == "ADDNEWFIRST":
                qs = qs.order_by('-created_at')
            if sort_by == "ADDOLDFIRST":
                qs = qs.order_by('created_at')

        return qs

    def post(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class ProdListCollection(APIView):
    permission_classes = [IsSuperAdminOrSeller]

    def search(self, qs, search_string):
        for qstring in search_string.split(" "):
            qs = qs.filter(
                Q(name__icontains=qstring)
                | Q(nameAR__icontains=qstring)
                | Q(store__name__icontains=qstring)
                | Q(store__nameAR__icontains=qstring)
                | Q(brand__name__icontains=qstring)
                | Q(brand__nameAR__icontains=qstring)
                | Q(category__name__icontains=qstring)
                | Q(category__nameAR__icontains=qstring)
            ).order_by('id').distinct()
        return qs

    def post(self, request, pk):
        collection = get_object_or_404(ProductCollection, pk=pk)
        search_string = self.request.data.get("search_string", "")
        qs = collection.products.all()

        if search_string != "":
            qs = self.search(qs, search_string)
        return Response(
            ProductMinNewSerializer(
                qs, many=True,
            ).data
        )


class ProdListSeller(APIView):
    permission_classes = [IsSuperAdminOrSeller]

    def search(self, qs, search_string):
        for qstring in search_string.split(" "):
            qs = qs.filter(
                Q(name__icontains=qstring)
                | Q(nameAR__icontains=qstring)
                | Q(store__name__icontains=qstring)
                | Q(store__nameAR__icontains=qstring)
                | Q(brand__name__icontains=qstring)
                | Q(brand__nameAR__icontains=qstring)
                | Q(category__name__icontains=qstring)
                | Q(category__nameAR__icontains=qstring)
            ).order_by('id').distinct()
        return qs

    def post(self, request, pk):
        seller = get_object_or_404(Store, pk=pk)
        search_string = self.request.data.get("search_string", "")
        if self.request.user.is_seller:
            sub_admins = self.request.user.seller_sub_admins.all()
            if sub_admins.exists():
                sub_admin = sub_admins.latest('id')
                qs = EcommProduct.objects.filter(
                    status='AC',
                    store=sub_admin.store,
                    isHiddenFromOrder=False).annotate(
                    variant_count=Count('productVariantValue', distinct=True)).exclude(
                    Q(variant_count=0, parent__isnull=False) |
                    Q(parent=None, children__isnull=False, important=False) |
                    Q(parent__important=True, important=False))
            else:
                qs = EcommProduct.objects.filter(
                    status='AC',
                    store__member=self.request.user,
                    isHiddenFromOrder=False).annotate(
                    variant_count=Count('productVariantValue', distinct=True)).exclude(
                    Q(variant_count=0, parent__isnull=False) |
                    Q(parent=None, children__isnull=False, important=False) |
                    Q(parent__important=True, important=False))
        else:
            if seller.name == "Becon (All products)":
                qs = EcommProduct.objects.filter(
                    status='AC',
                    isHiddenFromOrder=False).annotate(
                    variant_count=Count('productVariantValue', distinct=True)).exclude(
                    Q(variant_count=0, parent__isnull=False) |
                    Q(parent=None, children__isnull=False, important=False) |
                    Q(parent__important=True, important=False))

            else:
                qs = EcommProduct.objects.filter(
                    status='AC',
                    store=seller,
                    isHiddenFromOrder=False).annotate(
                    variant_count=Count('productVariantValue', distinct=True)).exclude(
                    Q(variant_count=0, parent__isnull=False) |
                    Q(parent=None, children__isnull=False, important=False) |
                    Q(parent__important=True, important=False))

        if search_string != "":
            qs = self.search(qs, search_string)

        return Response(
            ProductMinNewSerializer(
                qs, many=True,
            ).data
        )


class ChildProductList(ListAPIView):
    permission_classes = [IsSuperAdminOrSeller]
    serializer_class = ProductListSerializer
    http_method_names = [u'get', u'post']

    def _allowed_methods(self):
        return [m.upper() for m in self.http_method_names if hasattr(self, m)]

    def search(self, qs, search_string):
        for qstring in search_string.split(" "):
            qs = qs.filter(
                Q(name__icontains=qstring)
                | Q(nameAR__icontains=qstring)
                | Q(store__name__icontains=qstring)
                | Q(store__nameAR__icontains=qstring)
                | Q(brand__name__icontains=qstring)
                | Q(brand__nameAR__icontains=qstring)
                | Q(category__name__icontains=qstring)
                | Q(category__nameAR__icontains=qstring)
            ).order_by('id').distinct()
        return qs

    def get_serializer_context(self):
        return {"user": self.request.user,
                "lang_code": self.request.query_params.get("lang_code", "")}

    def get_queryset(self):
        search_string = self.request.query_params.get("search_string", "")
        product_status = self.request.query_params.get("product_status", "")
        brand_id = self.request.query_params.get("brand_id", "")
        sort_by = self.request.query_params.get("sort_by", "")
        seller_ids = self.request.data.get("seller_ids", "")
        category_ids = self.request.data.get("category_ids", "")
        days = self.request.data.get("days", None)
        from_date = self.request.data.get("from_date", None)
        to_date = self.request.data.get("to_date", None)
        brand_ids = self.request.data.get("brand_ids", None)

        if self.request.user.is_seller:
            qs = EcommProduct.objects.filter(
                parent__isnull=False, store__member=self.request.user)
        else:
            qs = EcommProduct.objects.filter(parent__isnull=False)

        if brand_id != "" and brand_id != 0:
            if self.request.user.is_seller:
                qs = EcommProduct.objects.filter(
                    store__member=self.request.user,
                    brand__pk=brand_id).distinct()
            else:
                qs = EcommProduct.objects.filter(
                    brand__pk=brand_id).distinct()

        if brand_ids != "" and json_list(brand_ids)[0]:
            qs = qs.filter(
                brand__pk__in=json_list(brand_ids)[1]).distinct()

        if seller_ids != "" and json_list(seller_ids)[0]:
            qs = qs.filter(
                store__in=json_list(seller_ids)[1]
            ).distinct()

        if category_ids != "" and json_list(category_ids)[0]:
            descendants_all = []
            for cat_id in json_list(category_ids)[1]:
                descendants = Category.objects.descendants(
                    get_object_or_404(Category, pk=cat_id)).values_list(
                    'id', flat=True).distinct()
                for descendant in descendants:
                    if descendant not in descendants_all:
                        descendants_all.append(descendant)

            qs = qs.filter(
                category__pk__in=descendants_all
            ).distinct()

        if days == 0 or days:
            date_selected = now() - timedelta(days=int(days))
            qs = qs.filter(created_at__date__gte=date_selected.date())

        if from_date and to_date:
            qs = qs.filter(
                created_at__date__gte=from_date,
                created_at__date__lte=to_date)

        if product_status == "InReview":
            qs = qs.filter(status='INR')
        if product_status == "Active":
            qs = qs.filter(status='AC')
        if product_status == "Draft":
            qs = qs.filter(status='DR')
        if product_status == "Declined":
            qs = qs.filter(status='DE')
        if search_string != "":
            qs = self.search(qs, search_string)

        if sort_by != "":
            if sort_by == "PRODUCTATOZ":
                qs = qs.order_by('name')
            if sort_by == "PRODUCTZTOA":
                qs = qs.order_by('-name')

            if sort_by == "SELLERZTOA":
                qs = qs.order_by('-store__name')
            if sort_by == "SELLERATOZ":
                qs = qs.order_by('store__name')

            if sort_by == "PRICEHIGHTOLOW":
                qs = qs.order_by('-base_price')
            if sort_by == "PRICELOWTOHIGH":
                qs = qs.order_by('base_price')

            if sort_by == "INVHIGHTOLOW":
                qs = sorted(
                    qs, key=lambda p: p.get_inventory_avail_count(),
                    reverse=True)
            if sort_by == "INVLOWTOHIGH":
                qs = sorted(
                    qs, key=lambda p: p.get_inventory_avail_count(),
                    reverse=False)

            if sort_by == "MODNEWFIRST":
                qs = qs.order_by('-updated_at')
            if sort_by == "MODOLDFIRST":
                qs = qs.order_by('updated_at')

            if sort_by == "ADDNEWFIRST":
                qs = qs.order_by('-created_at')
            if sort_by == "ADDOLDFIRST":
                qs = qs.order_by('created_at')

        return qs

    def post(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class ChangeProductStatus(APIView):
    permission_classes = [IsSuperAdminOrSeller]

    def post(self, request):
        product_ids = request.data.get("product_ids", "")
        product_status = request.data.get("product_status", "")
        delete_all = request.data.get("delete_all", False)

        if product_ids != "" and json_list(product_ids)[0]:
            if product_status != "":
                for prod in EcommProduct.objects.filter(
                    parent__pk__in=json_list(product_ids)[1]
                ):
                    prod.status = product_status
                    prod.save()

                for prod in EcommProduct.objects.filter(
                    pk__in=json_list(product_ids)[1]
                ):
                    prod.status = product_status
                    prod.save()

                if product_status == "AC":
                    seller_ids = EcommProduct.objects.filter(
                        pk__in=json_list(product_ids)[1]
                    ).values_list('store_id', flat=True)
                    for seller_id in seller_ids:
                        prod_ids = EcommProduct.objects.filter(
                            pk__in=json_list(product_ids)[1],
                            store_id=seller_id
                        ).values_list('id', flat=True)

                        # send_prod_approve_email(list(prod_ids), seller_id)

                create_invalidation()
                return Response({"detail": f"Successfully added products to {product_status}"})
            elif str2bool(delete_all):
                # EcommProduct.objects.filter(
                #     pk__in=json_list(product_ids)[1],
                # ).delete()
                EcommProduct.objects.filter(
                    pk__in=json_list(product_ids)[1],
                    orderProducts__isnull=True
                ).delete()
                EcommProduct.objects.filter(
                    pk__in=json_list(product_ids)[1],
                    orderProducts__isnull=False
                ).update(isHiddenFromOrder=True)

                create_invalidation()
                return Response({"detail": "Successfully deleted products"})
            return Response({"error": "Please select product status or choose delete_all"},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({"error": "Please select atleast one product"},
                        status=status.HTTP_400_BAD_REQUEST)


class ProductDetail(RetrieveAPIView):
    permission_classes = [IsSuperAdminOrObjectSeller]
    serializer_class = ProductDetailSerializer

    def get_object(self):
        obj = get_object_or_404(EcommProduct, pk=self.kwargs.get("pk"))
        return obj

    def get_serializer_context(self):
        return {"user": self.request.user}