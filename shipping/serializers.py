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
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]