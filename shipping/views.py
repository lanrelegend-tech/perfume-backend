from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAdminUser

from .models import ShippingRate
from .serializers import ShippingRateSerializer


class ShippingRateListCreateView(generics.ListCreateAPIView):
    serializer_class = ShippingRateSerializer

    def get_queryset(self):
        return ShippingRate.objects.filter(
            is_active=True
        ).order_by("state")

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]

        return [IsAdminUser()]


class ShippingRateDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ShippingRateSerializer

    def get_queryset(self):
        return ShippingRate.objects.all()

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]

        return [IsAdminUser()]