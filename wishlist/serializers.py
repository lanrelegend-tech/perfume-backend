from rest_framework import serializers
from .models import Wishlist


class WishlistSerializer(serializers.ModelSerializer):
    products = serializers.SerializerMethodField()

    class Meta:
        model = Wishlist
        fields = [
            "id",
            "products",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "products",
            "created_at",
            "updated_at",
        ]

    def get_products(self, obj):
        from products.serializers import ProductSerializer

        return ProductSerializer(
            obj.products.all(),
            many=True,
            context=self.context
        ).data