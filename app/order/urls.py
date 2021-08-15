from rest_framework.routers import DefaultRouter

from django.urls import path, include

from . import rest

router = DefaultRouter()

urlpatterns = [
    path("order-list/", rest.OrderList.as_view()),
    path("order-details/<int:pk>/", rest.OrderDetails.as_view()),

    path("", include(router.urls)),
]
