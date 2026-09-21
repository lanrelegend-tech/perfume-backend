from rest_framework import generics
from .models import ShippingRate
from .serializers import ShippingRateSerializer


class ShippingRateListCreateView(generics.ListCreateAPIView):
    serializer_class = ShippingRateSerializer

    def get_queryset(self):
        return ShippingRate.objects.all().order_by("state")


class ShippingRateDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ShippingRateSerializer
    queryset = ShippingRate.objects.all()