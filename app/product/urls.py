from rest_framework.routers import DefaultRouter

from django.urls import path, include
from . import rest

router = DefaultRouter()

urlpatterns = [
    path("brand-list/", rest.BrandList.as_view()),
    path("brand-list-filter/", rest.BrandList.as_view()),
    path("brand-detail/<int:pk>/", rest.BrandDetail.as_view()),
    path("add-brand/", rest.AddBrand.as_view()),
    path("edit-brand/<int:pk>/", rest.EditBrand.as_view()),
    path("delete-brands/", rest.DeleteBrands.as_view()),
    path("change-brands-status/", rest.ChangeBrandStatus.as_view()),

    path("product-list/", rest.ProductList.as_view()),
    path("child-product-list/", rest.ChildProductList.as_view()),
    path("change-products-status/", rest.ChangeProductStatus.as_view()),
    path("product-detail/<int:pk>/", rest.ProductDetail.as_view()),

    path("", include(router.urls)),
]
