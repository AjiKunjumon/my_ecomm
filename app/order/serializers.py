from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count, Q, When, Value, Case, CharField
from phonenumbers import national_significant_number
from rest_framework import serializers


from app.authentication.models import Member
from app.authentication.models.member import GuestAccount
from app.authentication.serializers import AddressDetailSerializer
from app.order.models import Order, OrderProduct, OrderStatusTrack, OrderProductStatusTrack
from app.product.models import Brand, VariantValues
from app.product.serializers import EcommProductMediaSerializer
from app.store.models import Store, PaymentType, Payment, Address
from django.utils.translation import ugettext_lazy as _


class CustomerSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    company = serializers.SerializerMethodField()

    class Meta:
        model = Member
        fields = (
            'id', "full_name", "email", "phone", "company"
        )

    def get_phone(self, obj):
        if obj.phone != "" and obj.phone is not None:
            phone_string = "-".join([
                str(obj.phone.country_code),
                str(national_significant_number(obj.phone))
            ])
            return "+" + phone_string
        return ""

    def get_full_name(self, obj):
        if obj.full_name == "":
            return obj.get_full_name()
        return obj.full_name

    def get_company(self, obj):
        if obj.is_super_admin:
            obj.company = "Becon"
            obj.save()
        return obj.company


class GuestAccSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    company = serializers.SerializerMethodField()

    class Meta:
        model = GuestAccount
        fields = (
            'id', "full_name", "email", "phone", "company"
        )

    def get_phone(self, obj):
        if obj.phone != "" and obj.phone is not None:
            phone_string = "-".join([
                str(obj.phone.country_code),
                str(national_significant_number(obj.phone))
            ])
            return "+" + phone_string
        return ""

    def get_full_name(self, obj):
        return obj.get_exact_full_name()

    def get_company(self, obj):
        return ""


class OrderListSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    serial_no = serializers.SerializerMethodField()
    total_prod_count = serializers.SerializerMethodField()
    date = serializers.SerializerMethodField()
    customer = serializers.SerializerMethodField()
    totalPrice = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    seller_info = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()
    updated_at = serializers.SerializerMethodField()
    is_seen = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            'id', 'status', 'customer',
            'totalPrice', 'payment_status',
            'total_prod_count',
            'serial_no', 'created_at', 'updated_at',
            'discounted_price', 'shipping_charge',
            'refunded_price', 'total_after_refund',
            'date', 'seller_info', 'is_seen'
        )

    def get_date(self, obj):
        if obj.created_at:
            return obj.created_at
        return None
        # kuwait_date = datetime_from_utc_to_local_new(obj.created_at)
        # formatted_date = obj.created_at.strftime("%b %d, %Y")
        # formatted_time = obj.created_at.strftime("%H:%M %p")
        # return f"{formatted_date} at {formatted_time}"

    def get_created_at(self, obj):
        if obj.created_at:
            return obj.created_at
        return None
        # kuwait_date = datetime_from_utc_to_local_new(obj.created_at)
        # formatted_date = obj.created_at.strftime("%b %d, %Y")
        # formatted_time = obj.created_at.strftime("%H:%M %p")
        # return f"{formatted_date} at {formatted_time}"

    def get_updated_at(self, obj):
        if obj.updated_at:
            return obj.updated_at
        return None

        # kuwait_date = datetime_from_utc_to_local_new(obj.updated_at)
        # formatted_date = obj.updated_at.strftime("%b %d, %Y")
        # formatted_time = obj.updated_at.strftime("%H:%M %p")
        # return f"{formatted_date} at {formatted_time}"

    def reduce_order_amount(self, order, deductable_amount):
        order.totalPrice = order.get_totalPrice_without_shipping_charge()
        order.sub_total = order.get_sub_total()
        order.totalPrice -= deductable_amount
        order.sub_total -= deductable_amount

        if order.totalPrice < 0:
            order.totalPrice = 0
        if order.sub_total < 0:
            order.sub_total = 0
        order.totalPrice += settings.SHIPPING_CHARGE
        order.save()

    def order_amount_to_reduce(self, order):
        coupon = order.coupon
        if coupon:
            if order.customer and order.customer.cart.exists():
                cart = order.customer.cart.all().latest('id')
                deductable_amount = 0.0
                if coupon.deductable_amount != 0.0:
                    deductable_amount = coupon.deductable_amount
                elif coupon.deductable_percentage != 0.0:
                    deductable_amount = coupon.get_discounted_price_order(order)
                elif coupon.type == "FS":
                    deductable_amount = 0.0
                if deductable_amount > order.get_sub_total():
                    order.discounted_price = order.get_sub_total()
                else:
                    order.discounted_price = deductable_amount
                order.save()
            elif order.guest_acc and order.guest_acc.cart.exists():
                cart = order.guest_acc.cart.all().latest('id')
                deductable_amount = 0.0
                if coupon.deductable_amount != 0.0:
                    deductable_amount = coupon.deductable_amount
                elif coupon.deductable_percentage != 0.0:
                    deductable_amount = coupon.get_discounted_price_order(self)
                elif coupon.type == "FS":
                    deductable_amount = 0.0

                if deductable_amount > self.get_sub_total():
                    order.discounted_price = self.get_sub_total()
                else:
                    order.discounted_price = deductable_amount
                order.save()
            self.reduce_order_amount(order, order.discounted_price)

    def get_totalPrice(self, obj):
        user = self.context.get("user")
        return obj.get_totalPrice_with_user(user)

    def get_payment_status(self, obj):
        if obj.payments.all().filter(status='SU').exists():
            cancelled_op_count = obj.orderProducts.filter(
                status='CA'
            ).count()

            if cancelled_op_count == obj.orderProducts.all().count():
                return "Refunded"
            elif cancelled_op_count > 0:
                return "Partially Refunded"
            return "Paid"

            # sub_total = obj.orderProducts.all().aggregate(
            #     sub_total=Sum(Case(When(
            #         product__discount__isnull=True,
            #         then=F('product__base_price') * F('quantity')),
            #         default=(F('product__base_price')
            #                  - (F('product__base_price')
            #                     * F('product__discount__percentage')) / 100) * F('quantity'),
            #         output_field=FloatField()))).get('sub_total')
            #
            # if obj.refunded_price < sub_total and obj.refunded_price != 0.0:
            #     return "Partially Refunded"
            # elif obj.refunded_price == sub_total and obj.refunded_price != 0.0:
            #     return "Refunded"
            # return "Paid"

        return "Failed"

    def get_seller_info(self, obj):
        if obj.orderProducts.exists():
            seller_id_list = obj.orderProducts.all().values_list(
                'product__store__id', flat=True).distinct()
            sellers = Store.objects.filter(
                pk__in=seller_id_list
            )
            return SellerListByCategorySerializer(sellers, many=True).data
        return None

    def get_customer(self, obj):
        if obj.customer:
            return CustomerSerializer(obj.customer).data
        elif obj.guest_acc:
            return GuestAccSerializer(obj.guest_acc).data

    def get_status(self, obj):
        cancelled_status = [_("Cancelled")]
        user = self.context.get("user")
        if user.is_seller:
            sub_admins = user.seller_sub_admins.all()
            if sub_admins.exists():
                sub_admin = sub_admins.latest('id')
                order_prods = obj.orderProducts.filter(
                    product__store=sub_admin.store).distinct()
            else:
                order_prods = obj.orderProducts.filter(
                    product__store__member=user).distinct()
        else:
            order_prods = obj.orderProducts.all()

        if obj.get_status_display() in cancelled_status:
           OrderProduct.objects.filter(order=obj).update(
                status='CA'
            )
        choices = dict(OrderProduct._meta.get_field('status').flatchoices)
        whens = [When(status=k, then=Value(v)) for k, v in choices.items()]
        status_tuple = (
            order_prods
                .annotate(status_to_display=Case(*whens, output_field=CharField()))
                .values('status_to_display')
                .annotate(count=Count('status'))
                .order_by()
        )
        return status_tuple

    def get_serial_no(self, obj):
        return "#".join([
             "", str(obj.id)
        ])

    def get_total_prod_count(self, obj):
        user = self.context.get("user")
        if user.is_seller:
            sub_admins = user.seller_sub_admins.all()
            if sub_admins.exists():
                sub_admin = sub_admins.latest('id')
                order_prod_count = obj.orderProducts.filter(
                    product__store=sub_admin.store).distinct().count()
            else:
                order_prod_count = obj.orderProducts.filter(
                    product__store__member=user).distinct().count()
        else:
            order_prod_count = obj.orderProducts.all().count()
        return order_prod_count

    def get_is_seen(self, obj):
        user = self.context.get("user")
        if obj.pk in user.order_views.all().values_list('order_id', flat=True):
            return True
        return False


class BrandSerializer(serializers.ModelSerializer):
    is_selected = serializers.SerializerMethodField()

    class Meta:
        model = Brand
        fields = (
            "id", "name", "image", "is_selected"
        )

    def get_name(self, obj):
        lang_code = self.context.get("lang_code")
        if lang_code == "ar":
            return obj.nameAR
        return obj.name

    def get_is_selected(self, obj):
        selected_brand_ids = self.context.get("selected_brand_ids", None)
        if selected_brand_ids:
            return True if obj.id in selected_brand_ids else False
        return False


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


class SellerListByCategorySerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()

    class Meta:
        model = Store
        fields = (
            "id", "name", "image", "type"
        )

    def get_name(self, obj):
        lang_code = self.context.get("lang_code")
        if lang_code == "ar":
            return obj.nameAR
        return obj.name

    def get_type(self, obj):
        return obj.get_type_display()


class ProdVariantSerializer(serializers.ModelSerializer):
    brand = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    media = serializers.SerializerMethodField()
    variant_with_value = serializers.SerializerMethodField()
    seller_information = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    id = serializers.SerializerMethodField()
    discounted_price = serializers.SerializerMethodField()
    base_price = serializers.SerializerMethodField()
    out_for_delivery_at = serializers.SerializerMethodField()
    delivered_at = serializers.SerializerMethodField()
    sku = serializers.SerializerMethodField()
    status_track = serializers.SerializerMethodField()
    order_prod_id = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    barCode = serializers.SerializerMethodField()

    class Meta:
        model = OrderProduct
        fields = (
            "id", "order_prod_id", "name", "quantity", "status",
            "base_price", "discounted_price", "barCode",
            "brand", "media", "sku",
            "variant_with_value", "seller_information",
            "out_for_delivery_at", "delivered_at",
            "status_track", "payment_status"
        )

    def get_id(self, obj):
        if obj.product:
            return obj.product.id
        return None

    def get_order_prod_id(self, obj):
        return obj.id

    def get_sku(self, obj):
        if obj.product:
            return obj.product.sku
        return None

    def get_barCode(self, obj):
        if obj.product:
            return obj.product.barCode
        return None

    def get_payment_status(self, obj):
        if obj.order.payments.all().filter(status='SU').exists():
            if obj.status == "CA":
                return "Refunded"
            return "Paid"
        return "Failed"

    def get_out_for_delivery_at(self, obj):
        if obj.out_for_delivery_at:
            return obj.out_for_delivery_at
            # kuwait_date = datetime_from_utc_to_local_new(obj.out_for_delivery_at)
            # formatted_date = obj.out_for_delivery_at.strftime("%b %d, %Y")
            # formatted_time = obj.out_for_delivery_at.strftime("%H:%M %p")
            # return f"{formatted_date} at {formatted_time}"
        return None

    def get_delivered_at(self, obj):
        if obj.delivered_at:
            return obj.delivered_at
            # kuwait_date = datetime_from_utc_to_local_new(obj.delivered_at)
            # formatted_date = obj.delivered_at.strftime("%b %d, %Y")
            # formatted_time = obj.delivered_at.strftime("%H:%M %p")
            # return f"{formatted_date} at {formatted_time}"
        return None

    def get_name(self, obj):
        lang_code = self.context.get("lang_code")
        if lang_code == "ar":
            return obj.product.nameAR
        return obj.product.name

    def get_base_price(self, obj):
        return obj.product.base_price

    def get_discounted_price(self, obj):
        try:
            obj.product.discount
        except ObjectDoesNotExist:
            return None
        return obj.product.discount.discounted_price()

    def get_status(self, obj):
        cancelled_status = [_("Cancelled"), _("Declined"), _("Refunded")]

        if obj.order.get_status_display() in cancelled_status \
                or obj.order.get_payment_status() == "Failed":
            return _("Cancelled")
        return obj.get_status_display()

    def get_brand(self, obj):
        return BrandSerializer(obj.product.brand).data

    def get_media(self, obj):
        if obj.product.medias.filter(is_thumbnail=False).exists():
            media = obj.product.medias.filter(is_thumbnail=False).first()
            return EcommProductMediaSerializer(media).data
        return None

    def get_variant_with_value(self, obj):
        var_vals = VariantValues.objects.filter(
            pk__in=obj.product.variant_value_ids()
        )
        return VariantValuesMinSerializer(
            var_vals, many=True, context=self.context).data

    def get_seller_information(self, obj):
        if obj.product.store:
            return SellerListByCategorySerializer(obj.product.store).data
        return None

    def get_status_track(self, obj):
        if obj.orderproductstatustrack.exists:
            order_prod_status_track = obj.orderproductstatustrack.order_by(
                '-created_at')
            return OrderProdStatusTrackSerializer(
                order_prod_status_track, many=True,
                context={'order': obj}).data
        return None


class OrderProdMinSerializer(serializers.ModelSerializer):
    brand = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    media = serializers.SerializerMethodField()
    seller_information = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    id = serializers.SerializerMethodField()
    discounted_price = serializers.SerializerMethodField()
    base_price = serializers.SerializerMethodField()
    variant_with_value = serializers.SerializerMethodField()
    status_track = serializers.SerializerMethodField()

    class Meta:
        model = OrderProduct
        fields = (
            "id", "name", "quantity", "status",
            "base_price", "discounted_price",
            "brand", "media",  "seller_information",
            "variant_with_value", "status_track"
        )

    def get_id(self, obj):
        if obj.product:
            return obj.product.id
        return None

    def get_sku(self, obj):
        if obj.product:
            return obj.product.sku
        return None

    def get_out_for_delivery_at(self, obj):
        if obj.out_for_delivery_at:
            return obj.out_for_delivery_at
            # kuwait_date = datetime_from_utc_to_local_new(obj.out_for_delivery_at)
            # formatted_date = obj.out_for_delivery_at.strftime("%b %d, %Y")
            # formatted_time = obj.out_for_delivery_at.strftime("%H:%M %p")
            # return f"{formatted_date} at {formatted_time}"
        return None

    def get_delivered_at(self, obj):
        if obj.delivered_at:
            return obj.delivered_at
            # kuwait_date = datetime_from_utc_to_local_new(obj.delivered_at)
            # formatted_date = obj.delivered_at.strftime("%b %d, %Y")
            # formatted_time = obj.delivered_at.strftime("%H:%M %p")
            # return f"{formatted_date} at {formatted_time}"
        return None

    def get_name(self, obj):
        lang_code = self.context.get("lang_code")
        if lang_code == "ar":
            return obj.product.nameAR
        return obj.product.name

    def get_base_price(self, obj):
        return obj.product.base_price

    def get_discounted_price(self, obj):
        try:
            obj.product.discount
        except ObjectDoesNotExist:
            return None
        return obj.product.discount.discounted_price()

    def get_status(self, obj):
        return obj.get_status_display()

    def get_brand(self, obj):
        return BrandSerializer(obj.product.brand).data

    def get_media(self, obj):
        if obj.product.medias.filter(is_thumbnail=False).exists():
            media = obj.product.medias.filter(is_thumbnail=False).first()
            return EcommProductMediaSerializer(media).data
        return None

    def get_variant_with_value(self, obj):
        var_vals = VariantValues.objects.filter(
            pk__in=obj.product.variant_value_ids()
        )
        return VariantValuesMinSerializer(
            var_vals, many=True, context=self.context).data

    def get_seller_information(self, obj):
        if obj.product.store:
            return SellerListByCategorySerializer(obj.product.store).data
        return None

    def get_status_track(self, obj):
        if obj.orderproductstatustrack.exists:
            order_prod_status_track = obj.orderproductstatustrack.order_by(
                '-created_at')
            return OrderProdStatusTrackSerializer(
                order_prod_status_track, many=True,
                context={'order': obj}).data
        return None


class PaymentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentType
        fields = '__all__'


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'


class OrderStatusTrackSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    updated_by = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()
    updated_at = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    remark = serializers.SerializerMethodField()
    rescheduled_at = serializers.SerializerMethodField()

    class Meta:
        model = OrderStatusTrack
        fields = (
            'id', 'status', 'updated_by', 'created_at', 'updated_at',
            'reason', 'payment_status', 'remark', 'rescheduled_at'
        )

    def get_updated_by(self, obj):
        if obj.updated_by:
            return CustomerSerializer(obj.updated_by).data
        return None

    def get_status(self, obj):
        return obj.get_status_display()

    def get_rescheduled_at(self, obj):
        if obj.rescheduled_at:
            return obj.rescheduled_at
            # kuwait_date = datetime_from_utc_to_local_new(obj.rescheduled_at)
            # formatted_date = obj.rescheduled_at.strftime("%b %d, %Y")
            # formatted_time = obj.rescheduled_at.strftime("%H:%M %p")
            # return f"{formatted_date} at {formatted_time}"
        return None

    def get_created_at(self, obj):
        if obj.created_at:
            return obj.created_at
            # kuwait_date = datetime_from_utc_to_local_new(obj.created_at)
            # formatted_date = obj.created_at.strftime("%b %d, %Y")
            # formatted_time = obj.created_at.strftime("%H:%M %p")
            # return f"{formatted_date} at {formatted_time}"
        return None

    def get_updated_at(self, obj):
        if obj.updated_at:
            return obj.updated_at
            # kuwait_date = datetime_from_utc_to_local_new(obj.updated_at)
            # formatted_date = obj.updated_at.strftime("%b %d, %Y")
            # formatted_time = obj.updated_at.strftime("%H:%M %p")
            # return f"{formatted_date} at {formatted_time}"
        return None

    def get_payment_status(self, obj):
        if obj.order:
            if obj.order.payments.all().filter(status='SU').exists():
                cancelled_op_count = obj.order.orderProducts.filter(
                    status='CA'
                ).count()

                if cancelled_op_count == obj.order.orderProducts.all().count():
                    return "Refunded"
                elif cancelled_op_count > 0:
                    return "Partially Refunded"
                return "Paid"

                # sub_total = obj.order.orderProducts.all().aggregate(
                #     total=Sum(F('product__base_price') * F('quantity'),
                #               output_field=FloatField())).get('total')
                #
                # if obj.order.refunded_price < sub_total and obj.order.refunded_price != 0.0:
                #     return "Partially Refunded"
                # elif obj.order.refunded_price == sub_total and obj.order.refunded_price != 0.0:
                #     return "Refunded"
                # return "Paid"
            return "Failed"
        return "Failed"

    def get_remark(self, obj):
        if obj.updated_at:
            return obj.updated_at
            # kuwait_date = datetime_from_utc_to_local_new(obj.updated_at)
            # formatted_date = obj.updated_at.strftime("%b %d, %Y")
            # formatted_time = obj.updated_at.strftime("%H:%M %p")
            # return f"{formatted_date} at {formatted_time}"
        return None


class OrderProdStatusTrackSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    updated_by = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    payment_reference = serializers.SerializerMethodField()
    rescheduled_at = serializers.SerializerMethodField()

    class Meta:
        model = OrderProductStatusTrack
        fields = (
            'id', 'status', 'created_at', 'updated_at', 'updated_by',
            'payment_status', 'reason', 'payment_reference', 'rescheduled_at'
        )

    def get_rescheduled_at(self, obj):
        if obj.rescheduled_at:
            return obj.rescheduled_at
            # kuwait_date = datetime_from_utc_to_local_new(obj.rescheduled_at)
            # formatted_date = obj.rescheduled_at.strftime("%b %d, %Y")
            # formatted_time = obj.rescheduled_at.strftime("%H:%M %p")
            # return f"{formatted_date} at {formatted_time}"
        return None

    def get_updated_by(self, obj):
        if obj.updated_by:
            return CustomerSerializer(obj.updated_by).data
        return None

    def get_status(self, obj):
        return obj.get_status_display()

    def get_created_at(self, obj):
        if obj.created_at:
            return obj.created_at
            # kuwait_date = datetime_from_utc_to_local_new(obj.created_at)
            # formatted_date = obj.created_at.strftime("%b %d, %Y")
            # formatted_time = obj.created_at.strftime("%H:%M %p")
            # return f"{formatted_date} at {formatted_time}"
        return None

    def get_updated_at(self, obj):
        if obj.updated_at:
            return obj.updated_at
            # kuwait_date = datetime_from_utc_to_local_new(obj.updated_at)
            # formatted_date = obj.updated_at.strftime("%b %d, %Y")
            # formatted_time = obj.updated_at.strftime("%H:%M %p")
            # return f"{formatted_date} at {formatted_time}"
        return None

    def get_payment_status(self, obj):
        if obj.order_product.order:
            if obj.order_product.order.payments.all().filter(status='SU').exists():
                order = obj.order_product.order
                cancelled_op_count = order.orderProducts.filter(
                    status='CA'
                ).count()

                if cancelled_op_count == order.orderProducts.all().count():
                    return "Refunded"
                elif cancelled_op_count > 0:
                    return "Partially Refunded"
                return "Paid"

                # sub_total = obj.order_product.order.orderProducts.all().aggregate(
                #     total=Sum(F('product__base_price') * F('quantity'),
                #               output_field=FloatField())).get('total')
                # order = obj.order_product.order
                # if order.refunded_price < sub_total and order.refunded_price != 0.0:
                #     return "Partially Refunded"
                # elif order.refunded_price == sub_total and order.refunded_price != 0.0:
                #     return "Refunded"
                # return "Paid"
            return "Failed"
        return "Failed"

    def get_payment_reference(self, obj):
        if obj.order_product.order:
            if obj.order_product.order.payments.all().filter(status='SU').exists():
                payment = obj.order_product.order.payments.all().first()
                return payment.ref
        return ""


class OrderDetailSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    serial_no = serializers.SerializerMethodField()
    total_prod_count = serializers.SerializerMethodField()
    date = serializers.SerializerMethodField()
    customer = serializers.SerializerMethodField()
    totalPrice = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    prod_details = serializers.SerializerMethodField()
    out_for_delivery_at = serializers.SerializerMethodField()
    delivered_at = serializers.SerializerMethodField()
    payment_type_details = serializers.SerializerMethodField()
    payment_details = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()
    status_track = serializers.SerializerMethodField()
    unseen_orders_count = serializers.SerializerMethodField()
    coupon = serializers.SerializerMethodField()
    shipping_charge = serializers.SerializerMethodField()
    sub_total = serializers.SerializerMethodField()
    delivered_count = serializers.SerializerMethodField()
    total_after_refund = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            'id', 'status', 'customer',
            'sub_total',
            'totalPrice', 'payment_status',
            'total_prod_count', 'address',
            'serial_no', 'created_at', 'updated_at',
            'discounted_price', 'shipping_charge',
            'refunded_price', 'total_after_refund',
            'date', 'prod_details', 'out_for_delivery_at',
            'delivered_at', 'payment_type_details',
            'payment_details', 'status_track',
            'unseen_orders_count', 'coupon',
            'delivered_count'
        )

    def get_total_after_refund(self, obj):
        if obj.refunded_price > 0:
            user = self.context.get("user")
            return obj.get_totalPrice_with_user(user)
        return "{0:.3f}".format(0.000)

    def get_delivered_count(self, obj):
        user = self.context.get("user")
        if user.is_seller:
            sub_admins = user.seller_sub_admins.all()
            if sub_admins.exists():
                sub_admin = sub_admins.latest('id')
                del_count = obj.orderProducts.filter(
                    status='DEL',
                    product__store=sub_admin.store).distinct().count()
            else:
                del_count = obj.orderProducts.filter(
                    status='DEL',
                    product__store__member=user).distinct().count()
        else:
            del_count = obj.orderProducts.all().filter(
                status='DEL').count()
        return del_count

    def get_sub_total(self, obj):
        user = self.context.get("user")
        return "{0:.3f}".format(obj.get_subtotal_with_user(user))

    def get_shipping_charge(self, obj):
        if obj.coupon and obj.coupon.type == "FS":
            return 0.0
        return settings.SHIPPING_CHARGE

    def get_address(self, obj):
        if obj.address:
            address = obj.address
            return AddressDetailSerializer(address).data
        return None

    def get_payment_details(self, obj):
        if obj.payments.exists():
            payment = obj.payments.all().first()
            return PaymentSerializer(payment).data
        return None

    def get_payment_type_details(self, obj):
        if obj.payments.exists():
            paymentType = obj.payments.all().first().paymentType
            return PaymentTypeSerializer(paymentType).data
        return None

    def get_date(self, obj):
        return obj.created_at

    def get_out_for_delivery_at(self, obj):
        if obj.out_for_delivery_at:
            return obj.out_for_delivery_at
        return None

    def get_delivered_at(self, obj):
        if obj.delivered_at:
            return obj.delivered_at
        return None

    def reduce_order_amount(self, order, deductable_amount):
        order.totalPrice = order.get_totalPrice_without_shipping_charge()
        order.sub_total = order.get_sub_total()
        order.totalPrice -= deductable_amount
        order.sub_total -= deductable_amount

        if order.totalPrice < 0:
            order.totalPrice = 0
        if order.sub_total < 0:
            order.sub_total = 0
        order.totalPrice += settings.SHIPPING_CHARGE
        order.save()

    def order_amount_to_reduce(self, order):
        coupon = order.coupon
        if coupon:
            if order.customer and order.customer.cart.exists():
                cart = order.customer.cart.all().latest('id')
                deductable_amount = 0.0
                if coupon.deductable_amount != 0.0:
                    deductable_amount = coupon.deductable_amount
                elif coupon.deductable_percentage != 0.0:
                    deductable_amount = coupon.get_discounted_price_order(order)
                elif coupon.type == "FS":
                    deductable_amount = 0.0
                if deductable_amount > order.get_sub_total():
                    order.discounted_price = order.get_sub_total()
                else:
                    order.discounted_price = deductable_amount
                order.save()
            elif order.guest_acc and order.guest_acc.cart.exists():
                cart = order.guest_acc.cart.all().latest('id')
                deductable_amount = 0.0
                if coupon.deductable_amount != 0.0:
                    deductable_amount = coupon.deductable_amount
                elif coupon.deductable_percentage != 0.0:
                    deductable_amount = coupon.get_discounted_price_order(self)
                elif coupon.type == "FS":
                    deductable_amount = 0.0

                if deductable_amount > self.get_sub_total():
                    order.discounted_price = self.get_sub_total()
                else:
                    order.discounted_price = deductable_amount
                order.save()
            self.reduce_order_amount(order, order.discounted_price)

    def get_totalPrice(self, obj):
        user = self.context.get("user")
        return obj.get_totalPrice_with_user(user)

    def get_payment_status(self, obj):
        if obj.payments.all().filter(status='SU').exists():
            cancelled_op_count = obj.orderProducts.filter(
                status='CA'
            ).count()

            if cancelled_op_count == obj.orderProducts.all().count():
                return "Refunded"
            elif cancelled_op_count > 0:
                return "Partially Refunded"
            return "Paid"
        return "Failed"

    def get_customer(self, obj):
        if obj.customer:
            return CustomerSerializer(obj.customer).data
        elif obj.guest_acc:
            return GuestAccSerializer(obj.guest_acc).data
        return None

    def get_status(self, obj):
        cancelled_status = [_("Cancelled")]
        in_progress_status = [
            _("Order Placed"), _("Ready For Pickup"),
            _("Picked Up"), _("Out For Delivery"), _("Returned"),
            _("Rescheduled")]

        if obj.get_status_display() in cancelled_status\
                or obj.get_payment_status() == "Failed":
            return _("Cancelled")
        if obj.get_status_display() in in_progress_status:
            return _("In Progress")
        if obj.get_status_display() == _("Delivered"):
            return _(obj.get_status_display())
        return _("In Progress")

    def get_serial_no(self, obj):
        return "#".join([
            "", str(obj.id)
        ])

    def get_total_prod_count(self, obj):
        user = self.context.get("user")
        if user.is_seller:
            sub_admins = user.seller_sub_admins.all()
            if sub_admins.exists():
                sub_admin = sub_admins.latest('id')
                order_prod_count = obj.orderProducts.filter(
                    product__store=sub_admin.store).distinct().count()
            else:
                order_prod_count = obj.orderProducts.filter(
                    product__store__member=user).distinct().count()
        else:
            order_prod_count = obj.orderProducts.all().count()
        return order_prod_count

    def get_prod_details(self, obj):
        if obj.orderProducts.exists:
            order_prods = obj.orderProducts.all()
            user = self.context.get("user")
            if user.is_seller:
                sub_admins = user.seller_sub_admins.all()
                if sub_admins.exists():
                    sub_admin = sub_admins.latest('id')
                    order_prods = order_prods.filter(
                        product__store=sub_admin.store).distinct()
                else:
                    order_prods = order_prods.filter(
                        product__store__member=user).distinct()
            else:
                order_prods = order_prods

            return ProdVariantSerializer(
                order_prods, many=True,
                context={'order': obj}).data
        return None

    def get_status_track(self, obj):
        if obj.orderstatustrack.exists():
            order_status_track = obj.orderstatustrack.order_by('-created_at')
            return OrderStatusTrackSerializer(
                order_status_track, many=True,
                context={'order': obj}).data
        return None

    def get_unseen_orders_count(self, obj):
        user = self.context.get("user")
        if user.is_seller:
            sub_admins = user.seller_sub_admins.all()
            if sub_admins.exists():
                sub_admin = sub_admins.latest('id')
                qs = Order.objects.filter(
                    payments__isnull=False,
                    orderProducts__product__store=sub_admin.store).distinct()
            else:
                qs = Order.objects.filter(
                    payments__isnull=False,
                    orderProducts__product__store__member=user).distinct()
        else:
            qs = Order.objects.filter(payments__isnull=False).distinct()

        order_prod_filter = filter(
            lambda x: x.order_prods_has_prod() is True, qs)
        qs = qs.filter(id__in=list([x.id for x in order_prod_filter]))

        unseen_order_count = qs.filter(~Q(
            pk__in=user.order_views.all().values_list('order_id', flat=True))).count()
        return unseen_order_count


class AddEditAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ('title', 'area_name', 'block', 'street', 'house',
                  'phone', 'country_code', 'state', 'jadda',
                  'floor', 'apartment', 'extra_directions',
                  'lon', 'lat', 'customer', 'customer_default',
                  'country_name', 'area')


class OrderNotificationSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    serial_no = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            'id', 'status', 'serial_no'
        )

    def get_status(self, obj):
        cancelled_status = ["Cancelled", "Declined"]
        in_progress_status = [
            "Order Placed", "Ready For Pickup",
            "Picked Up", "Out For Delivery"]

        if obj.get_status_display() in cancelled_status:
            return "Cancelled"
        if obj.get_status_display() in in_progress_status:
            return "In Progress"
        if obj.get_status_display() == "Delivered":
            return obj.get_status_display()
        return "In Progress"

    def get_serial_no(self, obj):
        return "#".join([
             "", str(obj.id)
        ])