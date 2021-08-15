from django.contrib.postgres.fields import ArrayField
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import CASCADE, Sum, F
from phonenumber_field.modelfields import PhoneNumberField

# Create your models here.
from phonenumbers import national_significant_number

from app.authentication.models import Member
from app.order.models import Order


class Store(models.Model):
    TYPE_CHOICES = (
        ('CON', 'Consignment'),
        ('NCON', 'Non Consignment'),
        ('NCONP', 'Non Consignment (Pickup)'),
    )
    type = models.CharField(
        max_length=5, default='CON',
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

    name = models.CharField(max_length=255)
    nameAR = models.CharField(max_length=255)
    member = models.OneToOneField(
        'authentication.Member', related_name='stores',
        on_delete=CASCADE)
    country = models.ForeignKey('store.Country', blank=True,
                                null=True, related_name='stores', on_delete=CASCADE)
    canAccessInventory = models.BooleanField(default=False)
    isDeliveryStore = models.BooleanField(default=False)
    useCityCost = models.BooleanField(default=False)
    pricePerMile = models.FloatField(default=1.0)
    pickUpCharge = models.FloatField(default=0.0)
    currency = models.CharField(max_length=255, default="KD")
    image = models.ImageField(
        upload_to='store/images', blank=True, null=True,
        validators=[
            FileExtensionValidator(allowed_extensions=["png", "jpeg", "jpg"])
        ]
    )
    resized_image = models.ImageField(
        upload_to='store/resized_images', blank=True, null=True,
        validators=[
            FileExtensionValidator(allowed_extensions=["png", "jpeg", "jpg"])
        ]
    )
    website = models.CharField(max_length=150, blank=True, null=True)
    phone = PhoneNumberField()
    address = models.TextField()
    addressAR = models.TextField()
    contact_email = models.EmailField(blank=True, null=True)
    iban = models.CharField(max_length=40)

    selling_categories = models.ManyToManyField(
        "product.Category", related_name="store_selling_categories",
        blank=True, default=None)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "-".join([self.name, str(self.member.__str__())])

    def owner(self):
        if self.member:
            return self.member
        return None

    def sub_admins(self):
        return self.seller_sub_admins.all()

    def get_sales(self):
        orders_sales_price = Order.objects.filter(
            payments__status='SU',
            orderProducts__product__store=self
        ).aggregate(price=Sum(F('totalPrice'))).get(
            'price')

        if orders_sales_price:
            return "{0:.3f}".format(orders_sales_price)
        return 0

    def get_sales_float(self):
        orders_sales_price = Order.objects.filter(
            payments__status='SU',
            orderProducts__product__store=self
        ).aggregate(price=Sum(F('totalPrice'))).get(
            'price')

        if orders_sales_price:
            return orders_sales_price
        return 0

    def get_earnings(self):
        sales = self.get_sales_float()
        if self.commission.exists():
            commission = self.commission.all().values(
                'percentage', 'category__id').order_by(
                'category__id').distinct('category__id')
            total_commission = 0
            for c in commission:
                category_id = c.get('category__id')
                percentage = c.get('percentage')
                cat_sales_price = Order.objects.filter(
                    payments__status='SU',
                    orderProducts__product__store=self,
                    orderProducts__product__category_id=category_id
                ).aggregate(price=Sum(F('totalPrice'))).get('price')
                if cat_sales_price:
                    commission_per_cat = cat_sales_price - (
                            cat_sales_price * percentage) / 100
                    total_commission += commission_per_cat
            return sales - total_commission
        return 0

    class Meta:
        ordering = ('name',)
        verbose_name = 'Seller'
        verbose_name_plural = ' Sellers'


class SellerSubAdmins(models.Model):
    name = models.CharField(
        max_length=255, blank=True, null=True)
    nameAR = models.CharField(
        max_length=255, blank=True, null=True)
    designation = models.CharField(
        max_length=255, blank=True, null=True)
    company = models.CharField(
        max_length=255, blank=True, null=True)

    store = models.ForeignKey(
        'store.Store', related_name='seller_sub_admins',
        on_delete=CASCADE)
    member = models.ForeignKey(
        'authentication.Member', related_name='seller_sub_admins',
        on_delete=CASCADE)

    def __str__(self):
        return "-".join([self.member.__str__(), str(self.store.__str__())])

    class Meta:
        ordering = ('id',)
        verbose_name_plural = 'SellerSubAdmins'


class Inventory(models.Model):
    name = models.CharField(max_length=255)
    nameAR = models.CharField(max_length=255)
    store = models.ForeignKey(
        'store.Store', related_name='inventories',
        on_delete=CASCADE)
    admins = models.ManyToManyField(
        "authentication.Member", related_name="inventories",
        blank=True, default=None)

    def __str__(self):
        return "-".join([self.name, str(self.store.__str__())])

    class Meta:
        ordering = ('name',)
        verbose_name_plural = 'Inventories'


class InventoryProduct(models.Model):
    product = models.ForeignKey(
        'product.EcommProduct',
        related_name='inventoryProducts', on_delete=CASCADE)
    price = models.FloatField(default=0.0)
    quantity = models.IntegerField(default=0)
    inventory = models.ForeignKey(
        'store.Inventory',
        related_name='inventoryProducts', on_delete=CASCADE)

    def __str__(self):
        return ' - '.join(
            [self.inventory.__str__(), self.product.__str__()]
        )

    class Meta:
        ordering = ('id',)


class StoreMedia(models.Model):
    store = models.ForeignKey(
        "store.Store", related_name="medias", on_delete=CASCADE)
    file_data = models.FileField(upload_to="store/medias")
    order = models.SmallIntegerField()

    class Meta:
        ordering = ("order", )


class Country(models.Model):
    name = models.CharField(max_length=150)
    nameAR = models.CharField(max_length=150)
    currency = models.CharField(max_length=5, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ('name',)
        verbose_name_plural = 'country'


class HomePageItems(models.Model):
    DEVICE_CHOICES = (
        ('MOB', 'Mobile'),
        ('WEB', 'Web'),
        ('WEBANDMOB', 'WebandMobile'),
    )
    device = models.CharField(
        max_length=9, default='MOB',
        choices=DEVICE_CHOICES)

    name = models.CharField(max_length=150, blank=True, null=True)
    nameAR = models.CharField(max_length=150, blank=True, null=True)
    type = models.CharField(max_length=150)
    title_alignment = models.CharField(max_length=150)
    title_image = models.ImageField(
        upload_to='homepageitems/images', blank=True, null=True
    )
    title_image_ar = models.ImageField(
        upload_to='homepageitems/images_ar', blank=True, null=True
    )
    banner = models.ForeignKey(
        'store.Banner', related_name='homepageitems',
        on_delete=CASCADE, blank=True, null=True)

    collection = models.ForeignKey(
        "product.ProductCollection",
        related_name="homepageitems",
        blank=True, null=True,
        on_delete=CASCADE)

    can_see_all = models.BooleanField(default=False)

    # ordering id not to be used anymore
    ordering_id = models.PositiveIntegerField(
        blank=True, null=True)

    # ordering id to be used for mob and web
    order_for_mob = models.IntegerField(
        blank=True, null=True)
    order_for_web = models.IntegerField(
        blank=True, null=True)

    # shuffling ordering id to be used for mob and web
    shuffling_order_for_web = models.IntegerField(
        blank=True, null=True)
    shuffling_order_for_mob = models.IntegerField(
        blank=True, null=True)

    no_of_rows = models.PositiveIntegerField(default=1)
    hidden = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    last_shuffled_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        if self.name:
            return "-".join([self.type, self.name])
        return self.type

    class Meta:
        ordering = ('id',)
        verbose_name_plural = 'homepageitems'


class HomePageItemValues(models.Model):
    name = models.CharField(
        max_length=255, blank=True, null=True)
    nameAR = models.CharField(
        max_length=255, blank=True, null=True)
    border_colour = models.CharField(max_length=150)
    base_price = models.FloatField(default=0.0)
    discounted_price = models.FloatField(default=0.0)
    discount_percent = models.FloatField(default=0.0)
    currency = models.CharField(max_length=5, blank=True)
    object_id = models.PositiveIntegerField(
        blank=True, null=True)
    object_ids = ArrayField(
        ArrayField(models.IntegerField()), blank=True, default=list)
    object_type = models.CharField(max_length=150, blank=True)

    image = models.ImageField(
        upload_to='homepageitemvalues/images', blank=True, null=True
    )
    image_ar = models.ImageField(
        upload_to='homepageitemvalues/images_ar', blank=True, null=True
    )
    image_web = models.ImageField(
        upload_to='homepageitemvalues/images_web', blank=True, null=True
    )
    image_web_ar = models.ImageField(
        upload_to='homepageitemvalues/images_web_ar', blank=True, null=True
    )
    icon = models.ImageField(
        upload_to='homepageitemvalues/icons', blank=True, null=True
    )
    background_image = models.ImageField(
        upload_to='homepageitemvalues/background_images', blank=True, null=True
    )
    brand_name = models.CharField(max_length=150, blank=True, null=True)
    brand_image = models.ImageField(
        upload_to='homepageitemvalues/brandimages', blank=True, null=True
    )
    seller_name = models.CharField(max_length=150, blank=True, null=True)
    seller_image = models.ImageField(
        upload_to='homepageitemvalues/sellerimages', blank=True, null=True
    )
    homepageitem = models.ForeignKey(
        'store.HomePageItems', related_name='homepageitemvalues',
        on_delete=CASCADE, blank=True, null=True)
    category = models.ForeignKey(
        'product.Category', related_name='homepageitemvalues',
        on_delete=CASCADE, blank=True, null=True)
    url_link = models.CharField(
        max_length=150, blank=True, null=True)

    device_id = models.CharField(
        blank=True, null=True, db_index=True,
        max_length=150
    )
    registration_id = models.TextField(blank=True, null=True)
    fcm_device_id = models.IntegerField(default=0)

    # ordering id not to be used anymore
    ordering_id = models.PositiveIntegerField(
        blank=True, null=True)

    # ordering id to be used for mob and web
    order_for_mob = models.IntegerField(
        blank=True, null=True)
    order_for_web = models.IntegerField(
        blank=True, null=True)

    # shuffling ordering id to be used for mob and web
    shuffling_order_for_web = models.IntegerField(
        blank=True, null=True)
    shuffling_order_for_mob = models.IntegerField(
        blank=True, null=True)

    member = models.ForeignKey(
        "authentication.Member", on_delete=CASCADE,
        blank=True, null=True, related_name="homepageitemvalues")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_shuffled_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        if self.name:
            return "-".join(
                [self.name, str(self.object_id), self.object_type])
        return "-".join(
                [str(self.object_id), self.object_type])

    class Meta:
        ordering = ('id',)
        verbose_name_plural = 'homepageitemvalues'


class HomePageItemLastShuffledAt(models.Model):
    created_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    preserved_order = models.CharField(
        max_length=255, blank=True, null=True)

    class Meta:
        ordering = ('id',)
        verbose_name_plural = 'homepageitemlastshuffledat'


class SellerPageItems(models.Model):
    DEVICE_CHOICES = (
        ('MOB', 'Mobile'),
        ('WEB', 'Web'),
        ('WEBANDMOB', 'WebandMobile'),
    )
    device = models.CharField(
        max_length=9, default='MOB',
        choices=DEVICE_CHOICES)

    name = models.CharField(max_length=150, blank=True, null=True)
    nameAR = models.CharField(max_length=150, blank=True, null=True)
    type = models.CharField(max_length=150)
    title_alignment = models.CharField(max_length=150)
    title_image = models.ImageField(
        upload_to='sellerpageitems/images', blank=True, null=True
    )
    can_see_all = models.BooleanField(default=False)

    collection = models.ForeignKey(
        "product.ProductCollection",
        related_name="sellerpageitems",
        blank=True, null=True,
        on_delete=CASCADE)

    ordering_id = models.PositiveIntegerField(
        blank=True, null=True)

    # ordering id to be used for mob and web
    order_for_mob = models.IntegerField(
        blank=True, null=True)
    order_for_web = models.IntegerField(
        blank=True, null=True)

    no_of_rows = models.PositiveIntegerField(default=1)
    store = models.ForeignKey(
        "store.Store", related_name="sellerpageitems",
        on_delete=CASCADE, blank=True, null=True)

    def __str__(self):
        if self.name:
            return "-".join([self.type, self.name, self.store.__str__()])
        return self.type

    class Meta:
        ordering = ('id',)
        verbose_name_plural = 'sellerpageitems'


class SellerPageItemValues(models.Model):
    name = models.CharField(
        max_length=150, blank=True, null=True)
    nameAR = models.CharField(
        max_length=150, blank=True, null=True)
    border_colour = models.CharField(max_length=150)
    base_price = models.FloatField(default=0.0)
    discounted_price = models.FloatField(default=0.0)
    discount_percent = models.FloatField(default=0.0)
    currency = models.CharField(max_length=5, blank=True)
    object_id = models.PositiveIntegerField(
        blank=True, null=True)
    object_ids = ArrayField(
        ArrayField(models.IntegerField()), blank=True, default=list)

    object_type = models.CharField(max_length=150, blank=True)
    url_link = models.CharField(
        max_length=150, blank=True, null=True)

    image = models.ImageField(
        upload_to='sellerpageitemvalues/images', blank=True, null=True
    )
    image_ar = models.ImageField(
        upload_to='sellerpageitemvalues/images_ar', blank=True, null=True
    )
    image_web = models.ImageField(
        upload_to='sellerpageitemvalues/images_web', blank=True, null=True
    )
    image_web_ar = models.ImageField(
        upload_to='sellerpageitemvalues/images_web_ar', blank=True, null=True
    )
    icon = models.ImageField(
        upload_to='sellerpageitemvalues/icons', blank=True, null=True
    )
    background_image = models.ImageField(
        upload_to='sellerpageitemvalues/background_images', blank=True, null=True
    )
    brand_name = models.CharField(max_length=150, blank=True, null=True)
    brand_image = models.ImageField(
        upload_to='sellerpageitemvalues/brandimages', blank=True, null=True
    )
    seller_name = models.CharField(max_length=150, blank=True, null=True)
    seller_image = models.ImageField(
        upload_to='sellerpageitemvalues/sellerimages', blank=True, null=True
    )
    website = models.CharField(max_length=150, blank=True, null=True)
    phone = PhoneNumberField()
    address = models.TextField()
    contact_email = models.EmailField(blank=True, null=True)
    sellerpageitem = models.ForeignKey(
        'store.SellerPageItems', related_name='sellerpageitemvalues',
        on_delete=CASCADE, blank=True, null=True)

    ordering_id = models.PositiveIntegerField(
        blank=True, null=True)

    # ordering id to be used for mob and web
    order_for_mob = models.IntegerField(
        blank=True, null=True)
    order_for_web = models.IntegerField(
        blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ('id',)
        verbose_name_plural = 'sellerpageitemvalues'


class SocialMediaURL(models.Model):
    SOCIAL_MEDIA_CHOICES = (
        (1, "Fb"),
        (2, "Insta"),
        (3, "Twitter"),
        (4, "Youtube"),
        (5, "Snapchat"),
    )
    url = models.CharField(max_length=255, blank=True, null=True)
    social_media_icon = models.ImageField(
        upload_to='socialmediaurls/images', blank=True, null=True
    )
    status = models.SmallIntegerField(choices=SOCIAL_MEDIA_CHOICES, default=1)

    store = models.ForeignKey(
        "store.Store", related_name="socialmediaurls",
        on_delete=CASCADE, blank=True, null=True)

    def __str__(self):
        return self.store.name

    class Meta:
        ordering = ('id',)
        verbose_name_plural = 'socialmediaurls'


class City(models.Model):
    name = models.CharField(max_length=255)
    nameAR = models.CharField(max_length=255)
    governerate = models.CharField(
        max_length=255, blank=True, null=True, )
    governerateAR = models.CharField(
        max_length=255, blank=True, null=True, )

    parent = models.ForeignKey(
        'self', related_name='children',
        blank=True, null=True, on_delete=CASCADE)
    delivery_cost = models.FloatField(default=0.0)
    delicon_city_id = models.IntegerField(default=0)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ('name',)
        verbose_name_plural = 'cities'


class Address(models.Model):
    area = models.ForeignKey(
        'store.City', related_name='addresses',
        blank=True, null=True, on_delete=CASCADE)
    area_name = models.CharField(max_length=255, blank=True, null=True)
    title = models.CharField(max_length=255)
    state = models.CharField(max_length=255, blank=True, null=True)
    block = models.CharField(max_length=10)
    street = models.CharField(max_length=255)
    jadda = models.CharField(max_length=10, blank=True, null=True)
    house = models.CharField(max_length=10)
    floor = models.CharField(max_length=20, blank=True, null=True)
    apartment = models.CharField(max_length=255, blank=True, null=True)
    extra_directions = models.CharField(max_length=255, blank=True, null=True)
    customer_default = models.BooleanField(default=False)
    guest_default = models.BooleanField(default=False)

    customer = models.ForeignKey(
        'authentication.Member', related_name='addresses',
        blank=True, null=True,
        on_delete=models.SET_NULL)
    guest_acc = models.ForeignKey(
        'authentication.GuestAccount', related_name='addresses',
        blank=True, null=True,
        on_delete=models.SET_NULL
    )
    seller = models.ForeignKey(
        'store.Store', related_name='addresses',
        blank=True, null=True,
        on_delete=models.SET_NULL)
    lon = models.FloatField(blank=True, null=True)
    lat = models.FloatField(blank=True, null=True)
    phone = PhoneNumberField(blank=True, null=True)
    country = models.ForeignKey(
        "store.Country", related_name="addresses",
        blank=True, null=True,
        on_delete=CASCADE)
    country_code = models.CharField(max_length=10, blank=True)
    country_name = models.CharField(max_length=255)
    shipping_charge = models.FloatField(default=0.0)

    def __str__(self):
        return "Block: %s, Street %s" % (self.block, self.street)

    def get_phone_for_delicon(self):
        if self.phone != "" and self.phone is not None:
            # phone_string = "".join([
            #     str(national_significant_number(self.phone))
            # ])
            return str(national_significant_number(self.phone))
        return ""

    def address_str(self):
        return "Block: %s, Street %s," \
               " Jadda %s, House %s," \
               " Floor %s, Apartment %s, Country %s" % \
               (self.block, self.street, self.jadda,
                self.house, self.floor, self.apartment,
                self.country.name)

    def customer_name(self):
        return self.customer.__str__()

    class Meta:
        ordering = ('-id',)


class Commission(models.Model):
    percentage = models.IntegerField(default=0)
    category = models.ForeignKey(
        'product.Category', related_name='commission',
        blank=True, null=True, on_delete=CASCADE)
    seller = models.ForeignKey(
        'store.Store', related_name='commission',
        blank=True, null=True, on_delete=CASCADE)

    def __str__(self):
        if self.category and self.seller:
            return "-".join([self.category.__str__(),
                             self.seller.__str__(),
                             str(self.percentage)])
        return str(self.percentage)

    class Meta:
        ordering = ('id',)
        verbose_name_plural = 'Commissions'


class Payment(models.Model):
    STATUS_CHOICES = (
        ('SU', 'Success'),
        ('FA', 'Failure'),
    )
    status = models.CharField(
        max_length=2, default='SU',
        choices=STATUS_CHOICES)
    paymentType = models.ForeignKey(
        'store.PaymentType', related_name='payments',
        on_delete=CASCADE, blank=True, null=True)
    order = models.ForeignKey(
        'order.Order', related_name='payments',
        on_delete=CASCADE)
    card = models.ForeignKey(
        'order.Card', related_name='payments',
        on_delete=CASCADE, blank=True, null=True)
    member = models.ForeignKey(
        'authentication.Member',
        related_name='payments',
        blank=True, null=True,
        on_delete=CASCADE)
    guest_acc = models.ForeignKey(
        'authentication.GuestAccount', related_name='payments',
        blank=True, null=True,
        on_delete=CASCADE
    )
    amount = models.FloatField(default=0.0)
    isDeleted = models.BooleanField(default=False)
    cancellationReason = models.CharField(
        max_length=255, blank=True, null=True)
    isPaid = models.BooleanField(default=True)

    #payment gateway
    payment_id = models.CharField(
        max_length=255, blank=True, null=True)
    result = models.CharField(
        max_length=255, blank=True, null=True)
    post_date = models.CharField(
        max_length=255, blank=True, null=True)
    tran_id = models.CharField(
        max_length=255, blank=True, null=True)
    ref = models.CharField(
        max_length=255, blank=True, null=True)
    track_id = models.CharField(
        max_length=255, blank=True, null=True)
    auth = models.CharField(
        max_length=255, blank=True, null=True)

    def __str__(self):
        if self.member:
            return ' - '.join(
                ["payment", str(self.order.id),
                 self.member.get_exact_full_name()]
            )
        elif self.guest_acc:
            return ' - '.join(
                ["payment", str(self.order.id),
                 self.guest_acc.get_exact_full_name()]
            )
        return ' - '.join(
            ["payment", str(self.order.id)]
        )

    class Meta:
        ordering = ('-id',)


class PaymentType(models.Model):
    name = models.CharField(max_length=255)
    nameAR = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ('-id',)


class TopDealItems(models.Model):
    DEVICE_CHOICES = (
        ('MOB', 'Mobile'),
        ('WEB', 'Web'),
        ('WEBANDMOB', 'WebandMobile'),
    )
    device = models.CharField(
        max_length=9, default='MOB',
        choices=DEVICE_CHOICES)

    name = models.CharField(max_length=150, blank=True, null=True)
    nameAR = models.CharField(max_length=150, blank=True, null=True)
    type = models.CharField(max_length=150)
    title_alignment = models.CharField(max_length=150)
    title_image = models.ImageField(
        upload_to='topdealitems/images', blank=True, null=True
    )
    can_see_all = models.BooleanField(default=False)
    ordering_id = models.PositiveIntegerField(
        blank=True, null=True)

    # ordering id to be used for mob and web
    order_for_mob = models.IntegerField(
        blank=True, null=True)
    order_for_web = models.IntegerField(
        blank=True, null=True)

    no_of_rows = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.name:
            return "-".join([self.type, self.name])
        return self.type

    class Meta:
        ordering = ('id',)
        verbose_name_plural = 'topdealitems'


class TopDealItemValues(models.Model):
    name = models.CharField(max_length=150)
    nameAR = models.CharField(max_length=150)
    border_colour = models.CharField(max_length=150)
    base_price = models.FloatField(default=0.0)
    discounted_price = models.FloatField(default=0.0)
    discount_percent = models.FloatField(default=0.0)
    currency = models.CharField(max_length=5, blank=True)
    object_id = models.PositiveIntegerField(
        blank=True, null=True)
    object_ids = ArrayField(
        ArrayField(models.IntegerField()), blank=True, default=list)
    object_type = models.CharField(max_length=150, blank=True)

    image = models.ImageField(
        upload_to='topdealitemvalues/images', blank=True, null=True
    )
    image_ar = models.ImageField(
        upload_to='topdealitemvalues/images_ar', blank=True, null=True
    )
    image_web = models.ImageField(
        upload_to='topdealitemvalues/images_web', blank=True, null=True
    )
    image_web_ar = models.ImageField(
        upload_to='topdealitemvalues/images_web_ar', blank=True, null=True
    )
    icon = models.ImageField(
        upload_to='topdealitemvalues/icons', blank=True, null=True
    )
    background_image = models.ImageField(
        upload_to='topdealitemvalues/background_images', blank=True, null=True
    )
    brand_name = models.CharField(max_length=150, blank=True, null=True)
    brand_image = models.ImageField(
        upload_to='topdealitemvalues/brandimages', blank=True, null=True
    )
    seller_name = models.CharField(max_length=150, blank=True, null=True)
    seller_image = models.ImageField(
        upload_to='topdealitemvalues/sellerimages', blank=True, null=True
    )
    topdealitem = models.ForeignKey(
        'store.TopDealItems', related_name='topdealitemvalues',
        on_delete=CASCADE, blank=True, null=True)

    device_id = models.CharField(
        blank=True, null=True, db_index=True,
        max_length=150
    )
    registration_id = models.TextField(blank=True, null=True)
    fcm_device_id = models.IntegerField(default=0)

    ordering_id = models.PositiveIntegerField(
        blank=True, null=True)

    # ordering id to be used for mob and web
    order_for_mob = models.IntegerField(
        blank=True, null=True)
    order_for_web = models.IntegerField(
        blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.object_id:
            return "-".join(
                [self.name, str(self.object_id), self.object_type])
        return self.name

    class Meta:
        ordering = ('id',)
        verbose_name_plural = 'topdealitemvalues'


class EcommUserContact(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField()
    contact_no = PhoneNumberField(blank=True, null=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-id", )

    def __str__(self):
        return self.name


class Banner(models.Model):
    STATUS_CHOICES = (
        ('AC', 'Active'),
        ('IN', 'In-Active'),
        ('SCH', 'Scheduled'),
    )
    status = models.CharField(
        max_length=3, default='AC',
        choices=STATUS_CHOICES)
    status_start_date = models.DateTimeField(
        blank=True, null=True)
    status_end_date = models.DateTimeField(
        blank=True, null=True)

    TYPE_CHOICES = (
        ('APP', 'App'),
        ('WEB', 'Web'),
    )
    type = models.CharField(
        max_length=3, default='APP',
        choices=TYPE_CHOICES)

    LINK_CHOICES = (
        ('PROD', 'Prod'),
        ('COLL', 'Collection'),
        ('URL', 'Url'),
        ('MC', 'Main Category'),
        ('SC', 'Sub Category'),
        ('PT', 'Product Type'),
        ('SPT', 'Sub Product Type'),
    )
    link = models.CharField(
        max_length=4, default='PROD',
        choices=LINK_CHOICES)

    banner_image = models.ImageField(
        upload_to='banners/banner_images', blank=True, null=True
    )
    banner_image_ar = models.ImageField(
        upload_to='banners/banner_images_ar', blank=True, null=True
    )
    resized_banner_image = models.ImageField(
        upload_to='banners/banner_resizedimages', blank=True, null=True
    )
    resized_banner_image_ar = models.ImageField(
        upload_to='banners/banner_resizedimages_ar', blank=True, null=True
    )

    seller = models.ForeignKey(
        'store.Store',
        related_name='banners',
        blank=True, null=True,
        on_delete=CASCADE)
    product = models.ForeignKey(
        'product.EcommProduct',
        related_name='banners',
        blank=True, null=True,
        on_delete=CASCADE)
    collection = models.ForeignKey(
        "product.ProductCollection",
        related_name="banners",
        blank=True, null=True,
        on_delete=CASCADE)
    category = models.ForeignKey(
        'product.Category',
        related_name='banners',
        blank=True, null=True,
        on_delete=CASCADE)
    parent = models.ForeignKey(
        'self', related_name='children',
        blank=True, null=True, on_delete=CASCADE)

    name = models.CharField(max_length=255, blank=True, null=True)
    nameAR = models.CharField(max_length=255, blank=True, null=True)

    url = models.CharField(max_length=255, blank=True, null=True)
    ordering_id = models.PositiveIntegerField(default=1)
    clicks = models.PositiveIntegerField(default=0)

    is_for_homepage = models.BooleanField(default=False)
    is_for_seller = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-id", )

    def __str__(self):
        if self.name:
            return self.name
        return " ".join([
            self.seller.__str__(), self.type, self.link
        ])


class TopDealsBanner(models.Model):
    STATUS_CHOICES = (
        ('AC', 'Active'),
        ('IN', 'In-Active'),
        ('SCH', 'Scheduled'),
    )
    status = models.CharField(
        max_length=3, default='AC',
        choices=STATUS_CHOICES)
    status_start_date = models.DateTimeField(
        blank=True, null=True)
    status_end_date = models.DateTimeField(
        blank=True, null=True)

    TYPE_CHOICES = (
        ('APP', 'App'),
        ('WEB', 'Web'),
    )
    type = models.CharField(
        max_length=3, default='APP',
        choices=TYPE_CHOICES)

    LINK_CHOICES = (
        ('PROD', 'Prod'),
        ('COLL', 'Collection'),
        ('URL', 'Url'),
        ('MC', 'Main Category'),
        ('SC', 'Sub Category'),
        ('PT', 'Product Type'),
        ('SPT', 'Sub Product Type'),
    )
    link = models.CharField(
        max_length=4, default='PROD',
        choices=LINK_CHOICES)

    banner_image = models.ImageField(
        upload_to='top_deal_banners/banner_images', blank=True, null=True
    )
    banner_image_ar = models.ImageField(
        upload_to='top_deal_banners/banner_images_ar', blank=True, null=True
    )

    seller = models.ForeignKey(
        'store.Store',
        related_name='top_deal_banners',
        blank=True, null=True,
        on_delete=CASCADE)
    product = models.ForeignKey(
        'product.EcommProduct',
        related_name='top_deal_banners',
        blank=True, null=True,
        on_delete=CASCADE)
    collection = models.ForeignKey(
        "product.ProductCollection",
        related_name="top_deal_banners",
        blank=True, null=True,
        on_delete=CASCADE)
    category = models.ForeignKey(
        'product.Category',
        related_name='top_deal_banners',
        blank=True, null=True,
        on_delete=CASCADE)
    parent = models.ForeignKey(
        'self', related_name='children',
        blank=True, null=True, on_delete=CASCADE)

    name = models.CharField(max_length=255, blank=True, null=True)
    nameAR = models.CharField(max_length=255, blank=True, null=True)

    url = models.CharField(max_length=255, blank=True, null=True)
    clicks = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-id", )

    def __str__(self):
        if self.name:
            return self.name
        return " ".join([
            self.seller.__str__(), self.type, self.link
        ])
