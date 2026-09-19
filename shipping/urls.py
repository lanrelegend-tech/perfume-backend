from django.urls import path
from .views import ShippingRateListView


urlpatterns = [
    path("", ShippingRateListView.as_view(), name="shipping-rates"),
]