from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAdminUser

from .models import ShippingRate
from .serializers import ShippingRateSerializer


class ShippingRateListCreateView(generics.ListCreateAPIView):
    serializer_class = ShippingRateSerializer

    def get_queryset(self):
        user = self.request.user

        if user.is_authenticated and user.is_staff:
            return ShippingRate.objects.all().order_by(
                "delivery_type",
                "state",
                "id",
            )

        return ShippingRate.objects.filter(
            is_active=True
        ).order_by(
            "delivery_type",
            "state",
            "id",
        )

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]

        return [IsAdminUser()]


class ShippingRateDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ShippingRateSerializer

    def get_queryset(self):
        user = self.request.user

        if user.is_authenticated and user.is_staff:
            return ShippingRate.objects.all()

        return ShippingRate.objects.filter(
            is_active=True
        )

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]

        return [IsAdminUser()]