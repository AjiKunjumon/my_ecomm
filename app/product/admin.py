from django.contrib import admin

# Register your models here.

from django.contrib import admin
from parler.admin import TranslatableAdmin
from parler.models import TranslatableModel, TranslatedFields

from app.product.models import EcommProduct, Category, EcommProductMedia, Brand, MyModel, Discount, \
    EcommProductRatingandReview, Variant, VariantValues, ProductVariantValue, ProductSpecification, SearchKeyWord, \
    CategoryMedia, SearchKeyWordAR, ProductCollection, ProductCollectionCond, Coupon
from app.store.models import HomePageItemValues, HomePageItems, SellerPageItemValues, InventoryProduct, Inventory


class EcommProductMediaStackedAdmin(admin.StackedInline):
    model = EcommProductMedia
    fields = ("file_data", "order", )
    extra = 0


class EcommProductAdmin(admin.ModelAdmin):
    model = EcommProduct
    fields = (
        "name", "nameAR", "description", "descriptionAR", "sku", "status",
        "parent", "base_price", "category", "isHiddenFromOrder", "store",
        "barCode", "home_page_items", "seller_page_items", "brand", "isTrending",
        "isNew", "is_best_seller", "variant_values", "overall_rating",
        "searched_with_keywords", "additional_search_keywords",
        "order_count", "is_out_of_stock", "is_exclusive_deal", "is_new_arrival",
        "is_media_uploaded", "size_guide", "size_guide_ar", 'available_from',
        'discounted_price',
    )
    search_fields = ("name", "pk", )
    list_filter = ("isHiddenFromOrder", "category", "brand", "parent", "status",
                   "is_media_uploaded", "store")
    list_display = (
        "id", "name", "category", "brand", "created_at", "updated_at",
        "sku"
    )
    inlines = (EcommProductMediaStackedAdmin, )

    def save_model(self, request, obj, form, change):
        if obj.pk is not None:
            if obj.medias.exists():
                prod_media = obj.medias.all().first().file_data
            else:
                prod_media = None
            # if form.cleaned_data["home_page_items"].exists():
            #     for hmi in form.cleaned_data["home_page_items"].all():
            #         hmpi, created = HomePageItemValues.objects.update_or_create(
            #             homepageitem=hmi, object_id=obj.pk, object_type="Product",
            #             defaults={"name": obj.name, "nameAR": obj.nameAR,
            #                       "base_price": obj.base_price,
            #                       "discounted_price": obj.discounted_price,
            #                       "image": prod_media}
            #         )
            #
            # if form.cleaned_data["seller_page_items"].exists():
            #     for spi in form.cleaned_data["seller_page_items"].all():
            #         spim, created = SellerPageItemValues.objects.update_or_create(
            #             sellerpageitem=spi, object_id=obj.pk, object_type="Product",
            #             defaults={"name": obj.name, "nameAR": obj.nameAR,
            #                       "base_price": obj.base_price,
            #                       "discounted_price": obj.discounted_price,
            #                       "image": prod_media}
            #         )
            if form.cleaned_data["variant_values"].exists():
                for variant_val in form.cleaned_data["variant_values"].all():
                    prv, created = ProductVariantValue.objects.get_or_create(
                        product=obj,
                        variant_value=variant_val
                    )
        super(EcommProductAdmin, self).save_model(request, obj, form, change)


class MyModelAdmin(admin.ModelAdmin):
    model = MyModel
    fields = (
        "id", "title",
    )


class TranslatableSite(TranslatableModel, EcommProduct):
    class Meta:
        proxy = True

    translations = TranslatedFields()


class NewSiteAdmin(TranslatableAdmin):
    pass


class CategoryAdmin(admin.ModelAdmin):
    model = Category
    fields = (
        "name", "nameAR", "ordering_id", "parent", "image",
        "image_width", "image_height", "home_page_items",
        "seller_page_items", "home_page_thumbnail",
        "home_page_thumbnail_ar",  "home_page_icon",
        "status"
    )
    search_fields = ("name", "pk", )
    list_filter = ("parent", "status")
    list_display = (
        "id", "name", "image", "parent", "status", "ordering_id"
    )

    def assign_category_to_item(self, item):
        def assign_to_item(modeladmin, request, queryset):
            for obj in queryset:
                if item not in obj.home_page_items.all():
                    obj.home_page_items.add(item)
                    obj.save()
                HomePageItemValues.objects.update_or_create(
                    homepageitem=item,
                    name=obj.name, nameAR=obj.nameAR,
                    image=obj.image,
                    object_id=obj.pk, object_type="Category"
                )

        assign_to_item.short_description = "Assign selected to %s homepageitem" % item
        assign_to_item.__name__ = 'assign_to_user_{0}'.format(item.id)

        return assign_to_item

    def get_actions(self, request):
        actions = super(CategoryAdmin, self).get_actions(request)

        for item in HomePageItems.objects.all():
            action = self.assign_category_to_item(item)
            actions[action.__name__] = (action,
                                        action.__name__,
                                        action.short_description)

        return actions

    def save_model(self, request, obj, form, change):
        if obj.pk is not None:
            seller_page_items = obj.seller_page_items.all()
            for spi in seller_page_items:
                SellerPageItemValues.objects.update_or_create(
                    homepageitem=spi,
                    name=obj.name, nameAR=obj.nameAR,
                    image=obj.image,
                    object_id=obj.pk, object_type="Category"
                )
        super(CategoryAdmin, self).save_model(request, obj, form, change)


class ProductVariantValueAdmin(admin.ModelAdmin):
    model = ProductVariantValue
    fields = (
        "variant_value", "product"
    )
    search_fields = ("name", "pk", )
    list_filter = ("product", "product__category")
    list_display = (
        "__str__", "product_id",
    )


class ProductSpecificationAdmin(admin.ModelAdmin):
    model = ProductSpecification
    fields = (
        "value", "valueAR", "specification", "specificationAR",
        "product"
    )
    search_fields = ("product__name", "pk", )
    list_filter = ("product",)
    list_display = (
        "__str__", "product_id"
    )


class BrandAdmin(admin.ModelAdmin):
    model = Brand
    fields = (
        "name", "nameAR", "image", "image_width", "image_height",
        "is_top_brand", "selling_categories"
    )
    search_fields = ("product__name", "pk", )
    list_filter = ("is_top_brand",)
    list_display = (
        "__str__", "is_top_brand"
    )


class SearchKeyWordAdmin(admin.ModelAdmin):
    model = SearchKeyWord
    fields = (
         "keyword", "results_count", "searched_for",
    )
    search_fields = ("keyword", "pk", )
    list_filter = ("searched_for",)
    list_display = (
        "__str__", "created_at", "updated_at"
    )


class SearchKeyWordARAdmin(admin.ModelAdmin):
    model = SearchKeyWordAR
    fields = (
         "keyword_ar", "results_count", "searched_for",
    )
    search_fields = ("keyword_ar", "pk", )
    list_filter = ("searched_for",)
    list_display = (
        "__str__", "created_at", "updated_at"
    )


class CategoryMediaAdmin(admin.ModelAdmin):
    model = CategoryMedia
    list_filter = ("category",)
    list_display = (
         "category",
    )


admin.site.register(EcommProduct, EcommProductAdmin)
admin.site.register(ProductVariantValue, ProductVariantValueAdmin)
admin.site.register(EcommProductMedia)
admin.site.register(Category, CategoryAdmin)
admin.site.register(CategoryMedia, CategoryMediaAdmin)
admin.site.register(Brand, BrandAdmin)
admin.site.register(MyModel, NewSiteAdmin)
admin.site.register(Discount)
admin.site.register(EcommProductRatingandReview)
admin.site.register(Variant)
admin.site.register(VariantValues)
admin.site.register(ProductSpecification, ProductSpecificationAdmin)
admin.site.register(SearchKeyWord, SearchKeyWordAdmin)
admin.site.register(SearchKeyWordAR, SearchKeyWordARAdmin)
admin.site.register(Inventory)
admin.site.register(InventoryProduct)
admin.site.register(ProductCollection)
admin.site.register(ProductCollectionCond)
admin.site.register(Coupon)

