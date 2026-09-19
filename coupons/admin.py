from django.contrib import admin
from .models import Coupon


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "discount_type",
        "discount_value",
        "minimum_order_amount",
        "maximum_discount",
        "usage_limit",
        "used_count",
        "expires_at",
        "is_active",
    )

    list_filter = (
        "discount_type",
        "is_active",
        "expires_at",
    )

    search_fields = (
        "code",
    )

    list_editable = (
        "discount_value",
        "minimum_order_amount",
        "maximum_discount",
        "usage_limit",
        "expires_at",
        "is_active",
    )

    readonly_fields = (
        "used_count",
        "created_at",
        "updated_at",
    )