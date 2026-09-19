from django.contrib.auth.models import User
from rest_framework import serializers
from .models import CustomerProfile



class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        min_length=8
    )

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "password",
            "first_name",
            "last_name",
        ]

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
        )

        return user


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

from django.db.models import Sum


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
            "phone",
            "address",
            "city",
            "state",
            "order_count",
            "total_spent",
            "date_joined",
        ]
    def get_order_history(self, obj):
        orders = obj.orders.all().order_by("-created_at")

        return [
        {
            "id": order.id,
            "order_number": order.order_number,
            "total_amount": str(order.total_amount),
            "delivery_fee": str(order.delivery_fee),
            "discount_amount": str(order.discount_amount),
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
class VerifyEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(
        min_length=6,
        max_length=6
    )    
class ResendVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()    
class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()   
class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    code = serializers.CharField(
        min_length=6,
        max_length=6
    )

    new_password = serializers.CharField(
        write_only=True,
        min_length=8
    )

    confirm_password = serializers.CharField(
        write_only=True,
        min_length=8
    )

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {
                    "confirm_password": (
                        "Passwords do not match."
                    )
                }
            )

        return attrs     