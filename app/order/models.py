from creditcards.models import CardNumberField, CardExpiryField, SecurityCodeField
from django.conf import settings
from django.core.validators import MaxLengthValidator
from django.db import models

# Create your models here.
from django.db.models import CASCADE, Sum, FloatField, F, SET_NULL, Case, When
from django.utils.translation import ugettext_lazy as _
from phonenumbers import national_significant_number


class Order(models.Model):
    status_choices = (
        ('OP', _('Order Placed')),
        ('RFP', _('Ready For Pickup')),
        ('PU', _('Picked Up')),
        ('OFD', _('Out For Delivery')),
        ('RET', _('Returned')),
        ('RES', _('Rescheduled')),
        ('RFD', _('Refunded')),
        ('CA', _('Cancelled')),
        ('DEL', _('Delivered')),
        ('DEC', _('Declined')),
        ('TBS', _('Transit By Seller')),
        ('TBFC', _('Transit By BFC')),
        ('RBFC', _('Ready For BFC'))
    )
    status = models.CharField(
        max_length=4, default='OP',
        choices=status_choices)

    customer = models.ForeignKey(
        'authentication.Member', related_name='orders',
        blank=True, null=True,
        on_delete=CASCADE
    )
    guest_acc = models.ForeignKey(
        'authentication.GuestAccount', related_name='orders',
        blank=True, null=True,
        on_delete=CASCADE
    )
    fcm_device = models.ForeignKey(
        'fcm_django.FCMDevice', related_name='orders',
        blank=True, null=True,
        on_delete=SET_NULL
    )
    address = models.ForeignKey(
        'store.Address', related_name='orders',
        blank=True, null=True,
        on_delete=SET_NULL
    )
    isDelivery = models.BooleanField(default=False)
    deliveryDateTime = models.DateTimeField(blank=True, null=True)
    deliveryCost = models.FloatField(default=0.0)
    sub_total = models.FloatField(default=0.0)
    totalPrice = models.FloatField(default=0.0)
    refunded_price = models.FloatField(default=0.0)
    total_after_refund = models.FloatField(default=0.0)

    discounted_price = models.FloatField(default=0.0)
    shipping_charge = models.FloatField(default=0.0)
    isDeleted = models.BooleanField(default=False)
    cancellationReason = models.CharField(
        max_length=255, blank=True, null=True)
    serialNo = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    out_for_delivery_at = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)

    rescheduled_at = models.DateTimeField(blank=True, null=True)
    rescheduled_reason = models.CharField(
        max_length=255, blank=True, null=True)
    ready_for_pickup_remarks = models.CharField(
        max_length=255, blank=True, null=True)

    coupon = models.ForeignKey(
        'product.Coupon', related_name='orders',
        blank=True, null=True,
        on_delete=SET_NULL
    )

    def __str__(self):
        return ' - '.join(
            [str(self.pk), str(self.created_at)]
        )

    def get_sub_total(self):
        if self.orderProducts.exists():
            price_gt_zero = self.orderProducts.all().filter(
                price__gt=0
            )
            if price_gt_zero.count() > 0 and (price_gt_zero.count() == self.orderProducts.count()):
                sub_total = self.orderProducts.all().aggregate(
                    sub_total=Sum(F('price') * F('quantity'),
                                  output_field=FloatField())).get('sub_total')
            else:
                sub_total = self.orderProducts.all().aggregate(
                    sub_total=Sum(Case(When(
                        product__discount__isnull=True,
                        then=F('product__base_price') * F('quantity')),
                        default=(F('product__base_price')
                                 - (F('product__base_price')
                                    * F('product__discount__percentage')) / 100) * F('quantity'),
                        output_field=FloatField()))).get('sub_total')
            if sub_total:
                self.sub_total = sub_total
                self.save()
            else:
                sub_total = 0.0
            return sub_total
        return 0.0

    def get_subtotal_with_user(self, user):
        if self.orderProducts.exists():
            if self.orderProducts.exists:
                order_prods = self.orderProducts.all()
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

            price_gt_zero = order_prods.filter(
                price__gt=0
            )
            if price_gt_zero.count() > 0 and (price_gt_zero.count() == order_prods.count()):
                sub_total = order_prods.aggregate(
                    sub_total=Sum(F('price') * F('quantity'),
                                  output_field=FloatField())).get('sub_total')
            else:
                sub_total = order_prods.aggregate(
                    sub_total=Sum(Case(When(
                        product__discount__isnull=True,
                        then=F('product__base_price') * F('quantity')),
                        default=(F('product__base_price')
                                 - (F('product__base_price')
                                    * F('product__discount__percentage')) / 100) * F('quantity'),
                        output_field=FloatField()))).get('sub_total')

            if sub_total:
                self.sub_total = sub_total
                self.save()
            else:
                sub_total = 0.0
            return sub_total
        return 0.0

    def get_totalPrice_without_shipping_charge(self):
        if self.orderProducts.exists():
            price_gt_zero = self.orderProducts.all().filter(
                price__gt=0
            )
            if price_gt_zero.count() > 0 and (price_gt_zero.count() == self.orderProducts.count()):
                sub_total = self.orderProducts.all().aggregate(
                    sub_total=Sum(F('price') * F('quantity'),
                                  output_field=FloatField())).get('sub_total')
            else:
                sub_total = self.orderProducts.all().aggregate(
                    sub_total=Sum(Case(When(
                        product__discount__isnull=True,
                        then=F('product__base_price') * F('quantity')),
                        default=(F('product__base_price')
                                 - (F('product__base_price')
                                    * F('product__discount__percentage')) / 100) * F('quantity'),
                        output_field=FloatField()))).get('sub_total')

            # if obj.address:
            #     shipping_charge = obj.address.shipping_charge
            # else:
            #     shipping_charge = obj.shipping_charge
            if sub_total:
                discounted_total = sub_total
                self.sub_total = discounted_total
                self.totalPrice = discounted_total
                self.save()
                return self.totalPrice
            return 0.0
        return 0.0

    def reduce_order_amount(self, deductable_amount):
        self.totalPrice = self.get_totalPrice_without_shipping_charge()
        self.sub_total = self.get_sub_total()
        self.totalPrice -= deductable_amount
        self.sub_total -= deductable_amount

        if self.totalPrice < 0:
            self.totalPrice = 0
        if self.sub_total < 0:
            self.sub_total = 0
        self.totalPrice += settings.SHIPPING_CHARGE
        self.save()

    def order_amount_to_reduce(self):
        coupon = self.coupon
        if coupon:
            if self.customer and self.customer.cart.exists():
                cart = self.customer.cart.all().latest('id')
                deductable_amount = 0.0
                if coupon.deductable_amount != 0.0:
                    deductable_amount = coupon.deductable_amount
                elif coupon.deductable_percentage != 0.0:
                    deductable_amount = coupon.get_discounted_price_order(self)
                elif coupon.type == "FS":
                    deductable_amount = 0.0

                if deductable_amount > self.get_sub_total():
                    self.discounted_price = self.get_sub_total()
                else:
                    self.discounted_price = deductable_amount
                self.save()
            elif self.guest_acc and self.guest_acc.cart.exists():
                cart = self.guest_acc.cart.all().latest('id')
                deductable_amount = 0.0
                if coupon.deductable_amount != 0.0:
                    deductable_amount = coupon.deductable_amount
                elif coupon.deductable_percentage != 0.0:
                    deductable_amount = coupon.get_discounted_price_order(self)
                elif coupon.type == "FS":
                    deductable_amount = 0.0

                if deductable_amount > self.get_sub_total():
                    self.discounted_price = self.get_sub_total()
                else:
                    self.discounted_price = deductable_amount
                self.save()
            self.reduce_order_amount(self.discounted_price)

    def get_payment_status(self):
        if self.payments.all().filter(status='SU').exists():
            cancelled_op_count = self.orderProducts.filter(
                status='CA'
            ).count()

            if cancelled_op_count == self.orderProducts.all().count():
                return "Refunded"
            elif cancelled_op_count > 0:
                return "Partially Refunded"
            return "Paid"
        return "Failed"

    def get_totalPrice_float(self):
        if self.orderProducts.exists():
            price_gt_zero = self.orderProducts.all().filter(
                price__gt=0
            )
            if price_gt_zero.count() > 0 and (price_gt_zero.count() == self.orderProducts.count()):
                sub_total = self.orderProducts.all().aggregate(
                    sub_total=Sum(F('price') * F('quantity'),
                                  output_field=FloatField())).get('sub_total')
            else:
                sub_total = self.orderProducts.all().aggregate(
                    sub_total=Sum(Case(When(
                        product__discount__isnull=True,
                        then=F('product__base_price') * F('quantity')),
                        default=(F('product__base_price')
                                 - (F('product__base_price')
                                    * F('product__discount__percentage')) / 100) * F('quantity'),
                        output_field=FloatField()))).get('sub_total')

            if sub_total is None:
                sub_total = 0.0

            shipping_charge = settings.SHIPPING_CHARGE

            if self.coupon:
                if self.coupon.type == "FS":
                    shipping_charge = 0.0
                    discounted_total = sub_total + shipping_charge
                    self.sub_total = sub_total
                    self.totalPrice = discounted_total
                    self.save()
                else:
                    self.order_amount_to_reduce()
            else:
                discounted_total = sub_total + shipping_charge
                self.sub_total = sub_total
                self.totalPrice = discounted_total
                self.save()

        return self.totalPrice

    def get_totalPrice(self):
        if self.orderProducts.exists():
            price_gt_zero = self.orderProducts.all().filter(
                price__gt=0
            )
            if price_gt_zero.count() > 0 and (price_gt_zero.count() == self.orderProducts.count()):
                sub_total = self.orderProducts.all().aggregate(
                    sub_total=Sum(F('price') * F('quantity'),
                                  output_field=FloatField())).get('sub_total')
            else:
                sub_total = self.orderProducts.all().aggregate(
                    sub_total=Sum(Case(When(
                        product__discount__isnull=True,
                        then=F('product__base_price') * F('quantity')),
                        default=(F('product__base_price')
                                 - (F('product__base_price')
                                    * F('product__discount__percentage')) / 100) * F('quantity'),
                        output_field=FloatField()))).get('sub_total')

            if sub_total is None:
                sub_total = 0.0

            shipping_charge = settings.SHIPPING_CHARGE

            if self.coupon:
                if self.coupon.type == "FS":
                    shipping_charge = 0.0
                    discounted_total = sub_total + shipping_charge
                    self.sub_total = sub_total
                    self.totalPrice = discounted_total
                    self.save()
                else:
                    self.order_amount_to_reduce()
            else:
                discounted_total = sub_total + shipping_charge
                self.sub_total = sub_total
                self.totalPrice = discounted_total
                self.save()
            return "{0:.3f}".format(self.totalPrice)
        return "{0:.3f}".format(0.000)

    def get_totalPrice_with_user(self, user):
        if self.orderProducts.exists():
            if self.orderProducts.exists:
                order_prods = self.orderProducts.all()
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

            price_gt_zero = order_prods.filter(
                price__gt=0
            )
            if price_gt_zero.count() > 0 and (price_gt_zero.count() == order_prods.count()):
                sub_total = order_prods.aggregate(
                    sub_total=Sum(F('price') * F('quantity'),
                                  output_field=FloatField())).get('sub_total')
            else:
                sub_total = order_prods.aggregate(
                    sub_total=Sum(Case(When(
                        product__discount__isnull=True,
                        then=F('product__base_price') * F('quantity')),
                        default=(F('product__base_price')
                                 - (F('product__base_price')
                                    * F('product__discount__percentage')) / 100) * F('quantity'),
                        output_field=FloatField()))).get('sub_total')

            if sub_total is None:
                sub_total = 0.0

            shipping_charge = settings.SHIPPING_CHARGE

            if not user.is_seller:
                if self.coupon:
                    if self.coupon.type == "FS":
                        shipping_charge = 0.0
                        discounted_total = sub_total + shipping_charge
                        self.sub_total = sub_total
                        self.totalPrice = discounted_total
                        self.save()
                        if self.refunded_price > 0:
                            discounted_total = discounted_total - self.refunded_price
                        self.sub_total = sub_total
                        self.totalPrice = discounted_total
                        self.save()
                    else:
                        self.order_amount_to_reduce()
                else:
                    discounted_total = sub_total + shipping_charge
                    self.sub_total = sub_total
                    self.totalPrice = discounted_total
                    self.save()
                    if self.refunded_price > 0:
                        discounted_total = discounted_total - self.refunded_price
                    self.sub_total = sub_total
                    self.totalPrice = discounted_total
                    self.save()
                return "{0:.3f}".format(self.totalPrice)
            else:
                if self.coupon:
                    if self.coupon.type == "FS":
                        shipping_charge = 0.0
                        discounted_total = sub_total + shipping_charge
                        self.sub_total = sub_total
                        self.totalPrice = discounted_total
                        self.save()
                    else:
                        self.order_amount_to_reduce()
                else:
                    discounted_total = sub_total + shipping_charge
                    self.sub_total = sub_total
                    self.totalPrice = discounted_total
                    self.save()
                discounted_total = sub_total
                if self.refunded_price > 0:
                    discounted_total = discounted_total - self.refunded_price
                return "{0:.3f}".format(discounted_total)
        return "{0:.3f}".format(0.000)

    def get_seller_ids(self):
        if self.orderProducts.exists():
            seller_id_list = self.orderProducts.all().values_list(
                'product__store__id', flat=True).distinct()
            return seller_id_list
        return []

    def order_prods_has_prod(self):
        if self.orderProducts.exists():
            no_prod_count = self.orderProducts.all().filter(
                product__isnull=True
            ).count()
            return no_prod_count == 0
        return False

    def get_total_prod_count(self):
        return self.orderProducts.all().count()

    def get_phone_for_delicon(self):
        if self.address.get_phone_for_delicon() == "":
            if self.customer.phone != "" and self.customer.phone is not None:
                # phone_string = "".join([
                #     str(national_significant_number(self.customer.phone))
                # ])
                return str(national_significant_number(self.customer.phone))
            return ""
        return self.address.get_phone_for_delicon()


class OrderStatusTrack(models.Model):
    status_choices = (
        ('OP', _('Order Placed')),
        ('RFP', _('Ready For Pickup')),
        ('PU', _('Picked Up')),
        ('OFD', _('Out For Delivery')),
        ('RET', _('Returned')),
        ('RES', _('Rescheduled')),
        ('RFD', _('Refunded')),
        ('CA', _('Cancelled')),
        ('DEL', _('Delivered')),
        ('DEC', _('Declined')),
        ('TBS', _('Transit By Seller')),
        ('TBFC', _('Transit By BFC')),
        ('RBFC', _('Ready For BFC'))
    )
    status = models.CharField(
        max_length=4, default='OP',
        choices=status_choices)
    order = models.ForeignKey(
        'order.Order', related_name='orderstatustrack',
        blank=True, null=True,
        on_delete=models.SET_NULL
    )
    updated_by = models.ForeignKey(
        'authentication.Member', related_name='orderstatustrack',
        blank=True, null=True,
        on_delete=CASCADE
    )
    reason = models.CharField(
        max_length=255, blank=True, null=True)

    rescheduled_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return ' - '.join(
            [str(self.pk), str(self.created_at)]
        )


class OrderProduct(models.Model):
    status_choices = (
        ('OP', 'Order Placed'),
        ('RFP', 'Ready For Pickup'),
        ('PU', 'Picked Up'),
        ('OFD', 'Out For Delivery'),
        ('RET', 'Returned'),
        ('RES', 'Rescheduled'),
        ('RFD', 'Refunded'),
        ('CA', 'Cancelled'),
        ('DEL', 'Delivered'),
        ('DEC', 'Declined'),
        ('TBS', 'Transit By Seller'),
        ('TBFC', 'Transit By BFC'),
        ('RBFC', 'Ready For BFC')
    )
    status = models.CharField(
        max_length=4, default='OP',
        choices=status_choices)

    product = models.ForeignKey(
        'product.EcommProduct', related_name='orderProducts',
        blank=True, null=True,
        on_delete=models.SET_NULL
    )
    order = models.ForeignKey(
        'order.Order', related_name='orderProducts',
        blank=True, null=True,
        on_delete=models.SET_NULL
    )
    inventoryPrice = models.FloatField(default=0.0)
    price = models.FloatField(default=0.0)
    salesPercentage = models.FloatField(
        default=0.0, blank=True, null=True)
    quantity = models.IntegerField(default=0)
    note = models.TextField(blank=True, null=True)
    isDeleted = models.BooleanField(default=False)
    cancellationReason = models.CharField(
        max_length=255, blank=True, null=True)

    cancelled_qty = models.IntegerField(default=0)
    specific_qty_cancellationReason = models.CharField(
        max_length=255, blank=True, null=True)

    prodVariantValues = models.ManyToManyField(
        'product.ProductVariantValue', related_name='orderProducts',
        blank=True
    )

    prdParentId = models.IntegerField(default=0)
    prdParentName = models.CharField(
        max_length=255, blank=True, null=True)
    prdParentNameAR = models.CharField(
        max_length=255, blank=True, null=True)
    prdId = models.IntegerField(default=0)
    prdName = models.CharField(
        max_length=255, blank=True, null=True)
    prdNameAR = models.CharField(
        max_length=255, blank=True, null=True)

    orderId = models.IntegerField(default=0)
    serialNo = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    out_for_delivery_at = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)

    rescheduled_at = models.DateTimeField(blank=True, null=True)
    rescheduled_reason = models.CharField(
        max_length=255, blank=True, null=True)
    ready_for_pickup_remarks = models.CharField(
        max_length=255, blank=True, null=True)

    returned_reason = models.CharField(
        max_length=255, blank=True, null=True)
    declined_reason = models.CharField(
        max_length=255, blank=True, null=True)

    def __str__(self):
        if self.order:
            return ' - '.join(
                [str(self.created_at), str(self.order.id)]
            )
        return ' - '.join(
            [str(self.created_at), str(self.id)]
        )


class OrderProductStatusTrack(models.Model):
    status_choices = (
        ('OP', _('Order Placed')),
        ('RFP', _('Ready For Pickup')),
        ('PU', _('Picked Up')),
        ('OFD', _('Out For Delivery')),
        ('RET', _('Returned')),
        ('RES', _('Rescheduled')),
        ('RFD', _('Refunded')),
        ('CA', _('Cancelled')),
        ('DEL', _('Delivered')),
        ('DEC', _('Declined')),
        ('TBS', _('Transit By Seller')),
        ('TBFC', _('Transit By BFC')),
        ('RBFC', _('Ready For BFC'))
    )
    status = models.CharField(
        max_length=4, default='OP',
        choices=status_choices)
    order_product = models.ForeignKey(
        'order.OrderProduct', related_name='orderproductstatustrack',
        blank=True, null=True,
        on_delete=models.SET_NULL
    )
    updated_by = models.ForeignKey(
        'authentication.Member', related_name='orderproductstatustrack',
        blank=True, null=True,
        on_delete=CASCADE
    )
    reason = models.CharField(
        max_length=255, blank=True, null=True)

    rescheduled_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return ' - '.join(
            [str(self.pk), str(self.created_at)]
        )


class CancelledOrderProduct(models.Model):
    order_product = models.ForeignKey(
        'order.OrderProduct', related_name='cancelled_orderProducts',
        blank=True, null=True,
        on_delete=models.CASCADE
    )

    cancelled_qty = models.IntegerField(default=0)
    qty_cancellationReason = models.CharField(
        max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.order_product:
            return ' - '.join(
                [str(self.created_at), str(self.order_product.id)]
            )
        return ' - '.join(
            [str(self.created_at), str(self.id)]
        )


class Cart(models.Model):
    customer = models.ForeignKey(
        'authentication.Member', related_name='cart',
        blank=True, null=True,
        on_delete=CASCADE
    )
    guest_acc = models.ForeignKey(
        'authentication.GuestAccount', related_name='cart',
        blank=True, null=True,
        on_delete=CASCADE
    )
    address = models.ForeignKey(
        'store.Address', related_name='cart',
        blank=True, null=True,
        on_delete=CASCADE
    )
    isDelivery = models.BooleanField(default=False)
    deliveryDateTime = models.DateTimeField(blank=True, null=True)
    deliveryCost = models.FloatField(default=0.0)
    totalPrice = models.FloatField(default=0.0)
    discounted_price = models.FloatField(default=0.0)
    shipping_charge = models.FloatField(default=0.0)
    isDeleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.customer:
            return ' - '.join(
                [str(self.pk),
                 self.customer.first_name,
                 str(self.created_at)]
            )
        return ' - '.join(
            [str(self.pk), str(self.created_at)]
        )


class CartProduct(models.Model):
    product = models.ForeignKey(
        'product.EcommProduct', related_name='cartProducts',
        blank=True, null=True,
        on_delete=models.SET_NULL
    )
    cart = models.ForeignKey(
        'order.Cart', related_name='cartProducts',
        blank=True, null=True,
        on_delete=models.SET_NULL
    )
    inventoryPrice = models.FloatField(default=0.0)
    price = models.FloatField(default=0.0)
    salesPercentage = models.FloatField(
        default=0.0, blank=True, null=True)
    quantity = models.IntegerField(default=0)
    note = models.TextField(blank=True, null=True)
    isDeleted = models.BooleanField(default=False)
    prodVariantValues = models.ManyToManyField(
        'product.ProductVariantValue', related_name='cartProducts',
        blank=True
    )

    prdParentId = models.IntegerField(default=0)
    prdParentName = models.CharField(
        max_length=255, blank=True, null=True)
    prdParentNameAR = models.CharField(
        max_length=255, blank=True, null=True)
    prdId = models.IntegerField(default=0)
    prdName = models.CharField(
        max_length=255, blank=True, null=True)
    prdNameAR = models.CharField(
        max_length=255, blank=True, null=True)
    cartId = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.cart:
            return ' - '.join(
                [str(self.created_at), str(self.cart.id)]
            )
        return ' - '.join(
            [str(self.created_at), str(self.id)]
        )


class Card(models.Model):
    customer = models.ForeignKey(
        'authentication.Member', related_name='card',
        blank=True, null=True,
        on_delete=CASCADE
    )
    card_num = CardNumberField(_('card number'))
    expiry_date = CardExpiryField(_('expiration date'))
    cvv_num = SecurityCodeField(_('security code'))
    is_saved = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.customer:
            return ' - '.join(
                [str(self.pk), self.customer.__str__(),
                 str(self.created_at)]
            )
        return ' - '.join(
            [str(self.pk), str(self.created_at)]
        )


class OrderViews(models.Model):
    order = models.ForeignKey(
        "order.Order",
        related_name="order_views",
        on_delete=CASCADE)
    member = models.ForeignKey(
        "authentication.Member",
        related_name="order_views",
        on_delete=CASCADE,
        blank=True, null=True)
    no_of_views = models.PositiveIntegerField(default=0)

    device_id = models.CharField(
        blank=True, null=True, db_index=True,
        max_length=150
    )
    registration_id = models.TextField(blank=True, null=True)
    fcm_device_id = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("id", )

    def __str__(self):
        if self.order:
            return self.order.__str__()
        return str(self.pk)