import os
import sys
from django.db.models import Q, Count, F, Sum, Case, When
from rest_framework import viewsets, status
from rest_framework.generics import CreateAPIView, ListAPIView, UpdateAPIView, get_object_or_404, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from app.authentication.models import Member
from app.authentication.models.extensions import Rank
from app.authentication.permissions import IsSuperAdmin, IsSuperAdminOrSeller, IsSuperAdminOrObjectSeller
from app.authentication.serializers import GetSellerSerializer, MemberSerializer, SellerSerializer, \
    SellerDetailSerializer, SellerListSerializer, InventoryListSerializer, MemberEcommEditSerializer, \
    EditSellerSerializer, EditSellerBeconSerializer, SellerListCollectionSerializer
from app.ecommnotification.zappa_tasks import send_product_to_category_push, send_new_brand_push
from app.order.models import Order
from app.product.models import ProductCollection, Brand
from app.product.utils import json_list
from app.store.models import Store, Inventory, InventoryProduct, Banner, TopDealsBanner, HomePageItems
from app.store.serializers import AddBannerSerializer, BannerDetailSerializer, BannerListSerializer, \
    EditBannerSerializer, EditHomePageBannerSerializer, AddHomePageBannerSerializer, AddTopDealsBannerSerializer, \
    EditTopDealsBannerSerializer, TopDealsBannerDetailSerializer, TopDealsBannerListSerializer, \
    AddNewArrivalBannerSerializer, EditNewArrivalBannerSerializer
from app.store.zappa_tasks import assign_seller_page_banner_card_small, assign_seller_page_categories, \
    assign_seller_page_all_prods, assign_home_page_banner_card_small, assign_home_page_carousal_new_arrivals, \
    assign_top_deals_page_banner_card_small, assign_collections_to_home_page, assign_seller_page_banner_card_large, \
    assign_home_page_banner_card_rearranged, resize_seller_logo
from app.utilities.cache_invalidation import create_invalidation
from app.utilities.helpers import str2bool, report_to_developer
from app.utilities.utils import is_email_valid


class AddSeller(CreateAPIView):
    permission_classes = [IsSuperAdmin]
    serializer_class = GetSellerSerializer
    queryset = Member.objects.all()

    def set_logo(self, request, obj):
        for attach in request.FILES.getlist('seller_logo'):
            obj.image = attach
            obj.save()

    def create(self, request, *args, **kwargs):
        serializer = MemberSerializer(data=request.data)
        if serializer.is_valid():
            member = serializer.save()
            seller_serializer = SellerSerializer(
                data=request.data, context=member)
            try:
                if seller_serializer.is_valid():
                    seller = seller_serializer.save()
                    self.set_logo(request, seller)
                    resize_seller_logo(seller.id)
                    member.is_seller = True
                    member.has_full_access = True
                    member.designation = "Owner"
                    password = "Becon" + "_" + str(member.pk) + "@123"
                    member.set_password(password)
                    member.save()
                    create_invalidation()
                    return Response(
                        SellerDetailSerializer(seller).data,
                        status=status.HTTP_201_CREATED
                    )
                member.delete()
                return Response(seller_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                member.delete()
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                report_to_developer("Issue in add seller", str(e)
                                    + "at %s, line number %s" % (fname, exc_tb.tb_lineno))
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EditSeller(UpdateAPIView):
    permission_classes = (IsSuperAdminOrObjectSeller,)
    serializer_class = GetSellerSerializer
    queryset = Store.objects.all()

    def set_logo(self, request, obj):
        for attach in request.FILES.getlist('seller_logo'):
            obj.image = attach
            obj.save()

    def get_object(self):
        obj = get_object_or_404(Store, pk=self.kwargs.get("pk"))
        self.check_object_permissions(self.request, obj)
        return obj

    def update(self, request, *args, **kwargs):
        try:
            obj = self.get_object()
            mem_serializer = MemberEcommEditSerializer(
                obj.member, data=request.data)
            if mem_serializer.is_valid():
                member = mem_serializer.save()
                if obj.name == "Becon":
                    serializer = EditSellerBeconSerializer(obj, data=request.data)
                else:
                    serializer = EditSellerSerializer(obj, data=request.data)
                if serializer.is_valid():
                    seller = serializer.save()
                    self.set_logo(request, seller)
                    resize_seller_logo(seller.id)
                    create_invalidation()
                    return Response(
                        SellerDetailSerializer(seller).data,
                        status=status.HTTP_200_OK
                    )
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            return Response(mem_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            report_to_developer("Issue in edit seller", str(e)
                                + "at %s, line number %s" % (fname, exc_tb.tb_lineno))
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class SellerList(ListAPIView):
    permission_classes = [IsSuperAdmin]
    serializer_class = SellerListSerializer
    queryset = Store.objects.all()
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
        seller_status = self.request.query_params.get("seller_status", "")
        seller_type = self.request.query_params.get("seller_type", "")
        category_id = self.request.query_params.get("category_id", "")

        sort_by = self.request.query_params.get("sort_by", "")
        seller_ids = self.request.data.get("seller_ids", "")

        qs = Store.objects.all().exclude(
            name='Delicon'
        ).order_by('-created_at')

        if category_id != "":
            qs = qs.filter(
                selling_categories__pk=int(category_id)
            ).distinct()

        if seller_ids != "" and json_list(seller_ids)[0]:
            qs = qs.filter(
                pk__in=json_list(seller_ids)[1]
            ).distinct()

        if seller_type == "CON":
            qs = qs.filter(type='CON')
        if seller_type == "NCON":
            qs = qs.filter(type='NCON')
        if seller_type == "NCONP":
            qs = qs.filter(type='NCONP')

        if seller_status == "IN":
            qs = qs.filter(status='IN')
        if seller_status == "AC":
            qs = qs.filter(status='AC')
        if search_string != "":
            qs = self.search(qs, search_string)

        if sort_by != "":
            if sort_by == "ATOZ":
                qs = qs.order_by('name')
            if sort_by == "ZTOA":
                qs = qs.order_by('-name')

            if sort_by == "prod_ascending":
                qs = qs.annotate(prod_count=Count(
                    F('products')
                )).order_by('prod_count')
            if sort_by == "prod_descending":
                qs = qs.annotate(prod_count=Count(
                    F('products')
                )).order_by('-prod_count')

            if sort_by == "sales_low_to_high":
                qs = sorted(qs,
                            key=lambda t: t.get_sales_float(),
                            reverse=False)
            if sort_by == "sales_high_to_low":
                qs = sorted(qs,
                            key=lambda t: t.get_sales_float(),
                            reverse=True)

            if sort_by == "earnings_low_to_high":
                qs = sorted(qs,
                            key=lambda t: t.get_earnings(),
                            reverse=False)
            if sort_by == "earnings_high_to_low":
                qs = sorted(qs,
                            key=lambda t: t.get_earnings(),
                            reverse=True)

        return qs

    def post(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class SellerListForCollection(ListAPIView):
    permission_classes = [IsSuperAdmin]
    serializer_class = SellerListCollectionSerializer
    queryset = Store.objects.all()
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
        seller_status = self.request.query_params.get("seller_status", "")
        seller_type = self.request.query_params.get("seller_type", "")
        category_id = self.request.query_params.get("category_id", "")

        sort_by = self.request.query_params.get("sort_by", "")
        seller_ids = self.request.data.get("seller_ids", "")

        qs = Store.objects.all().exclude(
            name='Delicon'
        ).order_by('-created_at')

        if category_id != "":
            qs = qs.filter(
                selling_categories__pk=int(category_id)
            ).distinct()

        if seller_ids != "" and json_list(seller_ids)[0]:
            qs = qs.filter(
                pk__in=json_list(seller_ids)[1]
            ).distinct()

        if seller_type == "CON":
            qs = qs.filter(type='CON')
        if seller_type == "NCON":
            qs = qs.filter(type='NCON')
        if seller_type == "NCONP":
            qs = qs.filter(type='NCONP')

        if seller_status == "IN":
            qs = qs.filter(status='IN')
        if seller_status == "AC":
            qs = qs.filter(status='AC')
        if search_string != "":
            qs = self.search(qs, search_string)

        if sort_by != "":
            if sort_by == "ATOZ":
                qs = qs.order_by('name')
            if sort_by == "ZTOA":
                qs = qs.order_by('-name')

            if sort_by == "prod_ascending":
                qs = qs.annotate(prod_count=Count(
                    F('products')
                )).order_by('prod_count')
            if sort_by == "prod_descending":
                qs = qs.annotate(prod_count=Count(
                    F('products')
                )).order_by('-prod_count')

            if sort_by == "sales_low_to_high":
                qs = sorted(qs,
                            key=lambda t: t.get_sales_float(),
                            reverse=False)
            if sort_by == "sales_high_to_low":
                qs = sorted(qs,
                            key=lambda t: t.get_sales_float(),
                            reverse=True)

            if sort_by == "earnings_low_to_high":
                qs = sorted(qs,
                            key=lambda t: t.get_earnings(),
                            reverse=False)
            if sort_by == "earnings_high_to_low":
                qs = sorted(qs,
                            key=lambda t: t.get_earnings(),
                            reverse=True)

        return qs

    def post(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class SellerDetails(RetrieveAPIView):
    permission_classes = [IsSuperAdminOrObjectSeller]
    serializer_class = SellerDetailSerializer

    def get_object(self):
        obj = get_object_or_404(Store, pk=self.kwargs.get("pk"))
        return obj

    def get_serializer_context(self):
        return {"user": self.request.user}


class ChangeSellersStatus(APIView):
    permission_classes = [IsSuperAdmin]

    def post(self, request):
        seller_ids = request.data.get("seller_ids", "")
        seller_status = request.data.get("seller_status", "")
        delete_all = request.data.get("delete_all", False)

        if seller_ids != "" and json_list(seller_ids)[0]:
            if seller_status != "":
                Store.objects.filter(
                    pk__in=json_list(seller_ids)[1]
                ).update(status=seller_status)
                create_invalidation()
                return Response({"detail": f"Successfully added sellers to {seller_status}"})
            elif str2bool(delete_all):
                member_ids = Store.objects.filter(
                    pk__in=json_list(seller_ids)[1]
                ).values_list('member_id', flat=True)
                # print(Rank.objects.filter(member__pk__in=[2]))
                # Rank.objects.filter(member__pk__in=[2]).delete()
                Member.objects.filter(
                    pk__in=member_ids
                ).delete()
                Store.objects.filter(
                    pk__in=json_list(seller_ids)[1]
                ).delete()
                create_invalidation()
                return Response({"detail": "Successfully deleted sellers"})
            return Response({"error": "Please select seller status or choose delete_all"},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({"error": "Please select atleast one seller"},
                        status=status.HTTP_400_BAD_REQUEST)


class InventoryList(ListAPIView):
    permission_classes = [IsSuperAdminOrSeller]
    serializer_class = InventoryListSerializer
    queryset = InventoryProduct.objects.all()
    http_method_names = [u'get', u'post']

    def _allowed_methods(self):
        return [m.upper() for m in self.http_method_names if hasattr(self, m)]

    def search(self, qs, search_string):
        for qstring in search_string.split(" "):
            qs = qs.filter(
                Q(product__name__icontains=qstring)
                | Q(product__nameAR__icontains=qstring)
            ).order_by('id').distinct()
        return qs

    def get_serializer_context(self):
        return {"user": self.request.user,
                "lang_code": self.request.query_params.get("lang_code", "")}

    def get_queryset(self):
        search_string = self.request.query_params.get("search_string", "")
        stock_status = self.request.query_params.get("stock_status", "")

        sort_by = self.request.query_params.get("sort_by", "")
        seller_ids = self.request.data.get("seller_ids", "")
        brand_ids = self.request.data.get("brand_ids", "")

        if self.request.user.is_seller:
            sub_admins = self.request.user.seller_sub_admins.all()
            if sub_admins.exists():
                sub_admin = sub_admins.latest('id')
                qs = InventoryProduct.objects.filter(
                    inventory__store=sub_admin.store
                ).annotate(variant_count=Count('product__productVariantValue', distinct=True)).exclude(
                    Q(variant_count=0, product__parent__isnull=False) |
                    Q(product__parent=None, product__children__isnull=False))
            else:
                qs = InventoryProduct.objects.filter(
                    inventory__store__member=self.request.user,
                ).annotate(variant_count=Count('product__productVariantValue', distinct=True)).exclude(
                    Q(variant_count=0, product__parent__isnull=False) |
                    Q(product__parent=None, product__children__isnull=False))
        else:
            qs = InventoryProduct.objects.all().annotate(
                variant_count=Count(
                    'product__productVariantValue', distinct=True)).exclude(
                Q(variant_count=0, product__parent__isnull=False) |
                Q(product__parent=None, product__children__isnull=False))

        if seller_ids != "" and json_list(seller_ids)[0]:
            qs = qs.filter(
                product__store__pk__in=json_list(seller_ids)[1]
            ).distinct()

        if brand_ids != "" and json_list(brand_ids)[0]:
            qs = qs.filter(
                product__brand__pk__in=
                json_list(brand_ids)[1]
            ).distinct()

        if search_string != "":
            qs = self.search(qs, search_string)

        if stock_status == "INS":
            qs = qs.filter(quantity__gt=0)
        if stock_status == "OUS":
            qs = qs.filter(quantity=0)

        if sort_by != "":
            if sort_by == "PRODNAMEATOZ":
                qs = qs.order_by('product__name')
            if sort_by == "PRODNAMEZTOA":
                qs = qs.order_by('-product__name')

            if sort_by == "SELLERNAMEATOZ":
                qs = qs.order_by('product__store__name')
            if sort_by == "SELLERNAMEZTOA":
                qs = qs.order_by('-product__store__name')

            if sort_by == "BRANDNAMEATOZ":
                qs = qs.order_by('product__brand__name')
            if sort_by == "BRANDNAMEZTOA":
                qs = qs.order_by('-product__brand__namee')

            if sort_by == "avail_high_to_low":
                qs = qs.order_by('-quantity')
            if sort_by == "avail_low_to_high":
                qs = qs.order_by('quantity')

        return qs

    def post(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class InventoryQtyUpdate(APIView):
    permission_classes = [IsSuperAdminOrObjectSeller]

    def post(self, request):
        inv_prod_ids = request.data.get("inv_prod_ids", "")
        add_quantity = request.data.get("add_quantity", "")
        set_quantity = request.data.get("set_quantity", "")

        if inv_prod_ids != "" and json_list(inv_prod_ids)[0]:
            if add_quantity != "":
                InventoryProduct.objects.filter(
                    pk__in=json_list(inv_prod_ids)[1]
                ).update(quantity=F('quantity')+add_quantity)

            if set_quantity != "":
                InventoryProduct.objects.filter(
                    pk__in=json_list(inv_prod_ids)[1]
                ).update(quantity=set_quantity)

        if add_quantity == "" and set_quantity == "":
            return Response({"error": "Please select add or set quantity"},
                            status=status.HTTP_400_BAD_REQUEST)

        if add_quantity != "" and set_quantity != "":
            return Response({"error": "Only one of add or set quantity should be selected"},
                            status=status.HTTP_400_BAD_REQUEST)
        create_invalidation()
        return Response({"detail": "Quantity updated"},
                        status=status.HTTP_200_OK)


class ParentBannerList(ListAPIView):
    permission_classes = [IsSuperAdminOrSeller]
    serializer_class = BannerListSerializer
    queryset = Banner.objects.all()

    def get_serializer_context(self):
        return {"user": self.request.user,
                "lang_code": self.request.query_params.get("lang_code", "")}

    def get_serializer_class(self):
        top_deals = self.request.query_params.get("top_deals", "")
        if str2bool(top_deals):
            return TopDealsBannerListSerializer
        return BannerListSerializer

    def get_queryset(self):
        top_deals = self.request.query_params.get("top_deals", "")

        if top_deals != "" and str2bool(top_deals):
            qs = TopDealsBanner.objects.filter(
                parent=None).order_by('-created_at').distinct()

            if self.request.user.is_seller:
                qs = TopDealsBanner.objects.filter(
                    parent=None,
                    seller__member=self.request.user).order_by(
                    '-created_at').distinct()
        else:
            qs = Banner.objects.filter(
                is_for_homepage=True,
                parent=None).order_by(
                Case(When(name='New Arrivals', then=0), default=1)).distinct()

            if self.request.user.is_seller:
                qs = Banner.objects.filter(
                    is_for_homepage=True,
                    parent=None,
                    seller__member=self.request.user).order_by(
                    Case(When(name='New Arrivals', then=0), default=1)).distinct()

        return qs

    def post(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class ChildBannerList(ListAPIView):
    permission_classes = [IsSuperAdminOrSeller]
    serializer_class = BannerListSerializer
    queryset = Banner.objects.all()

    def get_serializer_context(self):
        return {"user": self.request.user,
                "lang_code": self.request.query_params.get("lang_code", "")}

    def get_queryset(self):
        parent_id = self.request.query_params.get("parent_id", "")

        qs = Banner.objects.filter(
            parent__pk=parent_id).order_by('-created_at').distinct()
        if self.request.user.is_seller:
            qs = Banner.objects.filter(
                parent__pk=parent_id,
                seller__member=self.request.user).order_by(
                '-created_at').distinct()
            return qs
        return qs

    def post(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class AddSellerBanner(CreateAPIView):
    permission_classes = [IsSuperAdminOrSeller]
    serializer_class = AddBannerSerializer
    queryset = Banner.objects.all()

    def set_banner_eng(self, request, obj):
        for attach in request.FILES.getlist('banner_image'):
            obj.banner_image = attach
            obj.save()

    def set_banner_ar(self, request, obj):
        for attach in request.FILES.getlist('banner_image_ar'):
            obj.banner_image_ar = attach
            obj.save()

    def set_seller_page_items(self, request, seller):
        assign_seller_page_banner_card_small(seller)
        assign_seller_page_banner_card_large(seller)
        assign_seller_page_categories(seller)
        assign_seller_page_all_prods(seller)

    def create(self, request, *args, **kwargs):
        serializer = AddBannerSerializer(data=request.data)
        if serializer.is_valid():
            banner = serializer.save()
            banner.is_for_seller = True
            banner.save()
            self.set_banner_eng(request, banner)
            self.set_banner_ar(request, banner)
            self.set_seller_page_items(
                request, banner.seller)
            create_invalidation()
            return Response(
                BannerDetailSerializer(banner).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EditBanner(UpdateAPIView):
    permission_classes = [IsSuperAdminOrSeller]
    serializer_class = AddBannerSerializer
    queryset = Banner.objects.all()

    def set_banner_eng(self, request, obj):
        for attach in request.FILES.getlist('banner_image'):
            obj.banner_image = attach
            obj.save()

    def set_banner_ar(self, request, obj):
        for attach in request.FILES.getlist('banner_image_ar'):
            obj.banner_image_ar = attach
            obj.save()

    def set_seller_page_items(self, request, seller):
        assign_seller_page_banner_card_small(seller)
        assign_seller_page_banner_card_large(seller)
        assign_seller_page_categories(seller)
        assign_seller_page_all_prods(seller)

    def update(self, request, *args, **kwargs):
        obj = get_object_or_404(Banner, pk=kwargs.get("pk"))
        serializer = EditBannerSerializer(
            instance=obj, data=request.data)
        if serializer.is_valid():
            banner = serializer.save()
            banner.save()
            self.set_banner_eng(request, banner)
            self.set_banner_ar(request, banner)
            self.set_seller_page_items(
                request, banner.seller)
            create_invalidation()
            return Response(
                BannerDetailSerializer(banner).data,
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BannerDetail(RetrieveAPIView):
    permission_classes = [IsSuperAdminOrSeller]
    serializer_class = BannerDetailSerializer

    def get_object(self):
        obj = get_object_or_404(Banner, pk=self.kwargs.get("pk"))
        return obj

    def get_serializer_context(self):
        return {"user": self.request.user}


class DeleteBanners(APIView):
    permission_classes = [IsSuperAdminOrSeller]

    def post(self, request):
        banner_ids = self.request.data.get("banner_ids", "")
        top_deals = self.request.data.get("top_deals", False)

        if banner_ids != "" and json_list(banner_ids)[0]:
            if str2bool(top_deals):
                TopDealsBanner.objects.filter(
                    pk__in=json_list(banner_ids)[1]).delete()
            else:
                Banner.objects.filter(
                    pk__in=json_list(banner_ids)[1]).delete()
            create_invalidation()
            return Response({"detail": "Banners deleted"})
        return Response({"detail": "Please select atleast one banner"},
                        status=status.HTTP_400_BAD_REQUEST)


class UpdateBannersOrder(APIView):
    permission_classes = [IsSuperAdminOrSeller]

    def post(self, request):
        try:
            banner_ids_and_order = self.request.data.get("banner_ids_and_order", "")

            if banner_ids_and_order != "" and json_list(banner_ids_and_order)[0]:
                for banner_ids_and_order in json_list(banner_ids_and_order)[1]:
                    banner_id = banner_ids_and_order.get("banner_id")
                    banner_order = banner_ids_and_order.get("banner_order")
                    banner = get_object_or_404(Banner, pk=banner_id)
                    status_choices = ["AC", "SCH"]

                    if banner.status in status_choices:
                        if banner.is_for_homepage:
                            banners = Banner.objects.filter(
                                type=banner.type, is_for_homepage=True,
                                ordering_id=banner_order,
                                parent=banner.parent,
                                status__in=status_choices
                            ).exclude(pk=banner.pk)
                        else:
                            banners = Banner.objects.filter(
                                type=banner.type, seller=banner.seller,
                                ordering_id=banner_order,
                                parent=banner.parent,
                                status__in=status_choices
                            ).exclude(pk=banner.pk)
                    else:
                        if banner.is_for_homepage:
                            banners = Banner.objects.filter(
                                type=banner.type, is_for_homepage=True,
                                ordering_id=banner_order,
                                parent=banner.parent,
                                status="IN"
                            ).exclude(pk=banner.pk)
                        else:
                            banners = Banner.objects.filter(
                                type=banner.type, seller=banner.seller,
                                ordering_id=banner_order,
                                parent=banner.parent,
                                status="IN"
                            ).exclude(pk=banner.pk)

                    if banners.exists():
                        if banners.filter(is_for_homepage=True).exists():
                            return Response(
                                {"error": "Ordering id should be unique for status, type"},
                                status=status.HTTP_400_BAD_REQUEST)
                        else:
                            return Response(
                                {"error": "Ordering id should be unique for status, type, seller"},
                                status=status.HTTP_400_BAD_REQUEST)
                    else:
                        banner.ordering_id = banner_order
                        banner.save()
                return Response({"detail": "Banners order updated"})
            return Response({"detail": "Please select atleast one banner"},
                            status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)},
                            status=status.HTTP_400_BAD_REQUEST)


class RenameBanner(APIView):
    permission_classes = [IsSuperAdminOrSeller]

    def post(self, request, pk):
        name = self.request.data.get("name", None)
        nameAR = self.request.data.get("nameAR", None)
        top_deals = self.request.data.get("top_deals", False)

        if str2bool(top_deals):
            banner = get_object_or_404(TopDealsBanner, pk=pk)
        else:
            banner = get_object_or_404(Banner, pk=pk)

        if name:
            banner.name = name
        if nameAR:
            banner.nameAR = nameAR
        banner.save()
        return Response({"detail": "Banners name updated"})


class AddBanner(APIView):
    permission_classes = [IsSuperAdminOrSeller]

    def post(self, request):
        name = request.data.get("name", None)
        nameAR = request.data.get("nameAR", None)
        new_arrivals = request.data.get("new_arrivals", False)

        if not name or len(name) == 0:
            return Response(
                {"error": "Banner name is required"},
                status=status.HTTP_400_BAD_REQUEST)
        else:
            if name.startswith('"') and name.endswith('"'):
                name = name[1:-1]
                if len(name) == 0:
                    return Response(
                        {"error": "Banner name is required"},
                        status=status.HTTP_400_BAD_REQUEST)
            else:
                if str2bool(new_arrivals):
                    if name != "New Arrivals":
                        return Response(
                            {"error": "New Arrival Banner name should be New Arrivals"},
                            status=status.HTTP_400_BAD_REQUEST)
                    banner = Banner.objects.create(
                        parent=None, is_for_homepage=True,
                        name=name, nameAR=nameAR)
                else:
                    banner = Banner.objects.create(
                        parent=None, is_for_homepage=True,
                        name=name, nameAR=nameAR)
                create_invalidation()
                return Response({"detail": "Banners Set Added",
                                 "id": banner.id})


class AddHomePageBanner(CreateAPIView):
    permission_classes = [IsSuperAdminOrSeller]
    serializer_class = AddHomePageBannerSerializer
    queryset = Banner.objects.all()

    def set_banner_eng(self, request, obj):
        for attach in request.FILES.getlist('banner_image'):
            obj.banner_image = attach
            obj.save()

    def set_banner_ar(self, request, obj):
        for attach in request.FILES.getlist('banner_image_ar'):
            obj.banner_image_ar = attach
            obj.save()

    def set_home_page_items(self, request, banner):
        assign_home_page_banner_card_small(banner)

    def create(self, request, *args, **kwargs):
        serializer = AddHomePageBannerSerializer(data=request.data)
        if serializer.is_valid():
            banner = serializer.save()
            banner.is_for_homepage = True
            banner.save()
            self.set_banner_eng(request, banner)
            self.set_banner_ar(request, banner)
            self.set_home_page_items(request, banner)
            create_invalidation()
            return Response(
                BannerDetailSerializer(banner).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AddNewArrivalBanner(CreateAPIView):
    permission_classes = [IsSuperAdminOrSeller]
    serializer_class = AddNewArrivalBannerSerializer
    queryset = Banner.objects.all()

    def set_banner_eng(self, request, obj):
        for attach in request.FILES.getlist('banner_image'):
            obj.banner_image = attach
            obj.save()

    def set_banner_ar(self, request, obj):
        for attach in request.FILES.getlist('banner_image_ar'):
            obj.banner_image_ar = attach
            obj.save()

    def set_home_page_items(self, request, banner):
        assign_home_page_carousal_new_arrivals(banner)

    def create(self, request, *args, **kwargs):
        serializer = AddNewArrivalBannerSerializer(data=request.data)
        if serializer.is_valid():
            banner = serializer.save()
            banner.is_for_homepage = True
            banner.save()
            self.set_banner_eng(request, banner)
            self.set_banner_ar(request, banner)
            self.set_home_page_items(request, banner)
            create_invalidation()
            return Response(
                BannerDetailSerializer(banner).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EditNewArrivalBanner(UpdateAPIView):
    permission_classes = [IsSuperAdminOrSeller]
    serializer_class = EditNewArrivalBannerSerializer
    queryset = Banner.objects.all()

    def set_banner_eng(self, request, obj):
        for attach in request.FILES.getlist('banner_image'):
            obj.banner_image = attach
            obj.save()

    def set_banner_ar(self, request, obj):
        for attach in request.FILES.getlist('banner_image_ar'):
            obj.banner_image_ar = attach
            obj.save()

    def set_home_page_items(self, request, banner):
        assign_home_page_carousal_new_arrivals(banner)

    def update(self, request, *args, **kwargs):
        obj = get_object_or_404(Banner, pk=kwargs.get("pk"))
        if obj.parent:
            parent_banner = obj.parent
            if parent_banner.name != "New Arrivals":
                return Response(
                    {"error": "Please use only new arrival banner"},
                    status=status.HTTP_400_BAD_REQUEST)

            serializer = EditNewArrivalBannerSerializer(
                instance=obj, data=request.data)
            if serializer.is_valid():
                banner = serializer.save()
                banner.is_for_homepage = True
                banner.save()
                self.set_banner_eng(request, banner)
                self.set_banner_ar(request, banner)
                self.set_home_page_items(request, banner)
                create_invalidation()
                return Response(
                    BannerDetailSerializer(banner).data,
                    status=status.HTTP_200_OK
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {"error": "Please use only new arrival banner"},
            status=status.HTTP_400_BAD_REQUEST)


class EditHomePageBanner(UpdateAPIView):
    permission_classes = [IsSuperAdminOrSeller]
    serializer_class = EditHomePageBannerSerializer
    queryset = Banner.objects.all()

    def set_banner_eng(self, request, obj):
        for attach in request.FILES.getlist('banner_image'):
            obj.banner_image = attach
            obj.save()

    def set_banner_ar(self, request, obj):
        for attach in request.FILES.getlist('banner_image_ar'):
            obj.banner_image_ar = attach
            obj.save()

    def set_home_page_items(self, request, banner):
        assign_home_page_banner_card_small(banner)

    def update(self, request, *args, **kwargs):
        print("editHOmepagebanner")
        print(request.data)
        obj = get_object_or_404(Banner, pk=kwargs.get("pk"))
        serializer = EditHomePageBannerSerializer(
            instance=obj, data=request.data)
        if serializer.is_valid():
            banner = serializer.save()
            banner.is_for_homepage = True
            banner.save()
            self.set_banner_eng(request, banner)
            self.set_banner_ar(request, banner)
            self.set_home_page_items(request, banner)
            create_invalidation()
            return Response(
                BannerDetailSerializer(banner).data,
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AddTopDealsBanner(CreateAPIView):
    permission_classes = [IsSuperAdminOrSeller]
    serializer_class = AddTopDealsBannerSerializer
    queryset = TopDealsBanner.objects.all()

    def set_banner_eng(self, request, obj):
        for attach in request.FILES.getlist('banner_image'):
            obj.banner_image = attach
            obj.save()

    def set_banner_ar(self, request, obj):
        for attach in request.FILES.getlist('banner_image_ar'):
            obj.banner_image_ar = attach
            obj.save()

    def set_top_deal_page_items(self, request, banner):
        assign_top_deals_page_banner_card_small(banner)

    def create(self, request, *args, **kwargs):
        serializer = AddTopDealsBannerSerializer(data=request.data)
        if serializer.is_valid():
            banner = serializer.save()
            banner.save()
            self.set_banner_eng(request, banner)
            self.set_banner_ar(request, banner)
            self.set_top_deal_page_items(request, banner)
            create_invalidation()
            return Response(
                BannerDetailSerializer(banner).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TopDealsBannerDetail(RetrieveAPIView):
    permission_classes = [IsSuperAdminOrSeller]
    serializer_class = TopDealsBannerDetailSerializer

    def get_object(self):
        obj = get_object_or_404(TopDealsBanner, pk=self.kwargs.get("pk"))
        return obj

    def get_serializer_context(self):
        return {"user": self.request.user}


class EditTopDealsBanner(UpdateAPIView):
    permission_classes = [IsSuperAdminOrSeller]
    serializer_class = EditTopDealsBannerSerializer
    queryset = TopDealsBanner.objects.all()

    def set_banner_eng(self, request, obj):
        for attach in request.FILES.getlist('banner_image'):
            obj.banner_image = attach
            obj.save()

    def set_banner_ar(self, request, obj):
        for attach in request.FILES.getlist('banner_image_ar'):
            obj.banner_image_ar = attach
            obj.save()

    def set_top_deal_page_items(self, request, banner):
        assign_top_deals_page_banner_card_small(banner)

    def update(self, request, *args, **kwargs):
        obj = get_object_or_404(TopDealsBanner, pk=kwargs.get("pk"))
        serializer = EditTopDealsBannerSerializer(
            instance=obj, data=request.data)
        if serializer.is_valid():
            banner = serializer.save()
            banner.save()
            self.set_banner_eng(request, banner)
            self.set_banner_ar(request, banner)
            self.set_top_deal_page_items(request, banner)
            create_invalidation()
            return Response(
                TopDealsBannerDetailSerializer(banner).data,
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


def test_function():
    print("testing zappa call later")
    report_to_developer("tested zappa later", "success")

