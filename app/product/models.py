from django.core.exceptions import ObjectDoesNotExist
from django.db import models

# Create your models here.
from django.db.models import CASCADE, Sum, F, Avg, Count, Q
from django.utils.timezone import now
from parler.models import TranslatableModel, TranslatedFields

from django.utils.translation import gettext as _

from app.authentication.models import Member
from app.order.models import Order
from app.product.managers import CategoryQuerySet
from app.store.models import InventoryProduct
from app.utilities.helpers import convert_date_time_to_kuwait_string, datetime_from_utc_to_local_new


class EcommProduct(models.Model):
    STATUS_CHOICES = (
        ('AC', 'Active'),
        ('INR', 'InReview'),
        ('DR', 'Draft'),
        ('DE', 'Declined')
    )
    status = models.CharField(
        max_length=3, default='INR',
        choices=STATUS_CHOICES)

    name = models.CharField(
        max_length=255, blank=True, null=True)
    nameAR = models.CharField(
        max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    descriptionAR = models.TextField(blank=True, null=True)
    size_guide = models.TextField(blank=True, null=True)
    size_guide_ar = models.TextField(blank=True, null=True)
    sku = models.CharField(max_length=255, blank=True, null=True)
    parent = models.ForeignKey('self', related_name='children',
                               blank=True, null=True, on_delete=CASCADE)
    category = models.ForeignKey(
        'product.Category', related_name='products',
        on_delete=CASCADE, blank=True, null=True)
    isHiddenFromOrder = models.BooleanField(default=False)

    isTrending = models.BooleanField(default=False)
    isNew = models.BooleanField(default=False)
    is_best_seller = models.BooleanField(default=False)
    is_out_of_stock = models.BooleanField(default=False)
    is_exclusive_deal = models.BooleanField(default=False)
    is_new_arrival = models.BooleanField(default=False)

    order_count = models.PositiveIntegerField(default=0)
    trending_count_field = models.PositiveIntegerField(
        default=0, blank=True, null=True)
    selling_count_field = models.PositiveIntegerField(
        default=0, blank=True, null=True)
    view_count_field = models.PositiveIntegerField(
        default=0, blank=True, null=True)

    store = models.ForeignKey('store.Store', related_name='products',
                              blank=True, null=True, on_delete=CASCADE)
    barCode = models.CharField(
        max_length=255, unique=True, blank=True, null=True)
    base_price = models.FloatField(default=0.000)
    discounted_price = models.FloatField(default=0.000)
    overall_rating = models.FloatField(default=0.0)

    home_page_items = models.ManyToManyField(
        "store.HomePageItems", related_name="products",
        blank=True, default=None)

    seller_page_items = models.ManyToManyField(
        "store.SellerPageItems", related_name="products",
        blank=True, default=None)

    brand = models.ForeignKey(
        'product.Brand', related_name='products', on_delete=CASCADE,
        blank=True, null=True)

    variant_values = models.ManyToManyField(
        "product.VariantValues", related_name="products",
        blank=True, default=None)

    additional_search_keywords = models.ManyToManyField(
        "product.SearchKeyWord", related_name="products_additional_search",
        blank=True, default=None)

    additional_search_keywords_ar = models.ManyToManyField(
        "product.SearchKeyWordAR", related_name="products_additional_search_ar",
        blank=True, default=None)

    searched_with_keywords = models.ManyToManyField(
        "product.SearchKeyWord", related_name="products",
        blank=True, default=None)

    is_media_uploaded = models.BooleanField(default=False)

    decline_reason = models.TextField(
        max_length=255, blank=True, null=True)

    available_from = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    important = models.BooleanField(default=False)
    thumbnail_image = models.ImageField(
        upload_to='ecomm_products/medias', blank=True, null=True
    )

    def __str__(self):
        if self.name:
            return "-".join([self.name, str(self.id)])
        return str(self.id)

    class Meta:
        ordering = ('-id',)

    def owner(self):
        if self.store.member:
            return self.store.member
        return None

    def is_prod_avail_now(self):
        conds = [self.status == 'AC',
                 (self.available_from and
                  self.available_from <= now())]
        filter__false_conds = [x for x in conds if x is False]
        if len(filter__false_conds) >= 1:
            return False
        return True

    def get_name(self):
        var_vals_list = VariantValues.objects.filter(
            pk__in=self.variant_value_ids()
        ).values_list('value', flat=True)
        var_string = ",".join(list(var_vals_list))
        if self.name and self.name != "":
            return "".join([self.name, "-", var_string])
        return var_string

    def get_name_AR(self):
        var_vals_list = VariantValues.objects.filter(
            pk__in=self.variant_value_ids()
        ).values_list('valueAR', flat=True)
        var_string = ",".join(list(var_vals_list))
        if self.nameAR and self.nameAR != "":
            return "".join([self.nameAR, "-", var_string])
        return var_string

    def get_variants(self):
        variant_list = VariantValues.objects.filter(
            pk__in=self.variant_value_ids()
        ).values('variant')
        return variant_list

    def get_variant_values(self, variant):
        variant_list = self.productVariantValue.all().filter(
            variant=variant
        ).values('variant_value__value')
        return variant_list

    def variant_value_ids(self):
        prod_variant_value_ids = self.productVariantValue.all().values_list(
            'variant_value_id', flat=True)
        return prod_variant_value_ids
        # return [var_val.id for var_val in self.variant_values.all()]

    def variant_ids(self):
        prod_variant_ids = self.productVariantValue.all().values_list(
            'variant_value__variant_id', flat=True)
        return prod_variant_ids
        # return [var_val.variant.id for var_val in self.variant_values.all()]

    def get_variant_string(self):
        variant_value_list = VariantValues.objects.filter(
            pk__in=self.variant_value_ids()
        )
        var_string = ""
        for var_value in variant_value_list:
            if var_value == variant_value_list.last():
                var_string += var_value.variant.name\
                              + ":" + var_value.value
            else:
                var_string += var_value.variant.name\
                              + ":" + var_value.value + ","
        return var_string

    def get_variant_string_ar(self):
        variant_value_list = VariantValues.objects.filter(
            pk__in=self.variant_value_ids()
        )
        var_string = ""
        for var_value in variant_value_list:
            if var_value == variant_value_list.last():
                var_string += var_value.variant.nameAR\
                              + ":" + var_value.valueAR
            else:
                var_string += var_value.variant.nameAR\
                              + ":" + var_value.valueAR + ","
        return var_string

    def parent_prod(self):
        return self.parent if self.parent else self

    def get_avail_qty(self):
        inv_store_prod = self.inventoryProducts.filter(
            inventory__store=self.store)
        if inv_store_prod.exists():
            return inv_store_prod.first().quantity
        return 0

    def get_inventory_avail_count(self):
        child_qty = InventoryProduct.objects.filter(
            product__pk__in=self.children.values_list('id')
        ).aggregate(quantity_count=Sum(F('quantity'))).get(
            'quantity_count')
        if child_qty:
            return child_qty
        return 0

    def get_overall_rating(self):
        if self.prod_ratings.exists():
            overall_rating = self.prod_ratings.aggregate(
                rating=Avg('star'))['rating']
            overall_rating = round(overall_rating, ndigits=2)
            return overall_rating
        return 0.0

    def get_discounted_price(self):
        try:
            self.discount
        except ObjectDoesNotExist:
            return 0.0
        return self.discount.discounted_price()

    def get_discount_percent(self):
        try:
            self.discount
        except ObjectDoesNotExist:
            return 0.0
        return self.discount.percentage

    def get_discounted_price_or_base_price(self):
        try:
            self.discount
        except ObjectDoesNotExist:
            return self.base_price
        return self.discount.discounted_price()

    def get_media_url(self):
        if self.medias.filter(is_thumbnail=False).exists():
            media = self.medias.filter(
                is_thumbnail=False).first().file_data.url
            return media
        return ""

    def get_thumbnail_url(self):
        if self.medias.filter(is_thumbnail=True).exists():
            media = self.medias.filter(is_thumbnail=True).latest('id')
            if media.file_data:
                return media.file_data.url
            return ""
        return ""

    def get_thumbnail_media(self):
        if self.medias.filter(is_thumbnail=True).exists():
            media = self.medias.filter(is_thumbnail=True).latest('id')
            if media.file_data:
                return media
            return ""
        return ""

    def thumbnail_exists(self):
        if self.medias.filter(is_thumbnail=True).exists():
            return True
        return False


class EcommProductMedia(models.Model):
    product = models.ForeignKey(
        "product.EcommProduct", related_name="medias", on_delete=CASCADE)
    file_data = models.FileField(upload_to="ecomm_products/medias")
    order = models.SmallIntegerField()
    is_thumbnail = models.BooleanField(default=False)

    class Meta:
        ordering = ("order", )


class EcommProductViews(models.Model):
    product = models.ForeignKey(
        "product.EcommProduct",
        related_name="ecomm_prod_views",
        on_delete=CASCADE)
    member = models.ForeignKey(
        "authentication.Member",
        related_name="ecomm_prod_views",
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
        if self.product:
            return self.product.__str__()
        return str(self.pk)


class SearchKeyWord(models.Model):
    TYPE__CHOICES = (
        ('product', 'Product'),
        ('seller', 'Seller'),
    )
    keyword = models.CharField(max_length=255, unique=True)
    results_count = models.PositiveIntegerField(default=0)
    searched_for = models.CharField(
        max_length=255, choices=TYPE__CHOICES, default='product')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "-".join([
            self.keyword, self.searched_for])

    class Meta:
        ordering = ("id", )


class SearchKeyWordAR(models.Model):
    TYPE__CHOICES = (
        ('product', 'Product'),
        ('seller', 'Seller'),
    )
    keyword_ar = models.CharField(max_length=255, unique=True)
    results_count = models.PositiveIntegerField(default=0)
    searched_for = models.CharField(
        max_length=255, choices=TYPE__CHOICES, default='product')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "-".join([
            self.keyword_ar, self.searched_for,
            str(self.results_count)])

    class Meta:
        ordering = ("id", )


class Category(models.Model):
    name = models.CharField(max_length=255)
    nameAR = models.CharField(max_length=255)
    ordering_id = models.PositiveIntegerField(
        blank=True, null=True)
    parent = models.ForeignKey('self', related_name='children',
                               blank=True, null=True, on_delete=CASCADE)
    image = models.ImageField(
        upload_to='category/images', blank=True, null=True
    )

    image_width = models.FloatField(default=0.0)
    image_height = models.FloatField(default=0.0)

    home_page_thumbnail = models.ImageField(
        upload_to='category/home_page_thumbnail',
        blank=True, null=True
    )
    home_page_thumbnail_ar = models.ImageField(
        upload_to='category/home_page_thumbnail_ar',
        blank=True, null=True
    )

    # for web
    home_page_icon = models.ImageField(
        upload_to='category/home_page_icon',
        blank=True, null=True
    )

    STATUS_CHOICES = (
        ('AC', 'Active'),
        ('IN', 'In-Active'),
    )
    status = models.CharField(
        max_length=2, default='AC',
        choices=STATUS_CHOICES)

    home_page_items = models.ManyToManyField(
        "store.HomePageItems", related_name="categories",
        blank=True, default=None)
    seller_page_items = models.ManyToManyField(
        "store.SellerPageItems", related_name="categories",
        blank=True, default=None)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CategoryQuerySet.as_manager()

    def __str__(self):
        if self.parent:
            return '->'.join(
                [self.parent.__str__(), self.name,
                 str(self.pk)]
            )
        else:
            return '->'.join(
                [self.name, str(self.pk)]
            )

    def get_parent_name_chain(self):
        if self.parent:
            return '>'.join(
                [self.name, self.parent.get_parent_name_chain()]
            )
        else:
            return '>'.join(
                [self.name]
            )

    class Meta:
        ordering = ('name',)
        verbose_name_plural = 'categories'


class Brand(models.Model):
    name = models.CharField(max_length=255)
    nameAR = models.CharField(max_length=255)
    image = models.ImageField(
        upload_to='brand/images', blank=True, null=True
    )
    cover = models.ImageField(
        upload_to="brand/covers/", blank=True, null=True)

    image_width = models.FloatField(default=0.0)
    image_height = models.FloatField(default=0.0)
    is_top_brand = models.BooleanField(default=False)
    is_seller = models.BooleanField(default=False)

    selling_categories = models.ManyToManyField(
        "product.Category", related_name="brand_selling_categories",
        blank=True, default=None)
    seller = models.ForeignKey(
        "store.Store", related_name="brands",
        blank=True, null=True,
        on_delete=CASCADE)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def owner(self):
        if self.seller:
            return self.seller.member
        return None

    class Meta:
        ordering = ('name',)
        verbose_name_plural = 'brands'


class Discount(models.Model):
    product = models.OneToOneField(
        'product.EcommProduct', related_name='discount',
        on_delete=CASCADE
    )
    quantity = models.IntegerField(default=0)
    percentage = models.FloatField(default=0.0)
    startDate = models.DateTimeField(blank=False, null=True)
    endDate = models.DateTimeField(blank=False, null=True)

    def __str__(self):
        return self.product.__str__()

    class Meta:
        ordering = ('-id',)

    def discounted_price(self):
        return self.product.base_price - (
                self.product.base_price * self.percentage)/100


class EcommProductRatingandReview(models.Model):
    product = models.ForeignKey(
        "product.EcommProduct", related_name="prod_ratings", on_delete=CASCADE)
    member = models.ForeignKey(
        "authentication.Member", related_name="prod_ratings", on_delete=CASCADE)
    star = models.FloatField(default=0.0)
    review = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-id", )

    def owner(self):
        if self.product.store:
            return self.product.store.member
        return None

    def __str__(self):
        return "%d star rating of %s" % (self.star, self.product.name)

    def get_reviews_count(self):
        if self.product.prod_ratings.exists():
            reviews_count = self.product.prod_ratings.all().count()
            return reviews_count
        return 0

    def get_rating_string(self):
        if 1 <= self.product.overall_rating < 2:
            return "Bad"
        elif 2 <= self.product.overall_rating < 3:
            return "Good"
        elif 3 <= self.product.overall_rating < 4:
            return "Very Good"
        elif 4 <= self.product.overall_rating <= 5:
            return "Excellent"

    def get_order_status(self):
        if self.member.orders.exists():
            prod_with_order = self.member.orders.filter(
                orderProducts__product=self.product
            )
            if prod_with_order.exists():
                return "Ordered"
        return "Not Ordered"

    def get_last_added_date(self):
        if self.product.prod_ratings.exists():
            latest_rating = self.product.prod_ratings.latest('id')
            kuwait_date = datetime_from_utc_to_local_new(latest_rating.updated_at)
            return latest_rating.updated_at.date()
            # return kuwait_date.date()
        return self.updated_at.date()


class Variant(models.Model):
    TYPE__CHOICES = (
        ('textinput', 'Textinput'),
        ('singleselect', 'SingleSelect'),
        ('multipleselect', 'Multipleselect'),
        ('boolean', 'Boolean'),
    )
    category = models.ForeignKey(
        'product.Category', related_name='variants',
        null=True, blank=True, on_delete=CASCADE)
    name = models.CharField(max_length=255)
    nameAR = models.CharField(max_length=255)
    type = models.CharField(max_length=255,
                            choices=TYPE__CHOICES)
    required = models.BooleanField(default=False)
    userInput = models.BooleanField(default=False)
    hidden = models.BooleanField(default=False)
    orderingId = models.IntegerField(
        default=0, null=True, blank=True)
    important = models.BooleanField(default=True)

    def __str__(self):
        return ' - '.join(
            [self.category.__str__(), self.name]
        )

    class Meta:
        ordering = ('-id',)
        verbose_name_plural = 'Variants'


class VariantValues(models.Model):
    variant = models.ForeignKey(
        'product.Variant', related_name='variantValues',
        null=True, blank=True, on_delete=CASCADE)
    value = models.CharField(max_length=255)
    valueAR = models.CharField(max_length=255)
    amount = models.FloatField(blank=True, null=True)
    orderingId = models.IntegerField(
        default=0, null=True, blank=True)

    def __str__(self):
        if self.amount:
            return ' - '.join(
                [self.variant.__str__(), self.value, str(self.amount)]
            )
        else:
            return ' - '.join(
                [self.variant.__str__(), self.value]
            )

    class Meta:
        ordering = ('-id',)
        verbose_name_plural = 'VariantValues'


class ProductVariantValue(models.Model):
    variant_value = models.ForeignKey(
        'product.VariantValues', related_name='productVariantValue',
        null=True, blank=True, on_delete=CASCADE)
    product = models.ForeignKey(
        'product.EcommProduct', related_name='productVariantValue',
        null=True, blank=True, on_delete=CASCADE)

    def __str__(self):
        return self.variant_value.__str__()

    def parent(self):
        return self.product.parent

    class Meta:
        ordering = ('-id',)


class ProductSpecification(models.Model):
    specification = models.CharField(max_length=255)
    specificationAR = models.CharField(max_length=255)
    value = models.CharField(max_length=255)
    valueAR = models.CharField(max_length=255)
    product = models.ForeignKey(
        'product.EcommProduct', related_name='specifications',
        null=True, blank=True, on_delete=CASCADE)

    def __str__(self):
        return self.product.__str__()

    class Meta:
        ordering = ('-id',)


class MyModel(TranslatableModel):
    translations = TranslatedFields(
        title=models.CharField(_("Title"), max_length=200)
    )
    image_width = models.FloatField(default=0.0)
    image_height = models.FloatField(default=0.0)

    def __unicode__(self):
        return self.pk


class CategoryMedia(models.Model):
    TYPE_CHOICES = (
        ('im1', 'Image_1'),
        ('im2', 'Image_2'),
        ('im3', 'Image_3'),
    )
    type = models.CharField(
        max_length=3, default='im1',
        choices=TYPE_CHOICES)

    category = models.ForeignKey(
        "product.Category", related_name="medias", on_delete=CASCADE)
    media = models.ImageField(
        upload_to='category/medias', blank=True, null=True
    )

    image_width = models.FloatField(default=0.0)
    image_height = models.FloatField(default=0.0)
    order = models.SmallIntegerField(blank=True, null=True)

    class Meta:
        ordering = ("order", )


class ProductCollection(models.Model):
    name = models.CharField(max_length=255)
    nameAR = models.CharField(max_length=255)

    TYPE_CHOICES = (
        ('MAN', 'Manual'),
        ('AUTO', 'Automated'),
    )
    type = models.CharField(
        max_length=4, default='MAN',
        choices=TYPE_CHOICES)

    STATUS_CHOICES = (
        ('AC', 'Active'),
        ('IN', 'In-Active'),
    )
    status = models.CharField(
        max_length=2, default='AC',
        choices=STATUS_CHOICES)
    status_start_date = models.DateTimeField(
        blank=True, null=True)
    status_end_date = models.DateTimeField(
        blank=True, null=True)
    all_cond_match = models.BooleanField(default=False)

    products = models.ManyToManyField(
        'product.EcommProduct', related_name='prod_collections',
        blank=True)
    seller = models.ForeignKey(
        "store.Store", related_name="prod_collections",
        blank=True, null=True,
        on_delete=CASCADE)

    def __str__(self):
        return self.name

    def date_condition(self):
        if self.status_end_date and self.status_start_date:
            if self.status_start_date <= now() <= self.status_end_date:
                return True
            return False
        elif self.status_end_date and not self.status_start_date:
            if now() <= self.status_end_date:
                return True
            return False
        elif self.status_start_date and not self.status_end_date:
            if self.status_start_date <= now():
                return True
            return False
        return True

    class Meta:
        ordering = ('-id',)

    def prods_linked(self):
        return self.products.all().count()


class ProductCollectionCond(models.Model):
    field = models.CharField(max_length=255)
    operator = models.CharField(max_length=255)
    value = models.CharField(max_length=255)

    collections = models.ForeignKey(
        'product.ProductCollection', related_name='collection_conds',
        null=True, blank=True, on_delete=CASCADE)

    def __str__(self):
        return self.field

    class Meta:
        ordering = ('-id',)


class Coupon(models.Model):
    TYPE_CHOICES = (
        ('PER', 'Percentage'),
        ('FA', 'Fixed Amount'),
        ('FS', 'Free Shipping'),
        ('BXGY', 'Buy X get Y'),
    )
    type = models.CharField(
        max_length=4, default=None,
        choices=TYPE_CHOICES)

    STATUS_CHOICES = (
        ('AC', 'Active'),
        ('IN', 'In-Active'),
        ('SC', 'Scheduled')
    )
    status = models.CharField(
        max_length=2, default='AC',
        choices=STATUS_CHOICES)

    code = models.CharField(max_length=255, unique=True)
    deductable_percentage = models.FloatField(default=0.0)
    deductable_amount = models.FloatField(default=0.0)
    is_for_all_products = models.BooleanField(default=False)
    is_for_specific_products = models.BooleanField(default=False)

    is_for_specific_collections = models.BooleanField(default=False)

    min_required_purchase_amt = models.FloatField(default=0.0)
    min_qty_items = models.IntegerField(default=0)

    is_for_all_customers = models.BooleanField(default=False)
    is_for_customers_with_no_orders = models.BooleanField(default=False)
    is_for_specific_customers = models.BooleanField(default=False)

    no_of_times_usable = models.IntegerField(default=0)
    no_of_times_used = models.IntegerField(default=0)

    one_use_per_customer = models.BooleanField(default=False)

    active_start_date = models.DateTimeField(
        blank=True, null=True)
    active_end_date = models.DateTimeField(
        blank=True, null=True)

    send_push_immediately = models.BooleanField(default=False)
    push_notification_schedule_date = models.DateTimeField(
        blank=True, null=True)
    reason = models.TextField(
        max_length=255, blank=True, null=True)

    collections = models.ManyToManyField(
        "product.ProductCollection", related_name="coupons",
        blank=True)
    products = models.ManyToManyField(
        "product.EcommProduct", related_name="coupons",
        blank=True)
    customers = models.ManyToManyField(
        "authentication.Member", related_name="coupons",
        blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "%s Coupon Code" % self.code

    class Meta:
        ordering = ("-id", )

    def date_condition(self):
        if self.active_end_date and self.active_start_date:
            if self.active_start_date <= now() <= self.active_end_date:
                return True
            return False
        elif self.active_end_date and not self.active_start_date:
            if now() <= self.active_end_date:
                return True
            return False
        elif self.active_start_date and not self.active_end_date:
            if self.active_start_date <= now():
                return True
            return False
        return True

    def prod_condition(self, cart):

        if cart.cartProducts.exists():

            if self.is_for_all_products:
                return True

            cart_prod_ids = cart.cartProducts.all().values_list(
                'product_id', flat=True).distinct()

            if self.products.all().exists():
                prods_existing_count = self.products.filter(
                    pk__in=cart_prod_ids
                ).count()
                return prods_existing_count > 0

            elif self.collections.all().exists():
                prods_existing_count = self.collections.filter(
                    products__pk__in=cart_prod_ids
                ).count()
                return prods_existing_count > 0

        return True

    def purchase_amt_condition(self, cart):
        if cart.cartProducts.exists():
            if self.prod_condition(cart):
                return cart.totalPrice >= self.min_required_purchase_amt
            return False
        return True

    def get_prod_quantity(self, cart):
        prod_count = 0
        cart_prod_ids = cart.cartProducts.all().values_list(
            'product_id', flat=True).distinct()

        print("is_for_all_products")
        print(self.is_for_all_products)

        print(cart.cartProducts.all().aggregate(
                qty_sum=Sum("quantity")).get("qty_sum"))

        if self.is_for_all_products:
            prod_count = cart.cartProducts.all().aggregate(
                qty_sum=Sum("quantity")).get("qty_sum")
        else:
            if self.products.all().exists():
                prods_existing = self.products.filter(
                    pk__in=cart_prod_ids
                ).values_list('id', flat=True)
                prod_count = cart.cartProducts.all().filter(
                    product__pk__in=prods_existing
                ).aggregate(qty_sum=Sum("quantity")).get("qty_sum")

            elif self.collections.all().exists():
                prods_existing = self.collections.filter(
                    products__pk__in=cart_prod_ids
                ).values_list('id', flat=True)
                prod_count = cart.cartProducts.all().filter(
                    product__pk__in=prods_existing
                ).aggregate(qty_sum=Sum("quantity")).get("qty_sum")

        print("prod_count")
        print(prod_count)
        if prod_count is None:
            return 0
        return prod_count

    def min_qty_items_condition(self, cart):
        if cart.cartProducts.exists():
            print("self.prod_condition(cart)")
            print(self.prod_condition(cart))
            if self.prod_condition(cart):
                return self.get_prod_quantity(cart) >= self.min_qty_items
            return False
        return True

    def customer_condition(self, cart):
        if self.is_for_all_customers:
            return True
        elif self.is_for_customers_with_no_orders:
            customer_with_no_orders = Member.objects.annotate(
                order_count=Count('orders', filter=Q(orders__payments__status='SU')),
            ).filter(order_count=0)
            if cart.customer in customer_with_no_orders:
                return True
            return False
        elif cart.customer in self.customers.all():
            return True
        return False

    def single_use_customer_condition(self, cart):
        customer = cart.customer
        if customer.orders.exists():
            orders_with_same_coupon = customer.orders.filter(
                coupon=self
            )
            if orders_with_same_coupon.exists():
                return False
            return True
        return True

    def entire_usage_condition(self, cart):
        if self.no_of_times_usable == 0:
            if self.one_use_per_customer:
                return self.single_use_customer_condition(cart)
            elif self.is_for_all_customers:
                return True
            elif cart.customer in self.customers.all():
                return True
            return False
        elif self.no_of_times_used <= self.no_of_times_usable and self.no_of_times_usable > 0:
            if self.one_use_per_customer:
                return self.single_use_customer_condition(cart)
            elif self.is_for_all_customers:
                return True
            elif cart.customer in self.customers.all():
                return True
        return True

    def is_applicable_to_cart(self, cart):
        conditions = [self.status == "AC" or self.status == "SC",
                      self.date_condition(),
                      self.prod_condition(cart),
                      self.purchase_amt_condition(cart),
                      self.min_qty_items_condition(cart),
                      self.customer_condition(cart),
                      self.entire_usage_condition(cart)]
        print("conds")
        print(conditions)
        filter__false_conds = [x for x in conditions if x is False]
        if len(filter__false_conds) >= 1:
            return False
        return True

    def get_discounted_price(self, cart):
        return cart.totalPrice - (
                cart.totalPrice * self.deductable_percentage)/100

    def get_discounted_price_order(self, order):
        discount_price = (order.get_sub_total() * self.deductable_percentage)/100
        return discount_price
