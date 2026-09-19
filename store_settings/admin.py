from django.contrib import admin

from .models import StoreSettings


@admin.register(StoreSettings)
class StoreSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "store_name",
        "store_email",
        "store_phone",
        "currency",
        "maintenance_mode",
        "updated_at",
    )