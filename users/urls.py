from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from .views import RegisterView, MeView, CustomerProfileView
from .views import (
    RegisterView,
    MeView,
    CustomerProfileView,
    AdminCustomerListView,
    AdminCustomerDetailView,
    VerifyEmailView,
    ResendVerificationView,
    ForgotPasswordView, 
    ResetPasswordView,
    AdminGuestCustomerListView,
)


urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("me/", MeView.as_view(), name="me"),
    path("profile/", CustomerProfileView.as_view(), name="customer-profile"),
    path(
    "admin/customers/",
    AdminCustomerListView.as_view(),
    name="admin-customer-list"
),

path(
    "admin/customers/<int:pk>/",
    AdminCustomerDetailView.as_view(),
    name="admin-customer-detail"
),
path(
    "verify-email/",
    VerifyEmailView.as_view(),
    name="verify-email"
),
path(
    "resend-verification/",
    ResendVerificationView.as_view(),
    name="resend-verification"
),
path(
    "forgot-password/",
    ForgotPasswordView.as_view(),
    name="forgot-password"
),
path(
    "reset-password/",
    ResetPasswordView.as_view(),
    name="reset-password"
),
path(
    "admin/guests/",
    AdminGuestCustomerListView.as_view(),
    name="admin-guest-customer-list",
),
]