from django.urls import path

from .views import (
    ShippingRateListCreateView,
    ShippingRateDetailView,
)


urlpatterns = [
    path(
        "",
        ShippingRateListCreateView.as_view(),
        name="shipping-list-create",
    ),
    path(
        "<int:pk>/",
        ShippingRateDetailView.as_view(),
        name="shipping-detail",
    ),
]