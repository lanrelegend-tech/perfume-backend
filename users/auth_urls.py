from django.urls import path

from .views import (
    CSRFTokenView,
    CookieTokenObtainPairView,
    CookieTokenRefreshView,
    ForgotPasswordView,
    LogoutView,
    RegisterView,
    ResendVerificationView,
    ResetPasswordView,
    VerifyEmailLinkView,
    VerifyEmailView,
)


urlpatterns = [
    path("csrf/", CSRFTokenView.as_view(), name="csrf"),
    path("login/", CookieTokenObtainPairView.as_view(), name="login"),
    path("refresh/", CookieTokenRefreshView.as_view(), name="refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("register/", RegisterView.as_view(), name="register"),
    path("verify-email-link/", VerifyEmailLinkView.as_view(), name="verify-email-link"),
    path("verify-email/", VerifyEmailView.as_view(), name="verify-email"),
    path(
        "resend-verification/",
        ResendVerificationView.as_view(),
        name="resend-verification",
    ),
    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot-password"),
    path("reset-password/", ResetPasswordView.as_view(), name="reset-password"),
]
