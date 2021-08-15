
from django.db.models import Avg
from django.db.models.signals import post_save
from django.dispatch import receiver
from app.product.models import EcommProductRatingandReview


@receiver(post_save, sender=EcommProductRatingandReview)
def update_overall_rating_product(sender, instance=None, created=False, **kwargs):
    if instance.product.prod_ratings.exists():
        overall_rating = instance.product.prod_ratings.aggregate(
            rating=Avg('star'))['rating']
        instance.product.overall_rating = overall_rating
        instance.product.save()
