from django.contrib import admin

# Register your models here.
from app.store.models import Store, Country, HomePageItems, HomePageItemValues, \
    SellerPageItems, SellerPageItemValues, SocialMediaURL, Address, City, Commission, InventoryProduct, Inventory, \
    Banner, TopDealsBanner, SellerSubAdmins, Payment, PaymentType


class HomePageItemsAdmin(admin.ModelAdmin):
    model = HomePageItems
    fields = (
        'name', 'nameAR', 'type', 'title_alignment',
        'title_image', 'can_see_all', 'order_for_mob',
        'order_for_web', 'no_of_rows', 'device', 'ordering_id',
        'banner',
    )
    list_display = ("__str__", "ordering_id", "name", 'created_at', 'updated_at')


class HomePageItemValuesAdmin(admin.ModelAdmin):
    model = HomePageItemValues
    list_display = ("__str__", "homepageitem", "created_at", "updated_at")


class SellersPageItemsAdmin(admin.ModelAdmin):
    model = SellerPageItems
    list_display = ("__str__", "ordering_id", "name", "store")


class SellerPageItemValuesAdmin(admin.ModelAdmin):
    model = SellerPageItemValues
    list_display = ("__str__", "sellerpageitem", )


admin.site.register(Store)
admin.site.register(SellerSubAdmins)
admin.site.register(Country)
admin.site.register(HomePageItems, HomePageItemsAdmin)
admin.site.register(HomePageItemValues, HomePageItemValuesAdmin)
admin.site.register(SellerPageItems, SellersPageItemsAdmin)
admin.site.register(SellerPageItemValues, SellerPageItemValuesAdmin)
admin.site.register(SocialMediaURL)
admin.site.register(Address)
admin.site.register(City)
admin.site.register(Commission)
admin.site.register(Banner)
admin.site.register(TopDealsBanner)
admin.site.register(Payment)
admin.site.register(PaymentType)
