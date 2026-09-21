from django.urls import path

from .views import (
    ValidateCouponView,
    AdminCouponListCreateView,
    AdminCouponDetailView,
)

urlpatterns = [
    path(
        "validate/",
        ValidateCouponView.as_view(),
        name="validate-coupon",
    ),

    path(
        "admin/",
        AdminCouponListCreateView.as_view(),
        name="admin-coupon-list-create",
    ),

    path(
        "admin/<int:pk>/",
        AdminCouponDetailView.as_view(),
        name="admin-coupon-detail",
    ),
]