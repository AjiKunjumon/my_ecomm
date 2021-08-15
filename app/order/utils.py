import time
from collections import OrderedDict

from django.utils.timezone import now
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from zappa.async import task
from fcm_django.models import FCMDevice

from app.order.serializers import OrderProdMinSerializer


class DeliveryLogPagination(PageNumberPagination):

    def get_paginated_response(self, data, extra_keys):
        order_prod = extra_keys['order_prod']
        if order_prod:
            prod_info_resp = OrderProdMinSerializer(order_prod).data
        else:
            prod_info_resp = None

        return Response(OrderedDict([
            ('prod_info', prod_info_resp),
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data),
        ]))
