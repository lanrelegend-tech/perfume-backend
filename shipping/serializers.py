from rest_framework import serializers
from .models import ShippingRate


class ShippingRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingRate
        fields = [
            "id",
            "state",
            "delivery_fee",
            "is_active",
        ]