from datetime import timedelta

import resend

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
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
# ORENTEMIST EMAIL HELPER
# =========================================================

def send_orentemist_email(
    to_email,
    subject,
    heading,
    message,
    code=None,
    footer_message=None,
):
    """
    Sends branded ORENTEMIST HTML emails through Resend.

    The email contains:
    - ORENTEMIST branding
    - Luxury black/white styling
    - Verification/reset code when provided
    - Plain-text fallback
    """

    code_block = ""

    if code:
        code_block = f"""
        <div style="
            margin: 30px 0;
            padding: 28px 20px;
            background: #f8f7f4;
            border: 1px solid #e5e2dc;
            border-radius: 18px;
            text-align: center;
        ">
            <p style="
                margin: 0 0 12px;
                color: #777777;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 3px;
                text-transform: uppercase;
            ">
                Your Security Code
            </p>

            <div style="
                font-size: 38px;
                font-weight: 700;
                letter-spacing: 9px;
                color: #000000;
                line-height: 1.2;
            ">
                {code}
            </div>

            <p style="
                margin: 14px 0 0;
                color: #888888;
                font-size: 12px;
            ">
                This code expires in 10 minutes.
            </p>
        </div>
        """

    footer = footer_message or (
        "If you did not request this email, "
        "you can safely ignore it."
    )

    expiry_text = (
        "This code expires in 10 minutes."
        if code
        else ""
    )

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
        >
        <title>{subject}</title>
    </head>

    <body style="
        margin: 0;
        padding: 0;
        background: #f4f3f0;
        font-family: Arial, Helvetica, sans-serif;
        color: #111111;
    ">

        <div style="
            width: 100%;
            padding: 45px 15px;
            box-sizing: border-box;
        ">

            <div style="
                max-width: 560px;
                margin: 0 auto;
                background: #ffffff;
                border: 1px solid #e8e6e1;
                border-radius: 24px;
                overflow: hidden;
            ">

                <!-- HEADER -->

                <div style="
                    padding: 34px 30px 30px;
                    border-bottom: 1px solid #eeeeee;
                    text-align: center;
                ">

                    <div style="
                        font-size: 21px;
                        font-weight: 700;
                        letter-spacing: 5px;
                        color: #000000;
                    ">
                        ORENTEMIST
                    </div>

                    <div style="
                        margin-top: 9px;
                        color: #999999;
                        font-size: 9px;
                        letter-spacing: 3px;
                        text-transform: uppercase;
                    ">
                        The Art of Fragrance
                    </div>

                </div>

                <!-- CONTENT -->

                <div style="
                    padding: 42px 35px;
                ">

                    <p style="
                        margin: 0 0 12px;
                        color: #999999;
                        font-size: 10px;
                        font-weight: 700;
                        letter-spacing: 3px;
                        text-transform: uppercase;
                    ">
                        ORENTEMIST
                    </p>

                    <h1 style="
                        margin: 0 0 18px;
                        font-size: 29px;
                        line-height: 1.3;
                        font-weight: 600;
                        letter-spacing: -0.5px;
                        color: #111111;
                    ">
                        {heading}
                    </h1>

                    <p style="
                        margin: 0;
                        color: #666666;
                        font-size: 15px;
                        line-height: 1.8;
                    ">
                        {message}
                    </p>

                    {code_block}

                    <p style="
                        margin: 25px 0 0;
                        color: #888888;
                        font-size: 12px;
                        line-height: 1.7;
                    ">
                        {footer}
                    </p>

                </div>

                <!-- FOOTER -->

                <div style="
                    padding: 27px 30px;
                    background: #faf9f7;
                    border-top: 1px solid #eeeeee;
                    text-align: center;
                ">

                    <p style="
                        margin: 0;
                        color: #999999;
                        font-size: 11px;
                        line-height: 1.7;
                    ">
                        © ORENTEMIST
                        <br>
                        Crafted for those who leave an impression.
                    </p>

                </div>

            </div>

        </div>

    </body>
    </html>
    """

    code_text = (
        f"Your security code: {code}\n\n"
        if code
        else ""
    )

    plain_text = (
        "ORENTEMIST\n\n"
        f"{heading}\n\n"
        f"{message}\n\n"
        f"{code_text}"
        f"{expiry_text}\n\n"
        f"{footer}\n\n"
        "ORENTEMIST Customer Support"
    )

    resend.api_key = settings.RESEND_API_KEY

    resend.Emails.send(
        {
            "from": "ORENTEMIST <onboarding@resend.dev>",
            "to": [to_email],
            "subject": subject,
            "html": html,
            "text": plain_text,
        }
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

            send_orentemist_email(
                to_email=user.email,
                subject="Welcome to ORENTEMIST — Verify your email",
                heading="Welcome to ORENTEMIST.",
                message=(
                    f"Hello {user.first_name or user.username}, "
                    "thank you for creating your account. "
                    "Use the security code below to verify "
                    "your email and complete your registration."
                ),
                code=code,
                footer_message=(
                    "If you did not create this account, "
                    "you can safely ignore this email."
                ),
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

            send_orentemist_email(
                to_email=user.email,
                subject="Your new ORENTEMIST verification code",
                heading="Your new verification code.",
                message=(
                    f"Hello {user.first_name or user.username}, "
                    "you requested a new verification code "
                    "for your ORENTEMIST account."
                ),
                code=code,
                footer_message=(
                    "If you did not request a new verification "
                    "code, you can safely ignore this email."
                ),
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

            send_orentemist_email(
                to_email=user.email,
                subject="ORENTEMIST — Reset your password",
                heading="Reset your password.",
                message=(
                    f"Hello {user.first_name or user.username}, "
                    "we received a request to reset the password "
                    "for your ORENTEMIST account. "
                    "Use the security code below to continue."
                ),
                code=code,
                footer_message=(
                    "If you did not request a password reset, "
                    "you can safely ignore this email. "
                    "Your password will remain unchanged."
                ),
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
                    ),
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


# =========================================================
# LOGOUT
# =========================================================

class LogoutView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        profile, _ = (
            CustomerProfile.objects.get_or_create(
                user=request.user
            )
        )

        # Immediately invalidate all existing access tokens.
        profile.session_version += 1

        profile.save(
            update_fields=["session_version"]
        )

        # Blacklist every outstanding refresh token
        # belonging to this user.
        outstanding_tokens = (
            OutstandingToken.objects.filter(
                user=request.user
            )
        )

        for token in outstanding_tokens:

            BlacklistedToken.objects.get_or_create(
                token=token
            )

        return Response(
            {
                "message":
                    "Logged out successfully."
            },
            status=status.HTTP_200_OK,
        )