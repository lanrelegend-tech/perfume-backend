from django.urls import path

from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenObtainPairView,
    TokenBlacklistView,
)

from .serializers import EmailTokenObtainPairSerializer

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
    LogoutView,
    VerifyEmailLinkView,
)

urlpatterns = [
    path(
        "register/",
        RegisterView.as_view(),
        name="register",
    ),
    path(
    "verify-email-link/",
    VerifyEmailLinkView.as_view(),
),

    path(
        "login/",
        TokenObtainPairView.as_view(
            serializer_class=EmailTokenObtainPairSerializer
        ),
        name="token_obtain_pair",
    ),

    path(
        "refresh/",
        TokenRefreshView.as_view(),
        name="token_refresh",
    ),

    path(
    "logout/",
    LogoutView.as_view(),
    name="logout",
),

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
        "verify-email/",
        VerifyEmailView.as_view(),
        name="verify-email",
    ),

    path(
        "resend-verification/",
        ResendVerificationView.as_view(),
        name="resend-verification",
    ),

    path(
        "forgot-password/",
        ForgotPasswordView.as_view(),
        name="forgot-password",
    ),

    path(
        "reset-password/",
        ResetPasswordView.as_view(),
        name="reset-password",
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