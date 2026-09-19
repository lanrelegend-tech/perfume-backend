from rest_framework import generics
from .models import ShippingRate
from .serializers import ShippingRateSerializer


class ShippingRateListView(generics.ListAPIView):
    serializer_class = ShippingRateSerializer

    def get_queryset(self):
        return ShippingRate.objects.filter(
            is_active=True
        ).order_by("state")