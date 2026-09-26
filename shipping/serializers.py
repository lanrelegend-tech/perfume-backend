from rest_framework import serializers

from .models import ShippingRate


class ShippingRateSerializer(
    serializers.ModelSerializer
):
    class Meta:
        model = ShippingRate

        fields = [
            "id",
            "state",
            "city",
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
            getattr(
                self.instance,
                "delivery_type",
                "state",
            ),
        )

        state = attrs.get(
            "state",
            getattr(
                self.instance,
                "state",
                None,
            ),
        )

        city = attrs.get(
            "city",
            getattr(
                self.instance,
                "city",
                None,
            ),
        )

        pickup_address = attrs.get(
            "pickup_address",
            getattr(
                self.instance,
                "pickup_address",
                "",
            ),
        )

        if delivery_type not in [
            "state",
            "pickup",
        ]:
            raise serializers.ValidationError(
                {
                    "delivery_type": (
                        "Delivery type must be "
                        "state or pickup."
                    )
                }
            )

        if delivery_type == "state":
            if not state or not state.strip():
                raise serializers.ValidationError(
                    {
                        "state": (
                            "State name is required."
                        )
                    }
                )

            state = state.strip()

            if city:
                city = city.strip()

            attrs["state"] = state
            attrs["city"] = city or None
            attrs["pickup_address"] = ""

            queryset = ShippingRate.objects.filter(
                delivery_type="state",
                state__iexact=state,
            )

            if city:
                queryset = queryset.filter(
                    city__iexact=city
                )
            else:
                queryset = queryset.filter(
                    city__isnull=True
                )

            if self.instance:
                queryset = queryset.exclude(
                    pk=self.instance.pk
                )

            if queryset.exists():
                if city:
                    raise serializers.ValidationError(
                        {
                            "city": (
                                "A shipping rate for "
                                f"{city}, {state} "
                                "already exists."
                            )
                        }
                    )

                raise serializers.ValidationError(
                    {
                        "state": (
                            f"A state shipping rate "
                            f"for {state} already exists."
                        )
                    }
                )

        elif delivery_type == "pickup":
            if (
                not pickup_address
                or not pickup_address.strip()
            ):
                raise serializers.ValidationError(
                    {
                        "pickup_address": (
                            "Pickup address is required."
                        )
                    }
                )

            attrs["state"] = None
            attrs["city"] = None
            attrs["pickup_address"] = (
                pickup_address.strip()
            )

        return attrs