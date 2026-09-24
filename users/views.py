from datetime import timedelta

import resend

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q, Count, Sum
from django.utils import timezone

from rest_framework_simplejwt.token_blacklist.models import (
    OutstandingToken,
    BlacklistedToken,
)

from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator

from rest_framework import generics, status
from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
    IsAdminUser,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Order

from .models import (
    EmailVerificationCode,
    PasswordResetCode,
    CustomerProfile,
)

from .serializers import (
    RegisterSerializer,
    UserSerializer,
    CustomerProfileSerializer,
    AdminCustomerSerializer,
    VerifyEmailSerializer,
    ResendVerificationSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
)


# =========================================================
# REGISTER
# =========================================================

@method_decorator(
    ratelimit(
        key="ip",
        rate="5/h",
        method="POST",
        block=True
    ),
    name="dispatch",
)
class RegisterView(generics.CreateAPIView):

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):

        serializer = self.get_serializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        try:
            self.perform_create(serializer)
        except Exception:
            return Response(
                {
                    "error": "Registration failed",
                    "detail": (
                        "Unable to create your account. "
                        "Please try again later."
                    ),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        headers = self.get_success_headers(
            serializer.data
        )

        return Response(
            {
                **serializer.data,
                "verification_required": True,
                "message": (
                    "Account created. "
                    "Please verify your email."
                ),
            },
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def perform_create(self, serializer):

        user = serializer.save()

        verification, created = (
            EmailVerificationCode.objects.get_or_create(
                user=user
            )
        )

        code = verification.generate_code()

        try:

            resend.api_key = settings.RESEND_API_KEY

            resend.Emails.send(
                {
                    "from": "ORENTEMIST <onboarding@resend.dev>",
                    "to": [user.email],
                    "subject": "Verify your email",
                    "text": (
                        f"Hello {user.first_name or user.username},\n\n"
                        "Welcome to ORENTEMIST! 🎉\n\n"
                        "Thank you for creating an account with us.\n\n"
                        "Your email verification code is:\n\n"
                        f"{code}\n\n"
                        "This code will expire in 10 minutes.\n\n"
                        "Please enter this code on the verification page to complete your account registration.\n\n"
                        "If you did not create this account, you can safely ignore this email.\n\n"
                        "Thank you,\nORENTEMIST Customer Support"
                    ),
                }
            )

        except Exception:
            raise


# =========================================================
# VERIFY EMAIL
# =========================================================

@method_decorator(
    ratelimit(
        key="ip",
        rate="5/m",
        method="POST",
        block=True
    ),
    name="dispatch",
)
class VerifyEmailView(APIView):

    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):

        serializer = VerifyEmailSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        email = (
            serializer.validated_data["email"]
            .strip()
            .lower()
        )

        submitted_code = (
            serializer.validated_data["code"]
        )

        user = (
            User.objects
            .filter(email__iexact=email)
            .order_by("id")
            .first()
        )

        if not user:
            return Response(
                {
                    "error":
                        "Invalid verification code"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:

            verification = (
                EmailVerificationCode.objects.get(
                    user=user
                )
            )

        except EmailVerificationCode.DoesNotExist:

            return Response(
                {
                    "error":
                        "Invalid verification code"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if verification.verified_at:

            return Response(
                {
                    "message":
                        "Email is already verified"
                },
                status=status.HTTP_200_OK,
            )

        if (
            verification.attempts
            >= verification.MAX_ATTEMPTS
        ):

            return Response(
                {
                    "error":
                        "Too many incorrect attempts. "
                        "Please request a new code."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if timezone.now() >= verification.expires_at:

            return Response(
                {
                    "error":
                        "Verification code has expired"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not check_password(
            submitted_code,
            verification.code
        ):

            verification.attempts += 1

            verification.save(
                update_fields=["attempts"]
            )

            if (
                verification.attempts
                >= verification.MAX_ATTEMPTS
            ):

                return Response(
                    {
                        "error":
                            "Too many incorrect attempts. "
                            "Please request a new code."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response(
                {
                    "error":
                        "Invalid verification code"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        verification.verified_at = timezone.now()

        verification.save(
            update_fields=["verified_at"]
        )

        Order.objects.filter(
            user__isnull=True,
            email__iexact=user.email
        ).update(
            user=user
        )

        return Response(
            {
                "message":
                    "Email verified successfully"
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# RESEND VERIFICATION
# =========================================================

@method_decorator(
    ratelimit(
        key="ip",
        rate="3/10m",
        method="POST",
        block=True
    ),
    name="dispatch",
)
class ResendVerificationView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):

        serializer = ResendVerificationSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        email = (
            serializer.validated_data["email"]
            .strip()
            .lower()
        )

        generic_response = Response(
            {
                "message":
                    "If an account exists with this email, "
                    "a verification code has been sent."
            },
            status=status.HTTP_200_OK,
        )

        user = (
            User.objects
            .filter(email__iexact=email)
            .order_by("id")
            .first()
        )

        if not user:
            return generic_response

        try:

            verification = (
                EmailVerificationCode.objects.get(
                    user=user
                )
            )

        except EmailVerificationCode.DoesNotExist:

            verification = (
                EmailVerificationCode.objects.create(
                    user=user,
                    code="!",
                    expires_at=(
                        timezone.now()
                        + timedelta(minutes=10)
                    ),
                )
            )

        if verification.verified_at:
            return generic_response

        code = verification.generate_code()

        try:

            resend.api_key = settings.RESEND_API_KEY

            resend.Emails.send(
                {
                    "from": "ORENTEMIST <onboarding@resend.dev>",
                    "to": [user.email],
                    "subject":
                        "Your new ORENTEMIST verification code",
                    "text": (
                        f"Hello {user.first_name or user.username},\n\n"
                        "Here is your new ORENTEMIST email verification code:\n\n"
                        f"{code}\n\n"
                        "This code will expire in 10 minutes.\n\n"
                        "If you did not request this code, you can safely ignore this email.\n\n"
                        "Thank you,\nORENTEMIST Customer Support"
                    ),
                }
            )

        except Exception:

            return Response(
                {
                    "error":
                        "Unable to send the verification email. "
                        "Please try again later."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return generic_response


# =========================================================
# FORGOT PASSWORD
# =========================================================

@method_decorator(
    ratelimit(
        key="ip",
        rate="3/10m",
        method="POST",
        block=True
    ),
    name="dispatch",
)
class ForgotPasswordView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):

        serializer = ForgotPasswordSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        email = (
            serializer.validated_data["email"]
            .strip()
            .lower()
        )

        generic_response = Response(
            {
                "message":
                    "If an account exists with this email, "
                    "a password reset code has been sent."
            },
            status=status.HTTP_200_OK,
        )

        user = (
            User.objects
            .filter(email__iexact=email)
            .first()
        )

        if not user:
            return generic_response

        reset_code, created = (
            PasswordResetCode.objects.get_or_create(
                user=user
            )
        )

        code = reset_code.generate_code()

        try:

            send_mail(
                subject="Reset your password",
                message=(
                    f"Hello {user.first_name or user.username},\n\n"
                    "We received a request to reset your password.\n\n"
                    "Your password reset code is:\n\n"
                    f"{code}\n\n"
                    "This code will expire in 10 minutes.\n\n"
                    "If you did not request a password reset, you can safely ignore this email.\n\n"
                    "Thank you,\nORENTEMIST Customer Support"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )

        except Exception:

            return generic_response

        return generic_response


# =========================================================
# RESET PASSWORD
# =========================================================

@method_decorator(
    ratelimit(
        key="ip",
        rate="5/m",
        method="POST",
        block=True
    ),
    name="dispatch",
)
class ResetPasswordView(APIView):

    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):

        serializer = ResetPasswordSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        email = (
            serializer.validated_data["email"]
            .strip()
            .lower()
        )

        submitted_code = (
            serializer.validated_data["code"]
        )

        new_password = (
            serializer.validated_data["new_password"]
        )

        user = (
            User.objects
            .filter(email__iexact=email)
            .first()
        )

        if not user:

            return Response(
                {
                    "error":
                        "Invalid password reset code"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:

            reset_code = (
                PasswordResetCode.objects.get(
                    user=user
                )
            )

        except PasswordResetCode.DoesNotExist:

            return Response(
                {
                    "error":
                        "Invalid password reset code"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if (
            reset_code.attempts
            >= reset_code.MAX_ATTEMPTS
        ):

            return Response(
                {
                    "error":
                        "Too many incorrect attempts. "
                        "Please request a new code."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if timezone.now() >= reset_code.expires_at:

            return Response(
                {
                    "error":
                        "Password reset code has expired"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not check_password(
            submitted_code,
            reset_code.code
        ):

            reset_code.attempts += 1

            reset_code.save(
                update_fields=["attempts"]
            )

            if (
                reset_code.attempts
                >= reset_code.MAX_ATTEMPTS
            ):

                return Response(
                    {
                        "error":
                            "Too many incorrect attempts. "
                            "Please request a new code."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response(
                {
                    "error":
                        "Invalid password reset code"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:

            validate_password(
                new_password,
                user
            )

        except ValidationError as error:

            return Response(
                {
                    "error":
                        error.messages
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)

        user.save(
            update_fields=["password"]
        )

        # =================================================
        # IMMEDIATELY REVOKE ALL EXISTING ACCESS TOKENS
        # =================================================

        profile, created = (
            CustomerProfile.objects.get_or_create(
                user=user
            )
        )

        profile.session_version += 1

        profile.save(
            update_fields=["session_version"]
        )

        # =================================================
        # BLACKLIST ALL REFRESH TOKENS
        # =================================================

        for token in OutstandingToken.objects.filter(
            user=user
        ):

            BlacklistedToken.objects.get_or_create(
                token=token
            )

        reset_code.delete()

        return Response(
            {
                "message":
                    "Password reset successfully"
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# CURRENT USER
# =========================================================

class MeView(generics.RetrieveAPIView):

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


# =========================================================
# CUSTOMER PROFILE
# =========================================================

class CustomerProfileView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        profile, created = (
            CustomerProfile.objects.get_or_create(
                user=request.user
            )
        )

        serializer = CustomerProfileSerializer(
            profile
        )

        return Response(
            serializer.data
        )

    def patch(self, request):

        profile, created = (
            CustomerProfile.objects.get_or_create(
                user=request.user
            )
        )

        serializer = CustomerProfileSerializer(
            profile,
            data=request.data,
            partial=True
        )

        serializer.is_valid(
            raise_exception=True
        )

        serializer.save()

        return Response(
            serializer.data
        )


# =========================================================
# ADMIN CUSTOMER LIST
# =========================================================

class AdminCustomerListView(generics.ListAPIView):

    serializer_class = AdminCustomerSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):

        queryset = (
            User.objects
            .filter(is_staff=False)
            .select_related("profile")
            .prefetch_related("orders")
            .order_by("-date_joined")
        )

        search = self.request.query_params.get(
            "search"
        )

        if search:

            queryset = queryset.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )

        is_active = self.request.query_params.get(
            "is_active"
        )

        if is_active == "true":

            queryset = queryset.filter(
                is_active=True
            )

        elif is_active == "false":

            queryset = queryset.filter(
                is_active=False
            )

        return queryset


# =========================================================
# ADMIN CUSTOMER DETAIL
# =========================================================

# =========================================================
# ADMIN CUSTOMER DETAIL
# =========================================================

class AdminCustomerDetailView(
    generics.RetrieveUpdateAPIView
):

    serializer_class = AdminCustomerSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):

        return (
            User.objects
            .filter(is_staff=False)
            .select_related("profile")
            .prefetch_related("orders")
        )

    @transaction.atomic
    def update(self, request, *args, **kwargs):

        user = self.get_object()

        old_is_active = user.is_active

        serializer = self.get_serializer(
            user,
            data=request.data,
            partial=kwargs.pop("partial", False),
        )

        serializer.is_valid(
            raise_exception=True
        )

        updated_user = serializer.save()

        new_is_active = updated_user.is_active

        # =================================================
        # ACCOUNT STATUS CHANGED
        # =================================================

        if old_is_active != new_is_active:

            profile, _ = (
                CustomerProfile.objects.get_or_create(
                    user=updated_user
                )
            )

            # Immediately invalidate every existing
            # access token for this customer.
            profile.session_version += 1

            profile.save(
                update_fields=[
                    "session_version"
                ]
            )

            # Blacklist all existing refresh tokens.
            outstanding_tokens = (
                OutstandingToken.objects.filter(
                    user=updated_user
                )
            )

            for token in outstanding_tokens:

                BlacklistedToken.objects.get_or_create(
                    token=token
                )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


# =========================================================
# ADMIN GUEST CUSTOMERS
# =========================================================

class AdminGuestCustomerListView(APIView):

    permission_classes = [IsAdminUser]

    def get(self, request):

        guests = (
            Order.objects
            .filter(user__isnull=True)
            .exclude(email__isnull=True)
            .exclude(email="")
            .values("email")
            .annotate(
                order_count=Count("id"),
                total_spent=Sum(
                    "total_amount",
                    filter=Q(
                        payment_status="paid"
                    )
                ),
            )
            .order_by("-order_count")
        )

        results = []

        for guest in guests:

            results.append(
                {
                    "id":
                        f"guest-{guest['email']}",

                    "email":
                        guest["email"],

                    "first_name":
                        "",

                    "last_name":
                        "",

                    "username":
                        "",

                    "phone":
                        "",

                    "address":
                        "",

                    "city":
                        "",

                    "state":
                        "",

                    "order_count":
                        guest["order_count"],

                    "total_spent":
                        guest["total_spent"] or 0,

                    "is_active":
                        True,

                    "date_joined":
                        None,

                    "customer_type":
                        "guest",
                }
            )

        return Response(
            {
                "count":
                    len(results),

                "results":
                    results,
            }
        )

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile, _ = CustomerProfile.objects.get_or_create(
            user=request.user
        )

        # Immediately invalidate all existing access tokens.
        profile.session_version += 1
        profile.save(
            update_fields=["session_version"]
        )

        # Blacklist every outstanding refresh token
        # belonging to this user.
        outstanding_tokens = OutstandingToken.objects.filter(
            user=request.user
        )

        for token in outstanding_tokens:
            BlacklistedToken.objects.get_or_create(
                token=token
            )

        return Response(
            {
                "message": "Logged out successfully."
            },
            status=status.HTTP_200_OK,
        )
    