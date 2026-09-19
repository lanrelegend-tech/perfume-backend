from django.urls import path

from .views import (
    WishlistView,
    AddToWishlistView,
    RemoveFromWishlistView,
)


urlpatterns = [
    path("", WishlistView.as_view(), name="wishlist"),
    path("add/", AddToWishlistView.as_view(), name="add-to-wishlist"),
    path(
        "<int:product_id>/remove/",
        RemoveFromWishlistView.as_view(),
        name="remove-from-wishlist",
    ),
]