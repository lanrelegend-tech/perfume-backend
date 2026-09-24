from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Sum

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import CustomerProfile


# =========================================================
# LOGIN / JWT
# =========================================================
class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):

    username_field = "email"

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        profile, created = CustomerProfile.objects.get_or_create(
            user=user
        )

        token["session_version"] = profile.session_version

        return token

    def validate(self, attrs):
        email = attrs.get("email", "").strip().lower()
        password = attrs.get("password")

        user = User.objects.filter(
            email__iexact=email
        ).first()

        if not user:
            raise serializers.ValidationError(
                "Invalid email or password."
            )

        if not password or not user.check_password(password):
            raise serializers.ValidationError(
                "Invalid email or password."
            )

        if not user.is_active:
            raise serializers.ValidationError(
                "This account is inactive."
            )

        verification = getattr(
            user,
            "email_verification",
            None
        )

        if verification is None or not verification.verified_at:
            raise serializers.ValidationError({
                "error": "email_not_verified",
                "message": (
                    "Your email is not verified. "
                    "Please check your email for a verification link."
                ),
            })

        refresh = self.get_token(user)

        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }


# =========================================================
# REGISTER
# =========================================================

class RegisterSerializer(serializers.ModelSerializer):

    password = serializers.CharField(
        write_only=True,
        min_length=8
    )

    password2 = serializers.CharField(
        write_only=True,
        min_length=8
    )

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "password",
            "password2",
            "first_name",
            "last_name",
        ]

    def validate_username(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Username is required."
            )

        if User.objects.filter(
            username__iexact=value
        ).exists():
            raise serializers.ValidationError(
                "This username is already taken."
            )

        return value

    def validate_email(self, value):
        email = value.strip().lower()

        if User.objects.filter(
            email__iexact=email
        ).exists():
            raise serializers.ValidationError(
                "An account with this email already exists."
            )

        return email

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({
                "password2": "Passwords do not match."
            })

        try:
            validate_password(
                attrs["password"]
            )
        except ValidationError as error:
            raise serializers.ValidationError({
                "password": error.messages
            })

        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")

        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data.get(
                "first_name",
                ""
            ),
            last_name=validated_data.get(
                "last_name",
                ""
            ),
        )

        CustomerProfile.objects.get_or_create(
            user=user
        )

        return user


# =========================================================
# CURRENT USER
# =========================================================

class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User

        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
        ]

        read_only_fields = [
            "id",
            "username",
            "email",
        ]


# =========================================================
# CUSTOMER PROFILE
# =========================================================

class CustomerProfileSerializer(serializers.ModelSerializer):

    class Meta:
        model = CustomerProfile

        fields = [
            "phone",
            "address",
            "city",
            "state",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "created_at",
            "updated_at",
        ]


# =========================================================
# ADMIN CUSTOMER
# =========================================================

class AdminCustomerSerializer(serializers.ModelSerializer):

    phone = serializers.CharField(
        source="profile.phone",
        read_only=True
    )

    address = serializers.CharField(
        source="profile.address",
        read_only=True
    )

    city = serializers.CharField(
        source="profile.city",
        read_only=True
    )

    state = serializers.CharField(
        source="profile.state",
        read_only=True
    )

    order_count = serializers.SerializerMethodField()
    total_spent = serializers.SerializerMethodField()
    order_history = serializers.SerializerMethodField()

    class Meta:
        model = User

        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "phone",
            "address",
            "city",
            "state",
            "order_count",
            "total_spent",
            "date_joined",
            "is_active",
            "order_history",
        ]

        read_only_fields = [
            "id",
            "username",
            "email",
            "phone",
            "address",
            "city",
            "state",
            "order_count",
            "total_spent",
            "date_joined",
            "order_history",
        ]

    def get_order_history(self, obj):
        orders = obj.orders.all().order_by(
            "-created_at"
        )

        return [
            {
                "id": order.id,
                "order_number": order.order_number,
                "total_amount": str(
                    order.total_amount
                ),
                "delivery_fee": str(
                    order.delivery_fee
                ),
                "discount_amount": str(
                    order.discount_amount
                ),
                "status": order.status,
                "payment_status": order.payment_status,
                "payment_reference": order.payment_reference,
                "courier": order.courier,
                "tracking_number": order.tracking_number,
                "created_at": order.created_at,
                "updated_at": order.updated_at,
            }
            for order in orders
        ]

    def get_order_count(self, obj):
        return obj.orders.count()

    def get_total_spent(self, obj):
        total = obj.orders.filter(
            payment_status="paid"
        ).aggregate(
            total=Sum("total_amount")
        )["total"]

        return str(total or 0)


# =========================================================
# EMAIL VERIFICATION
# =========================================================

class VerifyEmailSerializer(serializers.Serializer):

    email = serializers.EmailField()

    code = serializers.RegexField(
        regex=r"^\d{6}$",
        error_messages={
            "invalid": (
                "Enter a valid 6-digit verification code."
            )
        },
    )

    def validate_email(self, value):
        return value.strip().lower()

    def validate_code(self, value):
        return value.strip()


# =========================================================
# RESEND VERIFICATION
# =========================================================

class ResendVerificationSerializer(serializers.Serializer):

    email = serializers.EmailField()

    def validate_email(self, value):
        return value.strip().lower()


# =========================================================
# FORGOT PASSWORD
# =========================================================

class ForgotPasswordSerializer(serializers.Serializer):

    email = serializers.EmailField()

    def validate_email(self, value):
        return value.strip().lower()


# =========================================================
# RESET PASSWORD
# =========================================================

class ResetPasswordSerializer(serializers.Serializer):

    email = serializers.EmailField()

    code = serializers.RegexField(
        regex=r"^\d{6}$",
        error_messages={
            "invalid": (
                "Enter a valid 6-digit password reset code."
            )
        },
    )

    new_password = serializers.CharField(
        write_only=True,
        min_length=8
    )

    confirm_password = serializers.CharField(
        write_only=True,
        min_length=8
    )

    def validate_email(self, value):
        return value.strip().lower()

    def validate_code(self, value):
        return value.strip()

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({
                "confirm_password": (
                    "Passwords do not match."
                )
            })

        try:
            validate_password(
                attrs["new_password"]
            )
        except ValidationError as error:
            raise serializers.ValidationError({
                "new_password": error.messages
            })

        return attrs