from datetime import timedelta
import secrets
import resend

from django.conf import settings
from django.contrib.auth.hashers import check_password,make_password
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
    Sends premium branded ORENTEMIST emails through Resend.
    """

    code_block = ""

    if code:
        code_block = f"""
        <div style="
            margin: 32px 0;
            padding: 30px 20px;
            background: #f7f5f1;
            border: 1px solid #e4e0d8;
            border-radius: 18px;
            text-align: center;
        ">

            <p style="
                margin: 0 0 12px;
                color: #8b877f;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 3px;
                text-transform: uppercase;
            ">
                Your Verification Code
            </p>

            <div style="
                font-size: 38px;
                font-weight: 700;
                letter-spacing: 9px;
                color: #111111;
                line-height: 1.2;
            ">
                {code}
            </div>

            <p style="
                margin: 14px 0 0;
                color: #8b877f;
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
        background: #f2f1ee;
        font-family: Arial, Helvetica, sans-serif;
        color: #111111;
    ">

        <div style="
            width: 100%;
            padding: 45px 15px;
            box-sizing: border-box;
        ">

            <div style="
                max-width: 580px;
                margin: 0 auto;
                background: #ffffff;
                border: 1px solid #e5e2dc;
                border-radius: 24px;
                overflow: hidden;
            ">

                <!-- =================================================
                     HEADER
                ================================================== -->

                <div style="
                    padding: 38px 30px 32px;
                    text-align: center;
                    border-bottom: 1px solid #eeeeee;
                ">

                    <div style="
                        font-size: 23px;
                        font-weight: 700;
                        letter-spacing: 6px;
                        color: #000000;
                    ">
                        ORENTEMIST
                    </div>

                    <div style="
                        margin-top: 10px;
                        color: #9a968f;
                        font-size: 9px;
                        font-weight: 600;
                        letter-spacing: 3px;
                        text-transform: uppercase;
                    ">
                        The Art of Fragrance
                    </div>

                </div>


                <!-- =================================================
                     MAIN CONTENT
                ================================================== -->

                <div style="
                    padding: 44px 35px 40px;
                ">

                    <p style="
                        margin: 0 0 12px;
                        color: #9a968f;
                        font-size: 10px;
                        font-weight: 700;
                        letter-spacing: 3px;
                        text-transform: uppercase;
                    ">
                        ORENTEMIST
                    </p>

                    <h1 style="
                        margin: 0 0 20px;
                        font-size: 30px;
                        line-height: 1.3;
                        font-weight: 600;
                        letter-spacing: -0.5px;
                        color: #111111;
                    ">
                        {heading}
                    </h1>

                    <p style="
                        margin: 0;
                        color: #626262;
                        font-size: 15px;
                        line-height: 1.85;
                    ">
                        {message}
                    </p>

                    {code_block}

                    <p style="
                        margin: 25px 0 0;
                        color: #858585;
                        font-size: 12px;
                        line-height: 1.8;
                    ">
                        {footer}
                    </p>

                </div>


                <!-- =================================================
                     BRAND FOOTER
                ================================================== -->

                <div style="
                    padding: 32px 25px;
                    background: #faf9f6;
                    border-top: 1px solid #eeeeee;
                    text-align: center;
                ">

                    <p style="
                        margin: 0 0 15px;
                        color: #111111;
                        font-size: 13px;
                        font-weight: 700;
                        letter-spacing: 2px;
                    ">
                        ORENTEMIST
                    </p>

                    <p style="
                        margin: 0 0 18px;
                        color: #777777;
                        font-size: 11px;
                        line-height: 1.8;
                    ">
                        The Art of Fragrance
                        <br>
                        Crafted for those who leave an impression.
                    </p>

                    <p style="
                        margin: 0 0 8px;
                        color: #555555;
                        font-size: 11px;
                        line-height: 1.8;
                    ">
                        <strong>Visit Us</strong>
                        <br>
                        22 Oyun, Ilorin, Kwara State, Nigeria
                    </p>

                    <p style="
                        margin: 0 0 8px;
                        color: #555555;
                        font-size: 11px;
                        line-height: 1.8;
                    ">
                        <strong>Call / WhatsApp</strong>
                        <br>
                        09153242202
                    </p>

                    <p style="
                        margin: 0 0 18px;
                        color: #555555;
                        font-size: 11px;
                        line-height: 1.8;
                    ">
                        <strong>Email</strong>
                        <br>
                        lanrelegend@gmail.com
                    </p>


                    <!-- SOCIAL MEDIA -->

                    <p style="
                        margin: 18px 0 0;
                        color: #999999;
                        font-size: 10px;
                        letter-spacing: 1px;
                    ">
                        FOLLOW ORENTEMIST
                    </p>

                    <p style="
                        margin: 9px 0 0;
                        font-size: 11px;
                    ">
                        <a
                            href="https://instagram.com/lanre_legend"
                            style="
                                color: #111111;
                                text-decoration: none;
                                font-weight: 600;
                            "
                        >
                            Instagram @lanre_legend
                        </a>
                    </p>

                    <p style="
                        margin: 7px 0 0;
                        font-size: 11px;
                    ">
                        <a
                            href="https://tiktok.com/@lanre_legend"
                            style="
                                color: #111111;
                                text-decoration: none;
                                font-weight: 600;
                            "
                        >
                            TikTok @lanre_legend
                        </a>
                    </p>

                    <p style="
                        margin: 7px 0 0;
                        font-size: 11px;
                    ">
                        <a
                            href="https://orentemist.online"
                            style="
                                color: #111111;
                                text-decoration: none;
                                font-weight: 600;
                            "
                        >
                            orentemist.online
                        </a>
                    </p>


                    <div style="
                        margin: 25px auto 0;
                        width: 45px;
                        height: 1px;
                        background: #d8d5cf;
                    "></div>

                    <p style="
                        margin: 18px 0 0;
                        color: #aaa7a0;
                        font-size: 10px;
                        line-height: 1.7;
                    ">
                        © ORENTEMIST
                        <br>
                        All rights reserved.
                    </p>

                </div>

            </div>

        </div>

    </body>

    </html>
    """

    code_text = (
        f"Your verification code: {code}\n\n"
        if code
        else ""
    )

    plain_text = (
        "ORENTEMIST — The Art of Fragrance\n\n"
        f"{heading}\n\n"
        f"{message}\n\n"
        f"{code_text}"
        f"{expiry_text}\n\n"
        f"{footer}\n\n"
        "ORENTEMIST\n"
        "22 Oyun, Ilorin, Kwara State, Nigeria\n"
        "Phone: 09153242202\n"
        "Email: lanrelegend@gmail.com\n"
        "Instagram: @lanre_legend\n"
        "TikTok: @lanre_legend\n"
        "Website: https://orentemist.online\n"
    )

    resend.api_key = settings.RESEND_API_KEY

    resend.Emails.send(
        {
           "from": "ORENTEMIST <hello@orentemist.online>",
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
                user=user,
                defaults={
                    "expires_at": (
                        timezone.now()
                        + timedelta(minutes=10)
                    ),
                },
            )
        )

        # Give every new verification code
        # a fresh 10-minute expiration time.
        verification.expires_at = (
            timezone.now()
            + timedelta(minutes=10)
        )

        code = verification.generate_code()

        try:

            send_orentemist_email(
                to_email=user.email,
                subject="Welcome to ORENTEMIST — Verify your email",
                heading="Welcome to ORENTEMIST.",
                message=(
                    f"Hello {user.first_name or user.username}, "
                    "welcome to ORENTEMIST. "
                    "We are delighted to have you with us. "
                    "Your signature scent journey begins here. "
                    "Use the security code below to verify your email "
                    "and step into the world of ORENTEMIST."
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







def send_verification_link_email(user):

    verification, created = (
        EmailVerificationCode.objects.get_or_create(
            user=user,
            defaults={
                "code": make_password("unused"),
                "expires_at": (
                    timezone.now()
                    + timedelta(minutes=10)
                ),
            },
        )
    )

    raw_token = secrets.token_urlsafe(48)

    verification.verification_token = (
        make_password(raw_token)
    )

    verification.verification_token_expires_at = (
        timezone.now()
        + timedelta(minutes=15)
    )

    verification.save(
        update_fields=[
            "verification_token",
            "verification_token_expires_at",
        ]
    )

    frontend_url = getattr(
        settings,
        "FRONTEND_URL",
        "https://perfume-frontend-new-ashy.vercel.app",
    ).rstrip("/")

    verification_url = (
        f"{frontend_url}/account-verification"
        f"?token={raw_token}"
    )

    resend.api_key = settings.RESEND_API_KEY

    resend.Emails.send(
        {
            "from":
                "ORENTEMIST <hello@orentemist.online>",

            "to":
                [user.email],

            "subject":
                "ORENTEMIST — Verify your email",

            "html":
                f"""
                <div style="
                    font-family: Arial, sans-serif;
                    background:#f7f7f5;
                    padding:40px 20px;
                ">

                    <div style="
                        max-width:600px;
                        margin:auto;
                        background:#ffffff;
                        padding:45px 35px;
                        text-align:center;
                    ">

                        <div style="
                            font-size:22px;
                            font-weight:600;
                            letter-spacing:4px;
                            margin-bottom:10px;
                        ">
                            ORENTEMIST
                        </div>

                        <div style="
                            font-size:11px;
                            letter-spacing:3px;
                            color:#999;
                            text-transform:uppercase;
                            margin-bottom:40px;
                        ">
                            The Art of Fragrance
                        </div>

                        <h1 style="
                            font-size:28px;
                            font-weight:400;
                            margin-bottom:20px;
                            color:#111;
                        ">
                            Verify your email
                        </h1>

                        <p style="
                            color:#555;
                            font-size:15px;
                            line-height:1.7;
                            margin-bottom:30px;
                        ">
                            Hello {user.first_name or user.username},
                            <br><br>
                            We noticed that you tried to sign in
                            before verifying your email address.
                            Please verify your email using the button
                            below to continue to your ORENTEMIST account.
                        </p>

                       <table
    role="presentation"
    border="0"
    cellpadding="0"
    cellspacing="0"
    width="100%"
    style="margin:0 auto;"
>
    <tr>
        <td
            align="center"
            style="padding:0;"
        >
            <a
                href="{verification_url}"
                target="_blank"
                rel="noopener noreferrer"
                style="
                    display:inline-block;
                    background-color:#000000;
                    color:#ffffff;
                    text-decoration:none;
                    padding:16px 32px;
                    font-family:Arial,Helvetica,sans-serif;
                    font-size:13px;
                    font-weight:600;
                    letter-spacing:1px;
                    line-height:20px;
                    border-radius:6px;
                    text-align:center;
                "
            >
                VERIFY MY EMAIL
            </a>
        </td>
    </tr>
</table>

                        <p style="
                            color:#999;
                            font-size:12px;
                            line-height:1.6;
                            margin-top:30px;
                        ">
                            This verification link expires in
                            15 minutes and can only be used once.
                        </p>

                        <div style="
                            margin-top:45px;
                            padding-top:25px;
                            border-top:1px solid #eee;
                            color:#999;
                            font-size:11px;
                            line-height:1.8;
                        ">
                            <strong style="color:#111;">
                                ORENTEMIST
                            </strong>
                            <br>
                            The Art of Fragrance
                            <br>
                            Crafted for those who leave an impression.
                            <br><br>
                            22 Oyun, Ilorin, Kwara State, Nigeria
                            <br>
                            09153242202
                            <br>
                            lanrelegend@gmail.com
                            <br><br>
                            Instagram:
                            @lanre_legend
                            <br>
                            TikTok:
                            @lanre_legend
                            <br><br>
                            <a
                                href="https://orentemist.online"
                                style="color:#111;"
                            >
                                orentemist.online
                            </a>
                        </div>

                    </div>

                </div>
                """,
        }
    )


# =========================================================
# VERIFY EMAIL BY SECURE LINK
# =========================================================

class VerifyEmailLinkView(APIView):

    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):

        token = (
            request.data.get("token", "")
            .strip()
        )

        if not token:
            return Response(
                {
                    "error":
                        "Invalid verification link."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        verification = (
            EmailVerificationCode.objects
            .select_related("user")
            .filter(
                verification_token__isnull=False,
                verification_token_expires_at__isnull=False,
            )
            .order_by("id")
        )

        matched_verification = None

        for item in verification:

            if not item.verification_token:
                continue

            if check_password(
                token,
                item.verification_token
            ):
                matched_verification = item
                break

        if matched_verification is None:
            return Response(
                {
                    "error":
                        "Invalid or expired verification link."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        verification = matched_verification
        user = verification.user

        if verification.verified_at:
            return Response(
                {
                    "message":
                        "Email is already verified."
                },
                status=status.HTTP_200_OK,
            )

        if (
            not verification.verification_token_expires_at
            or timezone.now()
            >= verification.verification_token_expires_at
        ):
            return Response(
                {
                    "error":
                        "This verification link has expired. "
                        "Please request a new one."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        verification.verified_at = timezone.now()

        verification.verification_token = None

        verification.verification_token_expires_at = None

        verification.save(
            update_fields=[
                "verified_at",
                "verification_token",
                "verification_token_expires_at",
            ]
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
                    "Email verified successfully."
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
                    "a verification email has been sent."
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

        verification = (
            EmailVerificationCode.objects
            .filter(user=user)
            .first()
        )

        if verification and verification.verified_at:
            return generic_response

        try:

            send_verification_link_email(user)

        except Exception as error:
            print("VERIFICATION LINK EMAIL ERROR:", error)
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
                user=user,
                defaults={
                    "expires_at": (
                        timezone.now()
                        + timedelta(minutes=10)
                    ),
                },
            )
        )

        reset_code.expires_at = (
            timezone.now()
            + timedelta(minutes=10)
        )

        code = reset_code.generate_code()
        print("GENERATED RESET CODE:", code)
        print(
           "GENERATED CODE MATCH:",
           check_password(code, reset_code.code)
)

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
        print("RESET DEBUG")

        print("EMAIL:", email)

        print("SUBMITTED CODE:", submitted_code)

        print("STORED HASH:", reset_code.code)

        print("EXPIRES:", reset_code.expires_at)

        print("NOW:", timezone.now())

        print(

    "CODE MATCH:",

           check_password(

        submitted_code,

        reset_code.code

    )

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
    def post(self, request, *args, **kwargs):

        user = self.get_object()

        message = (
            request.data.get("message", "")
            .strip()
        )

        if not message:
            return Response(
                {
                    "error": "Message is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user.email:
            return Response(
                {
                    "error":
                        "This customer does not have an email address."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        customer_name = (
            f"{user.first_name} {user.last_name}"
            .strip()
        )

        if not customer_name:
            customer_name = (
                user.username
                or user.email
                or "Customer"
            )

        try:

            send_orentemist_email(
                to_email=user.email,
                subject="Message from ORENTEMIST",
                heading="A message from ORENTEMIST.",
                message=(
                    f"Hello {customer_name},\n\n"
                    f"{message}"
                ),
                footer_message=(
                    "If you have any questions, "
                    "please reply to this email or "
                    "contact ORENTEMIST Customer Support."
                ),
            )

        except Exception as error:

            print(
                "CUSTOMER MESSAGE EMAIL ERROR:",
                error
            )

            return Response(
                {
                    "error":
                        "Unable to send the message. "
                        "Please try again later."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "message":
                    "Customer message sent successfully."
            },
            status=status.HTTP_200_OK,
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