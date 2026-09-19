from django.contrib import admin
from .models import ShippingRate


@admin.register(ShippingRate)
class ShippingRateAdmin(admin.ModelAdmin):
    list_display = (
        "state",
        "delivery_fee",
        "is_active",
        "created_at",
        "updated_at",
    )

    list_filter = (
        "is_active",
    )

    search_fields = (
        "state",
    )

    list_editable = (
        "delivery_fee",
        "is_active",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )