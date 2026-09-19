from django.urls import path

from .views import (
    ProductReviewListView,
    CreateReviewView,
    ReviewDetailView,
)


urlpatterns = [
    path(
        "products/<int:product_id>/",
        ProductReviewListView.as_view(),
        name="product-reviews",
    ),

    path(
        "products/<int:product_id>/create/",
        CreateReviewView.as_view(),
        name="create-review",
    ),

    path(
        "<int:pk>/",
        ReviewDetailView.as_view(),
        name="review-detail",
    ),
]