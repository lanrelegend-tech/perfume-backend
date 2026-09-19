from django.urls import path

from .views import (
    CartView,
    AddToCartView,
    UpdateCartItemView,
    RemoveFromCartView,
)


urlpatterns = [
    path("", CartView.as_view(), name="cart"),
    path("add/", AddToCartView.as_view(), name="add-to-cart"),
    path(
        "items/<int:item_id>/",
        UpdateCartItemView.as_view(),
        name="update-cart-item"
    ),
    path(
        "items/<int:item_id>/remove/",
        RemoveFromCartView.as_view(),
        name="remove-from-cart"
    ),
]