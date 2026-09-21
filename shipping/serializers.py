from rest_framework import serializers
from .models import ShippingRate


class ShippingRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingRate
        fields = [
            "id",
            "state",
            "delivery_type",
            "delivery_fee",
            "pickup_address",
            "is_active",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        delivery_type = attrs.get(
            "delivery_type",
            getattr(self.instance, "delivery_type", "state"),
        )

        state = attrs.get(
            "state",
            getattr(self.instance, "state", None),
        )

        pickup_address = attrs.get(
            "pickup_address",
            getattr(self.instance, "pickup_address", ""),
        )

        if delivery_type not in ["state", "pickup"]:
            raise serializers.ValidationError(
                {
                    "delivery_type": "Delivery type must be state or pickup."
                }
            )

        if delivery_type == "state":
            if not state or not state.strip():
                raise serializers.ValidationError(
                    {
                        "state": "State name is required."
                    }
                )

            attrs["state"] = state.strip()
            attrs["pickup_address"] = ""

        elif delivery_type == "pickup":
            if not pickup_address or not pickup_address.strip():
                raise serializers.ValidationError(
                    {
                        "pickup_address": "Pickup address is required."
                    }
                )

            attrs["state"] = None
            attrs["pickup_address"] = pickup_address.strip()

        return attrs