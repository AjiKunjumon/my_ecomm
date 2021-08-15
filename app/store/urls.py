from rest_framework.routers import DefaultRouter

from django.urls import path, include

from . import rest

router = DefaultRouter()

urlpatterns = [
    path("add-seller/", rest.AddSeller.as_view()),
    path("edit-seller/<int:pk>/", rest.EditSeller.as_view()),
    path("sellers-list/", rest.SellerList.as_view()),
    path("sellers-list-collection/", rest.SellerListForCollection.as_view()),
    path("sellers-detail/<int:pk>/", rest.SellerDetails.as_view()),
    path("change-sellers-status/", rest.ChangeSellersStatus.as_view()),

    path("inventory-list/", rest.InventoryList.as_view()),
    path("inventories-set-add-quantity/", rest.InventoryQtyUpdate.as_view()),

    path("", include(router.urls)),
]
