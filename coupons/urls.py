from django.urls import path

from .views import ValidateCouponView


urlpatterns = [
    path(
        "validate/",
        ValidateCouponView.as_view(),
        name="validate-coupon",
    ),
]