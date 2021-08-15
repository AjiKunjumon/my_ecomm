from rest_framework.routers import DefaultRouter

from django.urls import path, include, re_path

from app.views import ResetPassword
from . import rest

router = DefaultRouter()

urlpatterns = [
    path("sellers/login/", rest.SellerLoginView.as_view()),
    path("seller-details-by-token/", rest.SellerDetailByToken.as_view()),
    path("forgot-password/", rest.ForgotPassword.as_view()),

    path("customers-list/", rest.CustomerList.as_view()),
    path("customer-details/<int:pk>/", rest.CustomerDetails.as_view()),
    path("customer-add-address/", rest.AddAddress.as_view()),
    path("customer-edit-address/<int:pk>/", rest.EditAddress.as_view()),
    path("customer-edit/<int:pk>/", rest.CustomerEdit.as_view()),
    path("change-customers-status/", rest.ChangeCustomerStatus.as_view()),
    path("shipping-areas-list/", rest.ShippingAreaList.as_view()),
    path("guest-list/", rest.GuestList.as_view()),

    re_path(
        r'^reset-password/(?P<resetPassString>[^/]+)/$',
        ResetPassword.as_view(), name='reset-password'
    ),

    path("", include(router.urls)),
]
