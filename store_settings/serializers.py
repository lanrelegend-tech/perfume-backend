from rest_framework import serializers

from .models import StoreSettings


class StoreSettingsSerializer(serializers.ModelSerializer):

    class Meta:
        model = StoreSettings

        fields = [
            "id",
            "store_name",
            "store_email",
            "store_phone",
            "store_address",
            "currency",
            "free_shipping_threshold",
            "maintenance_mode",
            "instagram_url",
            "facebook_url",
            "tiktok_url",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "updated_at",
        ]