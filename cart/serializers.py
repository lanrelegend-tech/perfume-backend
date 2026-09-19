from rest_framework import serializers
from .models import Cart, CartItem


class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(
        source="product.name",
        read_only=True
    )

    variant_id = serializers.IntegerField(
        source="variant.id",
        read_only=True
    )

    size = serializers.CharField(
        source="variant.size",
        read_only=True
    )

    product_price = serializers.DecimalField(
        source="variant.price",
        max_digits=10,
        decimal_places=2,
        read_only=True
    )

    product_image = serializers.ImageField(
        source="product.image",
        read_only=True
    )

    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            "id",
            "product",
            "product_name",
            "variant_id",
            "size",
            "product_price",
            "product_image",
            "quantity",
            "subtotal",
        ]

    def get_subtotal(self, obj):
        if obj.variant:
            return obj.variant.price * obj.quantity

        return obj.product.price * obj.quantity


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(
        many=True,
        read_only=True
    )

    total = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = [
            "id",
            "items",
            "total",
            "created_at",
            "updated_at",
        ]

    def get_total(self, obj):
        total = 0

        for item in obj.items.all():
            if item.variant:
                total += item.variant.price * item.quantity
            else:
                total += item.product.price * item.quantity

        return total