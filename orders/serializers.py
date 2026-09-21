from rest_framework import serializers
from .models import Refund

from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    product_image = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product",
            "variant",
            "product_name",
            "product_brand",
            "variant_size",
            "product_price",
            "product_image",
            "quantity",
            "subtotal",
        ]

    def get_product_image(self, obj):
        if not obj.product:
            return None

        image = obj.product.image

        if not image:
            return None

        try:
            return image.url
        except Exception:
            return None
        

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(
        many=True,
        read_only=True
    )

    status_history = serializers.SerializerMethodField()

    def get_status_history(self, obj):
        return [
            {
                "id": history.id,
                "status": history.status,
                "changed_by": (
                    history.changed_by.username
                    if history.changed_by
                    else None
                ),
                "note": history.note,
                "created_at": history.created_at,
            }
            for history in obj.status_history.all()
        ]

    class Meta:
        model = Order

        fields = [
            "id",
            "order_number",
            "items",
            "total_amount",
            "delivery_fee",
            "status",
            "payment_status",
            "payment_reference",
            "full_name",
            "phone",
            "email",
            "address",
            "city",
            "state",
            "notes",
            "courier",
            "tracking_number",
            "shipped_at",
            "delivered_at",
            "created_at",
            "updated_at",
            "coupon",
            "discount_amount",
             "status_history",
        ]

        read_only_fields = [
            "id",
            "order_number",
            "items",
            "total_amount",
            "delivery_fee",
            "coupon",
            "discount_amount",
            "status",
            "payment_status",
            "payment_reference",
            "courier",
            "tracking_number",
            "shipped_at",
            "delivered_at",
            "created_at",
            "updated_at",
        ]


class AdminOrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(
        many=True,
        read_only=True
    )
    status_history = serializers.SerializerMethodField()

    def get_status_history(self, obj):
        return [
            {
                "id": history.id,
                "status": history.status,
                "changed_by": (
                    history.changed_by.username
                    if history.changed_by
                    else None
                ),
                "note": history.note,
                "created_at": history.created_at,
            }
            for history in obj.status_history.all()
        ]
    class Meta:
        model = Order

        fields = [
            "id",
            "order_number",
            "user",
            "items",
            "total_amount",
            "delivery_fee",
            "coupon",
            "discount_amount",
            "status",
            "payment_status",
            "payment_reference",
            "full_name",
            "phone",
            "email",
            "address",
            "city",
            "state",
            "notes",
            "courier",
            "tracking_number",
            "shipped_at",
            "delivered_at",
            "created_at",
            "updated_at",
             "status_history",
        ]

        read_only_fields = [
            "id",
            "order_number",
            "user",
            "items",
            "total_amount",
            "delivery_fee",
            "coupon",
            "discount_amount",
            "payment_reference",
            "shipped_at",
            "delivered_at",
            "created_at",
            "updated_at",
            "status_history",
        ]

class RefundSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(
        source="order.order_number",
        read_only=True
    )

    admin_name = serializers.CharField(
        source="processed_by.username",
        read_only=True
    )

    class Meta:
        model = Refund
        fields = [
            "id",
            "order",
            "order_number",
            "amount",
            "reason",
            "processed_by",
            "admin_name",
            "paystack_reference",
            "status",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "processed_by",
            "admin_name",
            "paystack_reference",
            "status",
            "created_at",
            "updated_at",
        ]        
     