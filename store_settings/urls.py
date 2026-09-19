from django.urls import path

from .views import (
    StoreSettingsView,
    AdminStoreSettingsView,
)


urlpatterns = [
    path(
        "",
        StoreSettingsView.as_view(),
        name="store-settings"
    ),

    path(
        "admin/",
        AdminStoreSettingsView.as_view(),
        name="admin-store-settings"
    ),
]