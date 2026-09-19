from django.urls import path
from .views import AdminRefundPaymentView

from .views import (
    OrderListView,
    OrderDetailView,
    OrderTrackingView,
    CreateOrderView,
    InitializePaymentView,
    VerifyPaymentView,
    PaystackWebhookView,
    AdminDashboardView,
    AdminOrderListView,
    AdminOrderDetailView,
    AdminRefundListView,
     MyOrderListView,
   
    
)


urlpatterns = [
    path(
        "",
        OrderListView.as_view(),
        name="order-list"
    ),

    path(
        "create/",
        CreateOrderView.as_view(),
        name="create-order"
    ),

    path(
        "<int:order_id>/pay/",
        InitializePaymentView.as_view(),
        name="initialize-payment"
    ),

    path(
        "verify-payment/",
        VerifyPaymentView.as_view(),
        name="verify-payment"
    ),

    path(
        "paystack/webhook/",
        PaystackWebhookView.as_view(),
        name="paystack-webhook"
    ),
    path(
    "my-orders/",
    MyOrderListView.as_view(),
    name="my-orders",
),
    path(
        "<int:pk>/tracking/",
        OrderTrackingView.as_view(),
        name="order-tracking"
    ),
    path(
    "admin/orders/<int:order_id>/refund/",
    AdminRefundPaymentView.as_view(),
    name="admin-refund-payment"
    ),
    
    path(
        "<int:pk>/",
        OrderDetailView.as_view(),
        name="order-detail"
    ),
    path(
    "admin/dashboard/",
    AdminDashboardView.as_view(),
    name="admin-dashboard"
    ),

    path(
    "admin/refunds/",
    AdminRefundListView.as_view(),
    name="admin-refund-list"
    ),
    path(
    "admin/",
    AdminOrderListView.as_view(),
    name="admin-order-list"
    ),
    path(
    "admin/<int:pk>/",
    AdminOrderDetailView.as_view(),
    name="admin-order-detail"
    ),
]