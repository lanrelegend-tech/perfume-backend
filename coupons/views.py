from decimal import Decimal

from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import generics
from rest_framework.permissions import IsAdminUser

from .models import Coupon
from .serializers import CouponSerializer



class ValidateCouponView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        code = request.data.get("code")
        order_amount = request.data.get("order_amount")

        if not code:
            return Response(
                {"error": "Coupon code is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if order_amount is None:
            return Response(
                {"error": "order_amount is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            order_amount = Decimal(str(order_amount))

            if order_amount < 0:
                raise ValueError

        except (ValueError, TypeError, ArithmeticError):
            return Response(
                {"error": "Invalid order amount"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            coupon = Coupon.objects.get(
                code__iexact=code.strip()
            )
        except Coupon.DoesNotExist:
            return Response(
                {"error": "Invalid coupon code"},
                status=status.HTTP_404_NOT_FOUND
            )

        if not coupon.is_active:
            return Response(
                {"error": "This coupon is inactive"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if coupon.expires_at and coupon.expires_at <= timezone.now():
            return Response(
                {"error": "This coupon has expired"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if (
            coupon.usage_limit is not None
            and coupon.used_count >= coupon.usage_limit
        ):
            return Response(
                {"error": "This coupon has reached its usage limit"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if order_amount < coupon.minimum_order_amount:
            return Response(
                {
                    "error": (
                        f"Minimum order amount is "
                        f"₦{coupon.minimum_order_amount:,.2f}"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if coupon.discount_type == "percentage":
            discount_amount = (
                order_amount * coupon.discount_value / Decimal("100")
            )

            if coupon.maximum_discount is not None:
                discount_amount = min(
                    discount_amount,
                    coupon.maximum_discount
                )

        else:
            discount_amount = coupon.discount_value

        discount_amount = min(
            discount_amount,
            order_amount
        )

        final_amount = order_amount - discount_amount

        return Response({
            "message": "Coupon applied successfully",
            "coupon": coupon.code.upper(),
            "discount_type": coupon.discount_type,
            "discount_value": str(coupon.discount_value),
            "discount_amount": str(discount_amount),
            "original_amount": str(order_amount),
            "final_amount": str(final_amount),
        })

class AdminCouponListCreateView(generics.ListCreateAPIView):
    serializer_class = CouponSerializer
    permission_classes = [IsAdminUser]
    filterset_fields = [
        "is_active",
        "discount_type",
    ]
    search_fields = [
        "code",
    ]
    ordering_fields = [
        "created_at",
        "expires_at",
        "used_count",
        "discount_value",
    ]

    def get_queryset(self):
        queryset = Coupon.objects.all().order_by("-created_at")
        coupon_status = self.request.query_params.get("status")
        now = timezone.now()

        if coupon_status == "active":
            queryset = queryset.filter(
                is_active=True,
            ).filter(
                expires_at__isnull=True
            ) | queryset.filter(
                is_active=True,
                expires_at__gt=now,
            )

        elif coupon_status == "inactive":
            queryset = queryset.filter(
                is_active=False,
            )

        elif coupon_status == "expired":
            queryset = queryset.filter(
                expires_at__lt=now,
            )

        return queryset.order_by("-created_at")


class AdminCouponDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Coupon.objects.all()
    serializer_class = CouponSerializer
    permission_classes = [IsAdminUser]    
