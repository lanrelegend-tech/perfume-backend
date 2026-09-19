from decimal import Decimal

from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Coupon


class ValidateCouponView(APIView):
    permission_classes = [IsAuthenticated]

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