from rest_framework import serializers
from .models import Coupon


class CouponSerializer(serializers.ModelSerializer):
    def validate_usage_limit(self, value):
        if value == 0:
            raise serializers.ValidationError(
                "Enter a usage limit greater than 0, or leave it blank for "
                "unlimited use."
            )

        return value

    def validate_maximum_discount(self, value):
        if value == 0:
            raise serializers.ValidationError(
                "Enter a maximum discount greater than 0, or leave it blank "
                "for no maximum."
            )

        return value

    class Meta:
        model = Coupon
        fields = [
            "id",
            "code",
            "discount_type",
            "discount_value",
            "minimum_order_amount",
            "maximum_discount",
            "usage_limit",
            "used_count",
            "expires_at",
            "is_active",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "used_count",
            "created_at",
            "updated_at",
        ]
