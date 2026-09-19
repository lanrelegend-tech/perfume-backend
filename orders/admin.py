from django.contrib import admin

from .models import Order, OrderItem
from .email import (
    send_order_shipped_email,
    send_order_delivered_email,
)
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

    readonly_fields = (
        "product",
        "product_name",
        "product_brand",
        "product_price",
        "quantity",
        "subtotal",
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):

    list_display = (
        "order_number",
        "user",
        "full_name",
        "total_amount",
        "status",
        "payment_status",
        "courier",
        "tracking_number",
        "shipped_at",
        "delivered_at",
        "created_at",
    )

    list_filter = (
        "status",
        "payment_status",
        "courier",
        "created_at",
    )

    search_fields = (
        "order_number",
        "user__username",
        "user__email",
        "full_name",
        "phone",
        "email",
        "tracking_number",
    )

    readonly_fields = (
        "order_number",
        "user",
        "total_amount",
        "delivery_fee",
        "coupon",
        "discount_amount",
        "payment_reference",
        "shipped_at",
        "delivered_at",
        "created_at",
        "updated_at",
    )

    list_editable = (
        "status",
        "payment_status",
    )

    fieldsets = (
        (
            "Order Information",
            {
                "fields": (
                    "order_number",
                    "user",
                    "status",
                    "payment_status",
                    "total_amount",
                    "delivery_fee",
                    "coupon",
                    "discount_amount",
                )
            },
        ),

        (
            "Customer Information",
            {
                "fields": (
                    "full_name",
                    "phone",
                    "email",
                    "address",
                    "city",
                    "state",
                    "notes",
                )
            },
        ),

        (
            "Shipping & Tracking",
            {
                "fields": (
                    "courier",
                    "tracking_number",
                    "shipped_at",
                    "delivered_at",
                )
            },
        ),

        (
            "Payment",
            {
                "fields": (
                    "payment_reference",
                )
            },
        ),

        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )
    def save_model(self, request, obj, form, change):
        old_status = None

        if change:
            old_order = Order.objects.get(pk=obj.pk)
            old_status = old_order.status

        super().save_model(request, obj, form, change)

        if old_status != "shipped" and obj.status == "shipped":
            send_order_shipped_email(obj)

        if old_status != "delivered" and obj.status == "delivered":
            send_order_delivered_email(obj)
    inlines = [
        OrderItemInline,
    ]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):

    list_display = (
        "order",
        "product_name",
        "product_brand",
        "product_price",
        "quantity",
        "subtotal",
    )

    search_fields = (
        "order__order_number",
        "product_name",
        "product_brand",
    )

    readonly_fields = (
        "subtotal",
    )