from django.urls import path

from .views import (
    ProductReviewListView,
    CreateReviewView,
    ReviewDetailView,
    AdminReviewListView,
    AdminReviewDeleteView,
)


urlpatterns = [
    path(
        "product/<int:product_id>/",
        ProductReviewListView.as_view(),
        name="product-reviews",
    ),

    path(
        "product/<int:product_id>/create/",
        CreateReviewView.as_view(),
        name="create-review",
    ),

    path(
        "<int:pk>/",
        ReviewDetailView.as_view(),
        name="review-detail",
    ),

    path(
        "admin/",
        AdminReviewListView.as_view(),
        name="admin-reviews",
    ),

    path(
        "admin/<int:pk>/",
        AdminReviewDeleteView.as_view(),
        name="admin-review-delete",
    ),
]