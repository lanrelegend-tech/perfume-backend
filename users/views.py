from datetime import timedelta
import random

from django.conf import settings
import resend
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q, Count, Sum
from django.utils import timezone

from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator

from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
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

class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            self.perform_create(serializer)

        except Exception as error:
            import traceback

            print("REGISTER ERROR:", repr(error))
            traceback.print_exc()

            return Response(
                {
                    "error": "Registration failed",
                    "detail": str(error),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        headers = self.get_success_headers(serializer.data)

        return Response(
            {
                **serializer.data,
                "verification_required": True,
                "message": "Account created. Please verify your email.",
            },
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def perform_create(self, serializer):
        user = serializer.save()

        verification, created = EmailVerificationCode.objects.get_or_create(
            user=user,
            defaults={
                "code": str(random.randint(100000, 999999)),
                "expires_at": timezone.now() + timedelta(minutes=10),
            },
        )

        if not created:
            verification.generate_code()

        try:
            resend.api_key = settings.RESEND_API_KEY

            response = resend.Emails.send({
                "from": "ORENTEMIST <onboarding@resend.dev>",
                "to": [user.email],
                "subject": "Verify your email",
                "text": (
                    f"Hello {user.first_name or user.username},\n\n"
                    "Welcome to ORENTEMIST! 🎉\n\n"
                    "Thank you for creating an account with us.\n\n"
                    "Your email verification code is:\n\n"
                    f"{verification.code}\n\n"
                    "This code will expire in 10 minutes.\n\n"
                    "Please enter this code on the verification page "
                    "to complete your account registration.\n\n"
                    "If you did not create this account, you can safely "
                    "ignore this email.\n\n"
                    "Thank you,\n"
                    "ORENTEMIST Customer Support"
                ),
            })

            print(
                "VERIFICATION EMAIL RESPONSE:",
                response
            )

        except Exception as error:
            import traceback

            print(
                "REGISTER EMAIL ERROR:",
                repr(error)
            )
            traceback.print_exc()
            raise


# =========================================================
# VERIFY EMAIL
# =========================================================

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

        email = serializer.validated_data["email"]
        code = serializer.validated_data["code"]

        try:
            user = User.objects.filter(
    email=email
).order_by("id").first()

            if not user:
              return Response(
        {
            "error": "Account not found"
        },
        status=status.HTTP_404_NOT_FOUND,
    )

        except User.DoesNotExist:
            return Response(
                {
                    "error": "Account not found"
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            verification = (
                EmailVerificationCode.objects
                .get(user=user)
            )

        except EmailVerificationCode.DoesNotExist:
            return Response(
                {
                    "error": "Verification code not found"
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if verification.verified_at:
            return Response(
                {
                    "message": "Email is already verified"
                },
                status=status.HTTP_200_OK,
            )

        if not verification.is_valid():
            return Response(
                {
                    "error": "Verification code has expired"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if verification.code != code:
            return Response(
                {
                    "error": "Invalid verification code"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        verification.verified_at = timezone.now()

        # Attach previous guest orders to the new account
        Order.objects.filter(
            user__isnull=True,
            email__iexact=user.email,
        ).update(
            user=user
        )

        verification.save(
            update_fields=["verified_at"]
        )

        return Response(
            {
                "message": "Email verified successfully"
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# RESEND VERIFICATION CODE
# =========================================================

class ResendVerificationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            serializer = ResendVerificationSerializer(
                data=request.data
            )

            serializer.is_valid(
                raise_exception=True
            )

            email = serializer.validated_data["email"]

            print(
                "RESEND VERIFICATION REQUEST FOR:",
                email
            )

            user = User.objects.filter(
             email=email
).order_by("id").first()

            if not user:
             return Response(
        {
            "error": "No account found with this email address."
        },
        status=status.HTTP_404_NOT_FOUND,
    )

            try:
                verification = (
                    EmailVerificationCode.objects
                    .get(user=user)
                )

            except EmailVerificationCode.DoesNotExist:
                verification = (
                    EmailVerificationCode.objects.create(
                        user=user,
                        code=str(
                            random.randint(
                                100000,
                                999999
                            )
                        ),
                        expires_at=(
                            timezone.now()
                            + timedelta(minutes=10)
                        ),
                    )
                )

            if verification.verified_at:
                return Response(
                    {
                        "message": "Email is already verified"
                    },
                    status=status.HTTP_200_OK,
                )

            # Generate a fresh verification code
            verification.generate_code()

            print(
                "NEW VERIFICATION CODE GENERATED FOR:",
                user.email
            )

            print(
                "VERIFICATION CODE:",
                verification.code
            )

            # Resend API
            resend.api_key = settings.RESEND_API_KEY

            response = resend.Emails.send({
                "from": "ORENTEMIST <onboarding@resend.dev>",
                "to": [user.email],
                "subject": (
                    "Your new ORENTEMIST verification code"
                ),
                "text": (
                    f"Hello {user.first_name or user.username},\n\n"
                    "Here is your new ORENTEMIST "
                    "email verification code:\n\n"
                    f"{verification.code}\n\n"
                    "This code will expire in 10 minutes.\n\n"
                    "If you did not request this code, "
                    "you can safely ignore this email.\n\n"
                    "Thank you,\n"
                    "ORENTEMIST Customer Support"
                ),
            })

            print(
                "RESEND VERIFICATION EMAIL RESPONSE:",
                response
            )

            return Response(
                {
                    "message": (
                        "A new verification code has been sent"
                    )
                },
                status=status.HTTP_200_OK,
            )

        except Exception as error:
            import traceback

            print(
                "RESEND VERIFICATION ERROR:",
                repr(error)
            )

            traceback.print_exc()

            return Response(
                {
                    "error": "Resend verification failed",
                    "detail": str(error),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =========================================================
# FORGOT PASSWORD
# =========================================================

class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        email = serializer.validated_data["email"]

        try:
            user = User.objects.get(
                email=email
            )

        except User.DoesNotExist:
            return Response(
                {
                    "message": (
                        "If an account exists with this email, "
                        "a password reset code has been sent."
                    )
                },
                status=status.HTTP_200_OK,
            )

        reset_code, created = (
            PasswordResetCode.objects.get_or_create(
                user=user
            )
        )

        reset_code.generate_code()

        try:
            send_mail(
                subject="Reset your password",
                message=(
                    f"Hello {user.first_name or user.username},\n\n"
                    "We received a request to reset your password.\n\n"
                    "Your password reset code is:\n\n"
                    f"{reset_code.code}\n\n"
                    "This code will expire in 10 minutes.\n\n"
                    "If you did not request a password reset, "
                    "you can safely ignore this email.\n\n"
                    "Thank you,\n"
                    "Customer Support"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )

        except Exception as error:
            print(
                "PASSWORD RESET EMAIL ERROR:",
                repr(error)
            )
            raise

        return Response(
            {
                "message": (
                    "If an account exists with this email, "
                    "a password reset code has been sent."
                )
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# RESET PASSWORD
# =========================================================

@method_decorator(
    ratelimit(
        key="ip",
        rate="5/m",
        method="POST",
        block=True,
    ),
    name="dispatch",
)
class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        email = serializer.validated_data["email"]
        code = serializer.validated_data["code"]
        new_password = serializer.validated_data["new_password"]

        try:
            user = User.objects.get(
                email=email
            )

        except User.DoesNotExist:
            return Response(
                {
                    "error": "Invalid password reset code"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            reset_code = (
                PasswordResetCode.objects
                .get(user=user)
            )

        except PasswordResetCode.DoesNotExist:
            return Response(
                {
                    "error": "Invalid password reset code"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not reset_code.is_valid():
            return Response(
                {
                    "error": "Password reset code has expired"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if reset_code.code != code:
            return Response(
                {
                    "error": "Invalid password reset code"
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
                    "error": error.messages
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(
            new_password
        )

        user.save(
            update_fields=["password"]
        )

        reset_code.delete()

        return Response(
            {
                "message": "Password reset successfully"
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
            partial=True,
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

class AdminCustomerListView(
    generics.ListAPIView
):
    serializer_class = AdminCustomerSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        queryset = (
            User.objects
            .filter(
                is_staff=False
            )
            .select_related(
                "profile"
            )
            .prefetch_related(
                "orders"
            )
            .order_by(
                "-date_joined"
            )
        )

        search = self.request.query_params.get(
            "search"
        )

        if search:
            queryset = queryset.filter(
                Q(
                    username__icontains=search
                )
                | Q(
                    email__icontains=search
                )
                | Q(
                    first_name__icontains=search
                )
                | Q(
                    last_name__icontains=search
                )
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
            .filter(
                is_staff=False
            )
            .select_related(
                "profile"
            )
            .prefetch_related(
                "orders"
            )
        )


# =========================================================
# ADMIN GUEST CUSTOMERS
# =========================================================

class AdminGuestCustomerListView(
    APIView
):
    permission_classes = [IsAdminUser]

    def get(self, request):
        guests = (
            Order.objects
            .filter(
                user__isnull=True
            )
            .exclude(
                email__isnull=True
            )
            .exclude(
                email=""
            )
            .values(
                "email"
            )
            .annotate(
                order_count=Count("id"),
                total_spent=Sum(
                    "total_amount",
                    filter=Q(
                        payment_status="paid"
                    ),
                ),
            )
            .order_by(
                "-order_count"
            )
        )

        results = []

        for guest in guests:
            results.append({
                "id": (
                    f"guest-{guest['email']}"
                ),
                "email": guest["email"],
                "first_name": "",
                "last_name": "",
                "username": "",
                "phone": "",
                "address": "",
                "city": "",
                "state": "",
                "order_count": (
                    guest["order_count"]
                ),
                "total_spent": (
                    guest["total_spent"] or 0
                ),
                "is_active": True,
                "date_joined": None,
                "customer_type": "guest",
            })

        return Response({
            "count": len(results),
            "results": results,
        })