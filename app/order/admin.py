from django.contrib import admin

# Register your models here.
from app.order.models import Order, OrderProduct, CancelledOrderProduct, OrderStatusTrack, OrderProductStatusTrack, \
    OrderViews, Cart


class OrderAdmin(admin.ModelAdmin):
    model = Order
    fields = (
        'status', 'customer', 'address', 'isDelivery',
        'totalPrice', 'isDeleted', 'cancellationReason',
        'serialNo', 'refunded_price', 'total_after_refund',
        'out_for_delivery_at', 'delivered_at'
    )
    readonly_fields = ('created_at', 'updated_at')
    search_fields = ("product__name", "pk",)
    list_filter = ("isDeleted", "status")
    list_display = (
        "__str__", "status", "created_at", "updated_at"
    )


class OrderProdAdmin(admin.ModelAdmin):
    model = OrderProduct
    fields = (
        'status', 'order', 'product', 'quantity'
    )
    readonly_fields = ('created_at', 'updated_at')
    search_fields = ("product__name", "pk",)
    list_filter = ("isDeleted", "status", "order", "product")
    list_display = (
        "__str__", "status", "created_at", "updated_at", "order", "product"
    )


class OrderProdStatTrackAdmin(admin.ModelAdmin):
    model = OrderProductStatusTrack
    list_display = (
        "__str__", "order_product_id", "created_at", "updated_at"
    )


admin.site.register(Order, OrderAdmin)
admin.site.register(OrderProduct, OrderProdAdmin)
admin.site.register(OrderStatusTrack)
admin.site.register(OrderProductStatusTrack, OrderProdStatTrackAdmin)
admin.site.register(CancelledOrderProduct)
admin.site.register(OrderViews)
admin.site.register(Cart)

