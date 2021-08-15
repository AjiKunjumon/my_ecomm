from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models import QuerySet, Q, Count, Case, When, F
from django.shortcuts import get_object_or_404

from app.utilities.helpers import str2bool
from app.product.utils import json_list


class CategoryQuerySet(QuerySet):
    def descendants(self, category):
        q = Q(pk=category.pk)
        for child in category.children.all():
            q |= Q(pk__in=self.descendants(child))
        return self.filter(q)

    def ancestors(self, category):
        q = Q(pk=category.pk)
        if category.parent:
            q |= Q(pk__in=self.ancestors(category.parent))
        return self.filter(q)


class BrandManager(QuerySet):
    def search(self, search_string):
        qs = self.filter(name__isnull=False)

        if search_string != "":
            for qstring in search_string.split(" "):
                qs = self.filter(
                    Q(name__icontains=qstring)
                    | Q(nameAR__icontains=qstring)
                ).order_by('id').distinct('id')
            return qs

        return qs.order_by('-created_at')
