
from django.db import models
from django.db.models import CASCADE

from .managers import RankQueryset


class Rank(models.Model):
    member = models.OneToOneField("authentication.Member", on_delete=CASCADE)
    current_rank = models.BigIntegerField()
    previous_rank = models.BigIntegerField()
    beams = models.FloatField(default=0.0)
    within_top_chart = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = RankQueryset.as_manager()

    def __str__(self):
        return "%s with rank %d" % (self.member.username, self.current_rank)

    class Meta:
        ordering = ("current_rank", )
