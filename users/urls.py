from django.urls import path

from .views import (
    MeView,
    CustomerProfileView,
    AdminCustomerListView,
    AdminCustomerDetailView,
    AdminGuestCustomerListView,
)

urlpatterns = [
    path(
        "me/",
        MeView.as_view(),
        name="me",
    ),

    path(
        "profile/",
        CustomerProfileView.as_view(),
        name="customer-profile",
    ),

    path(
        "admin/customers/",
        AdminCustomerListView.as_view(),
        name="admin-customer-list",
    ),

    path(
        "admin/customers/<int:pk>/",
        AdminCustomerDetailView.as_view(),
        name="admin-customer-detail",
    ),

    path(
        "admin/guests/",
        AdminGuestCustomerListView.as_view(),
        name="admin-guest-customer-list",
    ),
]
