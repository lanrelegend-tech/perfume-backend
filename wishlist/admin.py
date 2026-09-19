from django.contrib import admin
from .models import Wishlist


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "user__username",
        "user__email",
    )

    filter_horizontal = (
        "products",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )