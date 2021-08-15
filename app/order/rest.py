import os
import sys
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.db.models import Q, Count, F
from django.utils.timezone import now
from rest_framework import viewsets, status, generics
from rest_framework.authentication import TokenAuthentication
from rest_framework.generics import CreateAPIView, ListAPIView, get_object_or_404, UpdateAPIView, DestroyAPIView, \
    RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from app.authentication.permissions import IsSuperAdminOrSeller, IsSuperAdminOrObjectSeller, IsSuperAdmin
from app.authentication.serializers import AddressDetailSerializer
from app.ecommnotification.models import DashboardEcommNotification
from app.ecommnotification.zappa_tasks import send_order_out_for_delivery_push, send_order_delivered_push, \
    send_order_rescheduled_push
from app.order.delicon import create_reschedule_delicon_order, create_delicon_order
from app.order.models import Order, OrderProduct, CancelledOrderProduct, OrderStatusTrack, OrderProductStatusTrack, \
    OrderViews
from app.order.serializers import OrderListSerializer, OrderDetailSerializer, AddEditAddressSerializer, \
    OrderStatusTrackSerializer, OrderProdStatusTrackSerializer
from app.order.utils import DeliveryLogPagination
from app.order.zappa_tasks import send_cancel_email_orders_seller, send_cancel_email_orders_customer, \
    send_cancel_email_items_seller, send_cancel_email_items_customer
from app.product.models import Brand, Category, CategoryMedia, EcommProduct, EcommProductMedia
from app.product.serializers import BrandListSerializer, BrandSerializer, AddEditBrandSerializer, \
    CategoryListSerializer, AddEditCategorySerializer, CategorySerializer, AddSubCategorySerializer, \
    ProductListSerializer, AddEditProductSerializer, ProductDetailSerializer, EditProductSerializer
from app.product.utils import json_list
from app.store.models import Address, InventoryProduct
from app.utilities.cache_invalidation import create_invalidation
from app.utilities.helpers import str2bool, report_to_developer
from django.utils.translation import ugettext_lazy as _


class OrderList(ListAPIView):
    permission_classes = [IsSuperAdminOrSeller]
    serializer_class = OrderListSerializer
    http_method_names = [u'get', u'post']

    def _allowed_methods(self):
        return [m.upper() for m in self.http_method_names if hasattr(self, m)]

    def search(self, qs, search_string):
        for qstring in search_string.split(" "):
            qs = qs.filter(
                Q(pk__icontains=qstring) |
                Q(customer__full_name__icontains=qstring) |
                Q(customer__first_name__icontains=qstring) |
                Q(customer__last_name__icontains=qstring)
            ).order_by('id').distinct()
        return qs

    def get_serializer_context(self):
        return {"user": self.request.user,
                "lang_code": self.request.query_params.get("lang_code", "")}

    def get_queryset(self):
        search_string = self.request.query_params.get("search_string", "")
        sort_by = self.request.query_params.get("sort_by", "")
        seller_ids = self.request.data.get("seller_ids", "")
        order_status = self.request.query_params.get("order_status", "")
        payment_status = self.request.data.get("payment_status", "")
        days = self.request.data.get("days", None)
        from_date = self.request.data.get("from_date", None)
        to_date = self.request.data.get("to_date", None)
        customer_id = self.request.query_params.get("customer_id", "")

        if self.request.user.is_seller:
            sub_admins = self.request.user.seller_sub_admins.all()
            if sub_admins.exists():
                sub_admin = sub_admins.latest('id')
                qs = Order.objects.filter(
                    payments__isnull=False,
                    orderProducts__product__store=sub_admin.store).distinct()
            else:
                qs = Order.objects.filter(
                    payments__isnull=False,
                    orderProducts__product__store__member=self.request.user).distinct()
        else:
            qs = Order.objects.filter(payments__isnull=False).distinct()

        if customer_id != "":
            qs = qs.filter(customer__pk=customer_id).distinct()

        order_prod_filter = filter(
            lambda x: x.order_prods_has_prod() is True, qs)
        qs = qs.filter(id__in=list([x.id for x in order_prod_filter]))

        if seller_ids != "" and json_list(seller_ids)[0]:
            qs = qs.filter(
                orderProducts__product__store__pk__in=json_list(seller_ids)[1]
            ).distinct()

        if order_status != "":
            failed_payment_status_filter = filter(
                lambda x: x.get_payment_status() == "Failed", qs)

            qs = qs.filter(orderProducts__status=order_status).exclude(
                id__in=list([x.id for x in failed_payment_status_filter])
            )

        if payment_status != "":
            payment_status_filter = filter(
                lambda x: x.get_payment_status() == payment_status, qs)
            qs = qs.filter(id__in=list([x.id for x in payment_status_filter]))

        if days == 0 or days:
            date_selected = now() - timedelta(days=int(days))
            qs = qs.filter(created_at__date__gte=date_selected.date())

        if from_date and to_date:
            qs = qs.filter(
                created_at__date__gte=from_date,
                created_at__date__lte=to_date)

        if search_string != "":
            qs = self.search(qs, search_string)

        if sort_by != "":
            if sort_by == "new_first":
                qs = qs.order_by('-created_at')
            if sort_by == "old_first":
                qs = qs.order_by('created_at')

            if sort_by == "order_no_asc":
                qs = qs.order_by('pk')
            if sort_by == "order_no_desc":
                qs = qs.order_by('-pk')

            if sort_by == "cust_name_a_to_z":
                qs = qs.order_by('customer__full_name')
            if sort_by == "cust_name_z_to_a":
                qs = qs.order_by('-customer__full_name')

            if sort_by == "total_price_low_to_high":
                qs = sorted(qs,
                            key=lambda t: t.get_totalPrice_float(),
                            reverse=False)
            if sort_by == "total_price_high_to_low":
                qs = sorted(qs,
                            key=lambda t: t.get_totalPrice_float(),
                            reverse=True)

            if sort_by == "items_low_to_high":
                qs = qs.annotate(item_count=Count(F('orderProducts'))).order_by(
                    'item_count').distinct()
            if sort_by == "items_high_to_low":
                qs = qs.annotate(item_count=Count(F('orderProducts'))).order_by(
                    '-item_count').distinct()

        return qs

    def post(self, request, *args, **kwargs):
        try:
            qs = self.list(request, *args, **kwargs)
            return qs
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(str(e), (fname, exc_tb.tb_lineno))
            report_to_developer("Issue in order list", str(e)
                                + "at %s, line number %s" % (fname, exc_tb.tb_lineno))
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CancelOrders(APIView):
    permission_classes = [IsSuperAdminOrSeller]

    def post(self, request):
        order_ids = self.request.data.get("order_ids", "")
        cancellationReason = self.request.data.get("cancellationReason", "")

        if order_ids != "" and json_list(order_ids)[0]:
            Order.objects.filter(
                pk__in=json_list(order_ids)[1]
            ).update(status='CA', cancellationReason=cancellationReason)

            orders = Order.objects.filter(
                pk__in=json_list(order_ids)[1]
            )

            for ord in orders:
                ord.status = "CA"
                ord.save()
                OrderStatusTrack.objects.create(
                    order=ord,
                    status='CA',
                    updated_by=request.user,
                    reason=cancellationReason
                )
                DashboardEcommNotification.objects.order_status_cancelled(
                    ord, request.user, "CA", cancellationReason)

            OrderProduct.objects.filter(
                order__pk__in=json_list(order_ids)[1]
            ).update(status='CA', cancellationReason=cancellationReason)

            ops = OrderProduct.objects.filter(
                order__pk__in=json_list(order_ids)[1]
            )
            for op in ops:
                op.order.refunded_price += op.product.get_discounted_price_or_base_price() * op.quantity
                op.order.save()
                OrderProductStatusTrack.objects.create(
                    order_product=op,
                    status='CA',
                    updated_by=request.user,
                    reason=cancellationReason
                )
                if op.quantity > 0:
                    InventoryProduct.objects.filter(
                        product=op.product,
                        inventory__store=op.product.store
                    ).update(quantity=F('quantity') + op.quantity)

            send_cancel_email_orders_seller(json_list(order_ids)[1])
            send_cancel_email_orders_customer(json_list(order_ids)[1])
            create_invalidation()
            return Response({"detail": "Successfully cancelled orders"})
        return Response({"detail": "Please select atleast one order"},
                        status=status.HTTP_400_BAD_REQUEST)


class OrderDetails(RetrieveAPIView):
    serializer_class = OrderDetailSerializer

    def increase_logged_in_user_order_views(self, order, request):
        if OrderViews.objects.filter(
                order=order, member=request.user).exists():
            OrderViews.objects.update_or_create(
                order=order,
                member=request.user,
                defaults={
                    'no_of_views': F('no_of_views') + 1
                }
            )
        else:
            OrderViews.objects.create(
                order=order,
                member=request.user,
                no_of_views=1
            )

    def get_object(self):
        obj = get_object_or_404(Order, pk=self.kwargs.get("pk"))
        self.increase_logged_in_user_order_views(obj, self.request)
        return obj

    def get_serializer_context(self):
        return {"user": self.request.user,
                "lang_code": self.request.query_params.get("lang_code", "")}


class UpdateProdStatus(APIView):
    permission_classes = [IsSuperAdminOrSeller]

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        product_ids = request.data.get("product_ids", "")
        print("prod_ids")
        print(product_ids)
        order_prod_status = request.data.get("order_prod_status", "")
        reschedule_at = request.data.get("reschedule_at", "")
        reschedule_reason = request.data.get("reschedule_reason", "")
        rfp_remarks = request.data.get("rfp_remarks", "")
        dec_remarks = request.data.get("dec_remarks", "")
        ret_remarks = request.data.get("ret_remarks", "")

        if product_ids != "" and json_list(product_ids)[0]:

            if order_prod_status != "":
                order_prods = OrderProduct.objects.filter(
                    product__pk__in=json_list(product_ids)[1],
                    order=order
                )
                for op in order_prods:
                    op.status = order_prod_status
                    op.save()
                    print("op.status")
                    print(op.status)
                    print("param")
                    print(order_prod_status)
                    order_prod_status_track = OrderProductStatusTrack.objects.create(
                        order_product=op,
                        status=order_prod_status,
                        updated_by=request.user
                    )
                    if reschedule_at != "":
                        order_prod_status_track.rescheduled_at = reschedule_at
                        order_prod_status_track.save()

                    if reschedule_reason != "":
                        order_prod_status_track.reason = reschedule_reason
                        order_prod_status_track.save()

                    if rfp_remarks != "":
                        order_prod_status_track.reason = rfp_remarks
                        order_prod_status_track.save()

                    if dec_remarks != "":
                        order_prod_status_track.reason = dec_remarks
                        order_prod_status_track.save()

                    if ret_remarks != "":
                        order_prod_status_track.reason = ret_remarks
                        order_prod_status_track.save()

                    if order_prod_status == "OFD":
                        op.out_for_delivery_at = order_prod_status_track.created_at
                        op.save()
                    if order_prod_status == "DEL":
                        op.delivered_at = order_prod_status_track.created_at
                        op.save()

                if order_prod_status == "RES":
                    OrderProduct.objects.filter(
                        product__pk__in=json_list(product_ids)[1],
                        order=order
                    ).update(
                        rescheduled_at=reschedule_at,
                        rescheduled_reason=reschedule_reason)
                    DashboardEcommNotification.objects.order_status_rescheduled(
                        order, request.user, reschedule_at, reschedule_reason, "RES")

                    if settings.SITE_CODE == 1:
                        create_reschedule_delicon_order(order)

                if order_prod_status == "RFP":
                    OrderProduct.objects.filter(
                        product__pk__in=json_list(product_ids)[1],
                        order=order
                    ).update(
                        ready_for_pickup_remarks=rfp_remarks)

                if order_prod_status == "DEC":
                    OrderProduct.objects.filter(
                        product__pk__in=json_list(product_ids)[1],
                        order=order
                    ).update(
                        declined_reason=dec_remarks)
                    ps = EcommProduct.objects.filter(
                        pk__in=json_list(product_ids)[1]
                    )
                    DashboardEcommNotification.objects.order_prod_status_declined(
                        order, request.user, ps, dec_remarks, "DEC")

                if order_prod_status == "RET":
                    OrderProduct.objects.filter(
                        product__pk__in=json_list(product_ids)[1],
                        order=order
                    ).update(
                        returned_reason=ret_remarks)
                    ps = EcommProduct.objects.filter(
                        pk__in=json_list(product_ids)[1]
                    )
                    DashboardEcommNotification.objects.order_prod_status_returned(
                        order, request.user, ps, ret_remarks, "RET")

                if order_prod_status == "RBFC":
                    ps = EcommProduct.objects.filter(
                        pk__in=json_list(product_ids)[1]
                    )
                    DashboardEcommNotification.objects.order_prod_status_ready_for_bfc(
                        order, request.user, ps, "RBFC")

                if order_prod_status == "TBS":
                    ps = EcommProduct.objects.filter(
                        pk__in=json_list(product_ids)[1]
                    )
                    DashboardEcommNotification.objects.order_prod_status_transit_by_seller(
                        order, request.user, ps, "TBS")
                create_invalidation()
                return Response({"detail": f"Successfully added products to {order_prod_status}"})
            return Response({"error": "Please select order product status"},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({"error": "Please select atleast one product"},
                        status=status.HTTP_400_BAD_REQUEST)


class UpdateOrderStatus(APIView):
    permission_classes = [IsSuperAdminOrSeller]

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        order_status = request.data.get("order_status", "")
        reschedule_at = request.data.get("reschedule_at", "")
        reschedule_reason = request.data.get("reschedule_reason", "")
        rfp_remarks = request.data.get("rfp_remarks", "")
        dec_remarks = request.data.get("dec_remarks", "")
        ret_remarks = request.data.get("ret_remarks", "")

        if order_status != "":
            order.status = order_status
            order.save()

            OrderProduct.objects.filter(
                order=order).update(
                status=order_status
            )
            order_prods = OrderProduct.objects.filter(
                order=order
            )
            for op in order_prods:
                op_stat = OrderProductStatusTrack.objects.create(
                    order_product=op,
                    status=order_status,
                    updated_by=request.user
                )
                if reschedule_at != "":
                    op_stat.rescheduled_at = reschedule_at
                if reschedule_reason != "":
                    op_stat.reason = reschedule_reason
                op_stat.save()

            order_status_track = OrderStatusTrack.objects.create(
                order=order,
                status=order_status,
                updated_by=request.user
            )
            if order_status == "OFD":
                order.out_for_delivery_at = order_status_track.created_at
                order.save()
                send_order_out_for_delivery_push(order)

            if order_status == "DEL":
                order.delivered_at = order_status_track.created_at
                order.save()
                send_order_delivered_push(order)

            if order_status == "RES":
                OrderProduct.objects.filter(order=order).update(
                    rescheduled_at=reschedule_at,
                    rescheduled_reason=reschedule_reason)

                order.rescheduled_at = reschedule_at
                order.rescheduled_reason = reschedule_reason
                order.save()
                send_order_rescheduled_push(order)

                if settings.SITE_CODE == 1:
                    create_reschedule_delicon_order(order)

            if order_status == "RFP":
                OrderProduct.objects.filter(
                    order=order).update(
                    ready_for_pickup_remarks=rfp_remarks)

            if order_status == "RET":
                OrderProduct.objects.filter(
                    order=order).update(
                    returned_reason=ret_remarks)
                DashboardEcommNotification.objects.order_status_returned(
                    order, request.user, "RET", ret_remarks)

            if order_status == "DEC":
                OrderProduct.objects.filter(
                    order=order).update(
                    declined_reason=dec_remarks)
                DashboardEcommNotification.objects.order_status_declined(
                    order, request.user, dec_remarks, "DEC")

            if order_status == "RBFC":
                DashboardEcommNotification.objects.order_status_ready_for_bfc(
                    order, request.user, "RBFC")

            if order_status == "TBS":
                DashboardEcommNotification.objects.order_status_transit_by_seller(
                    order, request.user, "TBS")
            create_invalidation()
            return Response({"detail": f"Successfully updated order status to {order_status}"})
        return Response({"error": "Please select order status"},
                        status=status.HTTP_400_BAD_REQUEST)


class EditShippingAddress(UpdateAPIView):
    serializer_class = AddEditAddressSerializer

    def get_object(self):
        return get_object_or_404(Address, pk=self.kwargs.get("pk"))

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = self.serializer_class(obj, data=request.data)
        if serializer.is_valid():
            instance = serializer.save()
            create_invalidation()
            return Response(
                AddressDetailSerializer(
                    instance
                ).data
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CancelAndRefundOrder(APIView):
    permission_classes = [IsSuperAdminOrSeller]

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        previous_order_status = order.status
        print("order.status")
        print(order.status)
        cancellationReason = request.data.get("cancellationReason", "")
        restock_items = request.data.get("restock_items", True)
        cancelled_qty_list = request.data.get("cancelled_qty_list", "")

        OrderStatusTrack.objects.create(
            order=order,
            status="CA",
            updated_by=request.user,
            reason=cancellationReason
        )

        print("cancelled_qty_list_param")
        print(cancelled_qty_list)
        if cancelled_qty_list != "":
            for cancelled_qty_item in cancelled_qty_list:
                prod_id = cancelled_qty_item.get("product")
                qty = cancelled_qty_item.get("qty")

                if qty > 0:
                    order_prods = OrderProduct.objects.filter(
                        order=order,
                        product__id=prod_id
                    ).distinct()
                    print("order_qty_prods")
                    print(order_prods)
                    for op in order_prods:
                        if op.quantity == qty:
                            order.refunded_price += op.product.get_discounted_price_or_base_price() * qty
                            order.save()

                            op.cancellationReason = cancellationReason
                            op.status = "CA"
                            op.save()

                            print("order_stat")
                            print(order.status)
                        else:
                            CancelledOrderProduct.objects.create(
                                order_product=op,
                                cancelled_qty=qty,
                                qty_cancellationReason=cancellationReason
                            )
                            order.refunded_price += op.product.get_discounted_price_or_base_price() * qty
                            order.save()

                            op.cancellationReason = cancellationReason
                            op.status = "CA"
                            op.save()
                            print("order_stat")
                            print(order.status)
                        OrderProductStatusTrack.objects.create(
                            order_product=op,
                            status='CA',
                            updated_by=request.user,
                            reason=cancellationReason
                        )

        if str2bool(restock_items):
            for cancelled_qty_item in cancelled_qty_list:
                prod_id = cancelled_qty_item.get("product")
                qty = cancelled_qty_item.get("qty")

                if qty > 0:
                    order_prods = OrderProduct.objects.filter(
                        order=order,
                        product__id=prod_id
                    ).distinct()
                    for op in order_prods:
                        InventoryProduct.objects.filter(
                            product=op.product,
                            inventory__store=op.product.store
                        ).update(quantity=F('quantity')+qty)

        order_prod_ids = []
        for cancelled_qty_item in cancelled_qty_list:
            prod_id = cancelled_qty_item.get("product")
            order_product_ids = OrderProduct.objects.filter(
                order=order,
                product__id=prod_id
            ).values_list('id', flat=True)
            for x in order_product_ids:
                order_prod_ids.append(x)

        print("order_prod_ids")
        print(order_prod_ids)
        if len(order_prod_ids) > 0:
            send_cancel_email_items_seller(list(order_prod_ids))
            send_cancel_email_items_customer(list(order_prod_ids))

        print("order_stat")
        print(order.status)
        cancelled_op_count = order.orderProducts.filter(
            status='CA'
        ).count()
        if cancelled_op_count == order.orderProducts.all().count():
            DashboardEcommNotification.objects.order_status_cancelled(
                order, request.user, "CA", cancellationReason)
        else:
            prod_ids = OrderProduct.objects.filter(
                pk__in=list(order_prod_ids)
            ).values_list('product_id', flat=True)
            prod_qs = EcommProduct.objects.filter(
                pk__in=prod_ids
            )
            DashboardEcommNotification.objects.order_prod_status_cancelled(
                order, request.user, prod_qs, cancellationReason, "CA")
        create_invalidation()
        return Response({"detail": "Successfully cancelled order",
                         "refunded_total": order.refunded_price})


class DeliveryLogForOrderProd(ListAPIView):
    serializer_class = OrderProdStatusTrackSerializer

    def get_queryset(self):
        obj = get_object_or_404(OrderProduct, pk=self.kwargs.get("pk"))
        orderprodstats = OrderProductStatusTrack.objects.filter(
            order_product=obj
        )

        qs = obj.orderproductstatustrack.all().order_by('-created_at')
        return qs

    def get_serializer_context(self):
        return {"user": self.request.user,
                "lang_code": self.request.query_params.get("lang_code", "")}

    def list(self, request, *args, **kwargs):
        obj = get_object_or_404(OrderProduct, pk=self.kwargs.get("pk"))
        queryset = self.filter_queryset(self.get_queryset())
        result_qs = queryset

        paginator = DeliveryLogPagination()
        page = paginator.paginate_queryset(result_qs, request)
        if page is not None:
            serializer = self.get_serializer(
                page, many=True, context=self.get_serializer_context())
            return paginator.get_paginated_response(
                serializer.data, extra_keys={
                    'order_prod': obj
                })

        serializer = self.get_serializer(result_qs, many=True)
        return Response(serializer.data)
