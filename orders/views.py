from decimal import Decimal
from django.conf import settings
from django.http import HttpResponse
import hashlib
import hmac
import uuid
import requests
from cart.models import Cart
from products.models import ProductVariant, Product
from django.utils import timezone

from django.db import transaction
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


from .models import (
    Order,
    OrderItem,
    Refund,
    OrderStatusHistory,
)
from .serializers import (
    OrderSerializer,
    AdminOrderSerializer,
    RefundSerializer,
)
from coupons.models import Coupon
from .email import send_order_confirmation_email
from shipping.models import ShippingRate

from .dashboard import get_dashboard_stats
from rest_framework import generics, status


class AdminDashboardView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response(
            get_dashboard_stats()
        )

class AdminOrderListView(generics.ListAPIView):
    serializer_class = AdminOrderSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        return (
            Order.objects
            .all()
            .select_related(
                "user",
                "coupon",
            )
            .prefetch_related(
                "items",
                "status_history",
            )
            .order_by("-created_at")
        )
class AdminOrderDetailView(
    generics.RetrieveUpdateAPIView
):
    serializer_class = AdminOrderSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        return (
            Order.objects
            .all()
            .prefetch_related(
                "items",
                "status_history",
                "refunds",
            )
            .select_related(
                "user",
                "coupon",
            )
        )

    @transaction.atomic
    def perform_update(self, serializer):

        order = (
            Order.objects
            .select_for_update()
            .prefetch_related("items")
            .select_related("user", "coupon")
            .get(pk=self.get_object().pk)
        )

        old_status = order.status
        old_payment_status = order.payment_status

        new_status = serializer.validated_data.get(
            "status",
            old_status,
        )

        new_payment_status = serializer.validated_data.get(
            "payment_status",
            old_payment_status,
        )

        # -------------------------------------------------
        # PAYMENT STATUS CAN NEVER BE CHANGED BY ADMIN PATCH
        # -------------------------------------------------

        if new_payment_status != old_payment_status:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({
                "payment_status": (
                    "Payment status cannot be changed manually. "
                    "Payments and refunds must be processed "
                    "through the payment endpoints."
                )
            })

        # -------------------------------------------------
        # ALLOWED STATUS TRANSITIONS
        # -------------------------------------------------

        allowed_transitions = {
            "pending": [
                "confirmed",
                "cancelled",
            ],
            "confirmed": [
                "processing",
                "cancelled",
            ],
            "processing": [
                "shipped",
                "delivered",
                "cancelled",
            ],
            "shipped": [
                "delivered",
                "cancelled",
            ],
            "delivered": [
                "cancelled",
            ],
            "cancelled": [],
        }

        allowed_statuses = allowed_transitions.get(
            old_status,
            [],
        )

        if (
            new_status != old_status
            and new_status not in allowed_statuses
        ):
            from rest_framework.exceptions import ValidationError

            raise ValidationError({
                "status": (
                    f"Cannot change order status "
                    f"from '{old_status}' "
                    f"to '{new_status}'. "
                    f"Allowed next statuses: "
                    f"{', '.join(allowed_statuses) or 'none'}."
                )
            })

        # -------------------------------------------------
        # NEVER MOVE UNPAID ORDERS INTO FULFILMENT
        # -------------------------------------------------

        fulfilment_statuses = {
            "confirmed",
            "processing",
            "shipped",
            "delivered",
        }

        if (
            new_status in fulfilment_statuses
            and order.payment_status != "paid"
        ):
            from rest_framework.exceptions import ValidationError

            raise ValidationError({
                "status": (
                    "An order cannot be moved into "
                    "fulfilment before payment is confirmed."
                )
            })

        # -------------------------------------------------
        # CANCEL ORDER
        # -------------------------------------------------

        if (
            old_status != "cancelled"
            and new_status == "cancelled"
        ):

            refund = None

            # -------------------------------------------------
            # PAID ORDER -> REFUND THROUGH PAYSTACK
            # -------------------------------------------------

            if order.payment_status == "paid":

                from rest_framework.exceptions import ValidationError

                if not order.payment_reference:
                    raise ValidationError({
                        "status": (
                            "This paid order cannot be cancelled "
                            "because it has no payment reference."
                        )
                    })

                if not settings.PAYSTACK_SECRET_KEY:
                    raise ValidationError({
                        "status": (
                            "Paystack secret key is not configured."
                        )
                    })

                existing_refund = (
                    Refund.objects
                    .filter(
                        order=order,
                        status__in=[
                            "pending",
                            "processed",
                        ],
                    )
                    .first()
                )

                if existing_refund:
                    raise ValidationError({
                        "status": (
                            "A refund for this order already "
                            "exists or is being processed."
                        )
                    })

                reason = (
                    self.request.data.get(
                        "reason",
                        "Order cancelled by admin",
                    )
                    or "Order cancelled by admin"
                ).strip()

                if len(reason) > 500:
                    raise ValidationError({
                        "reason": (
                            "Refund reason cannot exceed "
                            "500 characters."
                        )
                    })

                refund = Refund.objects.create(
                    order=order,
                    amount=order.total_amount,
                    reason=reason,
                    processed_by=self.request.user,
                    status="pending",
                )

                payload = {
                    "transaction": order.payment_reference,
                    "amount": int(
                        order.total_amount * 100
                    ),
                }

                try:
                    response = requests.post(
                        "https://api.paystack.co/refund",
                        headers={
                            "Authorization": (
                                f"Bearer "
                                f"{settings.PAYSTACK_SECRET_KEY}"
                            ),
                            "Content-Type": "application/json",
                        },
                        json=payload,
                        timeout=30,
                    )

                    data = response.json()

                except requests.RequestException as exc:

                    refund.status = "failed"

                    refund.save(
                        update_fields=[
                            "status",
                            "updated_at",
                        ]
                    )

                    raise ValidationError({
                        "status": (
                            "Could not connect to Paystack. "
                            "The order was not cancelled."
                        )
                    }) from exc

                if (
                    not response.ok
                    or not data.get("status")
                ):

                    refund.status = "failed"

                    refund.save(
                        update_fields=[
                            "status",
                            "updated_at",
                        ]
                    )

                    raise ValidationError({
                        "status": (
                            data.get(
                                "message",
                                "Refund request failed. "
                                "The order was not cancelled.",
                            )
                        )
                    })

                refund_data = data.get(
                    "data",
                    {},
                )

                refund.status = "processed"

                refund.paystack_reference = (
                    refund_data.get(
                        "transaction_reference"
                    )
                    or refund_data.get(
                        "reference"
                    )
                    or order.payment_reference
                )

                refund.save(
                    update_fields=[
                        "status",
                        "paystack_reference",
                        "updated_at",
                    ]
                )

                # -------------------------------------------------
                # RESTORE INVENTORY
                # -------------------------------------------------

                _restore_order_inventory_and_coupon(order)

                order.payment_status = "refunded"

            # -------------------------------------------------
            # CANCEL ORDER
            # -------------------------------------------------

            order.status = "cancelled"

            order.save(
                update_fields=[
                    "status",
                    "payment_status",
                    "updated_at",
                ]
            )

            OrderStatusHistory.objects.create(
                order=order,
                status="cancelled",
                changed_by=self.request.user,
                note=(
                    "Order cancelled by admin"
                    + (
                        " and payment refunded"
                        if order.payment_status == "refunded"
                        else ""
                    )
                ),
            )

            if refund:

                def send_refund_email_after_commit():
                    try:
                        from .email import (
                            send_order_refund_email
                        )

                        send_order_refund_email(
                            order,
                            refund,
                        )

                    except Exception as exc:
                        print(
                            "REFUND EMAIL ERROR:",
                            repr(exc),
                        )

                transaction.on_commit(
                    send_refund_email_after_commit
                )

            return

        # -------------------------------------------------
        # NORMAL STATUS UPDATE
        # -------------------------------------------------

        for field, value in serializer.validated_data.items():

            if field == "payment_status":
                continue

            setattr(order, field, value)

        order.payment_status = old_payment_status

        order.save()

        new_status = order.status

        if old_status != new_status:

            OrderStatusHistory.objects.create(
                order=order,
                status=new_status,
                changed_by=self.request.user,
            )

        # -------------------------------------------------
        # SHIPPED EMAIL
        # -------------------------------------------------

        if (
            old_status != "shipped"
            and new_status == "shipped"
        ):

            from .email import (
                send_order_shipped_email
            )

            transaction.on_commit(
                lambda: _safe_send_email(
                    send_order_shipped_email,
                    order,
                )
            )

        # -------------------------------------------------
        # DELIVERED EMAIL
        # -------------------------------------------------

        elif (
            old_status != "delivered"
            and new_status == "delivered"
        ):

            from .email import (
                send_order_delivered_email
            )

            transaction.on_commit(
                lambda: _safe_send_email(
                    send_order_delivered_email,
                    order,
                )
            )


# =========================================================
# PAYMENT HELPERS
# =========================================================

def _safe_send_email(email_function, *args):

    try:
        email_function(*args)

    except Exception as exc:
        print(
            "EMAIL ERROR:",
            repr(exc),
        )


def _get_payment_metadata(payment):

    metadata = payment.get(
        "metadata",
        {}
    )

    if not isinstance(metadata, dict):
        return {}

    return metadata


def _payment_metadata_matches_order(
    order,
    payment,
):

    metadata = _get_payment_metadata(payment)

    metadata_order_id = metadata.get(
        "order_id"
    )

    metadata_order_number = metadata.get(
        "order_number"
    )

    metadata_checkout_token = metadata.get(
        "checkout_token"
    )

    if (
        metadata_order_id is not None
        and str(metadata_order_id) != str(order.id)
    ):
        return False

    if (
        metadata_order_number is not None
        and str(metadata_order_number)
        != str(order.order_number)
    ):
        return False

    if (
        metadata_checkout_token is not None
        and str(metadata_checkout_token)
        != str(order.checkout_token)
    ):
        return False

    return True


def _restore_order_inventory_and_coupon(order):

    """
    Restore stock and coupon usage exactly once
    when an already-paid order is refunded/cancelled.
    """

    # -------------------------------------------------
    # RESTORE INVENTORY
    # -------------------------------------------------

    requirements = {}

    for item in order.items.all():

        if item.variant_id:

            key = (
                "variant",
                item.variant_id,
            )

        elif item.product_id:

            key = (
                "product",
                item.product_id,
            )

        else:
            continue

        requirements[key] = (
            requirements.get(key, 0)
            + item.quantity
        )

    for key, quantity in requirements.items():

        item_type, item_id = key

        if item_type == "variant":

            variant = (
                ProductVariant.objects
                .select_for_update()
                .get(pk=item_id)
            )

            variant.stock_quantity += quantity

            variant.in_stock = (
                variant.stock_quantity > 0
            )

            variant.save(
                update_fields=[
                    "stock_quantity",
                    "in_stock",
                ]
            )

        else:

            product = (
                Product.objects
                .select_for_update()
                .get(pk=item_id)
            )

            product.stock_quantity += quantity

            product.in_stock = (
                product.stock_quantity > 0
            )

            product.save(
                update_fields=[
                    "stock_quantity",
                    "in_stock",
                ]
            )

    # -------------------------------------------------
    # RESTORE COUPON
    # -------------------------------------------------

    if order.coupon_id:

        coupon = (
            Coupon.objects
            .select_for_update()
            .get(
                pk=order.coupon_id
            )
        )

        if coupon.used_count > 0:

            coupon.used_count -= 1

            coupon.save(
                update_fields=[
                    "used_count"
                ]
            )

        if order.user:
            coupon.used_by.remove(
                order.user
            )


def _finalize_successful_payment(
    order,
    payment,
):

    """
    Finalize a verified Paystack payment.

    Must be called inside an atomic transaction
    with the order already locked.
    """

    # -------------------------------------------------
    # IDEMPOTENCY
    # -------------------------------------------------

    if order.payment_status == "paid":

        return False

    if order.payment_status == "refunded":

        from rest_framework.exceptions import ValidationError

        raise ValidationError(
            "This order has already been refunded."
        )

    if order.status == "cancelled":

        from rest_framework.exceptions import ValidationError

        raise ValidationError(
            "Cancelled orders cannot be paid."
        )

    # -------------------------------------------------
    # PAYMENT REFERENCE
    # -------------------------------------------------

    reference = payment.get(
        "reference"
    )

    if not reference:

        from rest_framework.exceptions import ValidationError

        raise ValidationError(
            "Paystack payment reference is missing."
        )

    # -------------------------------------------------
    # VERIFY PAYMENT METADATA
    # -------------------------------------------------

    if not _payment_metadata_matches_order(
        order,
        payment,
    ):

        from rest_framework.exceptions import ValidationError

        raise ValidationError(
            "Payment metadata does not match the order."
        )

    # -------------------------------------------------
    # VERIFY AMOUNT
    # -------------------------------------------------

    expected_amount = int(
        order.total_amount * 100
    )

    if payment.get("amount") != expected_amount:

        from rest_framework.exceptions import ValidationError

        raise ValidationError(
            "Payment amount does not match the order amount."
        )

    # -------------------------------------------------
    # VERIFY CURRENCY
    # -------------------------------------------------

    if payment.get("currency") != "NGN":

        from rest_framework.exceptions import ValidationError

        raise ValidationError(
            "Payment currency does not match the order currency."
        )

    # -------------------------------------------------
    # AGGREGATE STOCK REQUIREMENTS
    #
    # This prevents an order containing the same
    # variant multiple times from overselling stock.
    # -------------------------------------------------

    variant_requirements = {}
    product_requirements = {}

    for item in order.items.all():

        if item.variant_id:

            variant_requirements[item.variant_id] = (
                variant_requirements.get(
                    item.variant_id,
                    0,
                )
                + item.quantity
            )

        elif item.product_id:

            product_requirements[item.product_id] = (
                product_requirements.get(
                    item.product_id,
                    0,
                )
                + item.quantity
            )

    locked_variants = {}
    locked_products = {}

    # -------------------------------------------------
    # LOCK + CHECK VARIANTS
    # -------------------------------------------------

    for variant_id, quantity in variant_requirements.items():

        variant = (
            ProductVariant.objects
            .select_for_update()
            .get(pk=variant_id)
        )

        if (
            not variant.in_stock
            or variant.stock_quantity < quantity
        ):

            from rest_framework.exceptions import ValidationError

            raise ValidationError(
                f"Not enough stock for variant {variant_id}."
            )

        locked_variants[variant_id] = variant

    # -------------------------------------------------
    # LOCK + CHECK PRODUCTS
    # -------------------------------------------------

    for product_id, quantity in product_requirements.items():

        product = (
            Product.objects
            .select_for_update()
            .get(pk=product_id)
        )

        if (
            not product.in_stock
            or product.stock_quantity < quantity
        ):

            from rest_framework.exceptions import ValidationError

            raise ValidationError(
                f"Not enough stock for product {product_id}."
            )

        locked_products[product_id] = product

    # -------------------------------------------------
    # REDUCE VARIANT STOCK
    # -------------------------------------------------

    for variant_id, quantity in variant_requirements.items():

        variant = locked_variants[variant_id]

        variant.stock_quantity -= quantity

        variant.in_stock = (
            variant.stock_quantity > 0
        )

        variant.save(
            update_fields=[
                "stock_quantity",
                "in_stock",
            ]
        )

    # -------------------------------------------------
    # REDUCE PRODUCT STOCK
    # -------------------------------------------------

    for product_id, quantity in product_requirements.items():

        product = locked_products[product_id]

        product.stock_quantity -= quantity

        product.in_stock = (
            product.stock_quantity > 0
        )

        product.save(
            update_fields=[
                "stock_quantity",
                "in_stock",
            ]
        )

    # -------------------------------------------------
    # COUPON
    # -------------------------------------------------

    if order.coupon_id:

        coupon = (
            Coupon.objects
            .select_for_update()
            .get(
                pk=order.coupon_id
            )
        )

        if (
            coupon.usage_limit is not None
            and coupon.used_count
            >= coupon.usage_limit
        ):

            from rest_framework.exceptions import ValidationError

            raise ValidationError(
                "This coupon has reached its usage limit."
            )

        coupon.used_count += 1

        coupon.save(
            update_fields=[
                "used_count"
            ]
        )

        if order.user:
            coupon.used_by.add(
                order.user
            )

    # -------------------------------------------------
    # MARK ORDER PAID
    # -------------------------------------------------

    old_status = order.status

    order.payment_status = "paid"
    order.status = "confirmed"
    order.payment_reference = reference

    order.save(
        update_fields=[
            "payment_status",
            "status",
            "payment_reference",
            "updated_at",
        ]
    )

    # -------------------------------------------------
    # STATUS HISTORY
    # -------------------------------------------------

    if old_status != order.status:

        OrderStatusHistory.objects.create(
            order=order,
            status=order.status,
            changed_by=None,
            note="Payment confirmed",
        )

    # -------------------------------------------------
    # CONFIRMATION EMAIL
    # -------------------------------------------------

    transaction.on_commit(
        lambda: _safe_send_email(
            send_order_confirmation_email,
            order,
        )
    )

    # -------------------------------------------------
    # CLEAR AUTHENTICATED USER CART ONLY
    #
    # NEVER trust a client-provided guest session ID
    # to delete another cart.
    # -------------------------------------------------

    if order.user:

        cart = (
            Cart.objects
            .filter(user=order.user)
            .first()
        )

        if cart:
            cart.items.all().delete()

    return True


# =========================================================
# INITIALIZE PAYMENT
# =========================================================

class InitializePaymentView(APIView):

    permission_classes = [AllowAny]

    def post(self, request, order_id):

        checkout_token = request.data.get(
            "checkout_token"
        )

        if not checkout_token:

            return Response(
                {
                    "error": (
                        "Checkout token is required."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:

            order = (
                Order.objects
                .get(
                    id=order_id,
                    checkout_token=checkout_token,
                )
            )

        except Order.DoesNotExist:

            return Response(
                {
                    "error": (
                        "Invalid order or checkout token."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # -------------------------------------------------
        # CANCELLED
        # -------------------------------------------------

        if order.status == "cancelled":

            return Response(
                {
                    "error": (
                        "Cancelled orders cannot be paid."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -------------------------------------------------
        # ALREADY PAID
        # -------------------------------------------------

        if order.payment_status == "paid":

            return Response(
                {
                    "error": (
                        "This order has already been paid for."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -------------------------------------------------
        # REFUNDED
        # -------------------------------------------------

        if order.payment_status == "refunded":

            return Response(
                {
                    "error": (
                        "A refunded order cannot be paid again."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -------------------------------------------------
        # PREVENT DUPLICATE INITIALIZATION
        # -------------------------------------------------

        if (
            order.payment_status == "pending"
            and order.payment_reference
        ):

            return Response(
                {
                    "error": (
                        "A payment has already been initialized "
                        "for this order."
                    ),
                    "reference": order.payment_reference,
                },
                status=status.HTTP_409_CONFLICT,
            )

        # -------------------------------------------------
        # PAYSTACK KEY
        # -------------------------------------------------

        if not settings.PAYSTACK_SECRET_KEY:

            return Response(
                {
                    "error": (
                        "Paystack secret key is not configured."
                    )
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # -------------------------------------------------
        # CREATE PAYMENT REFERENCE
        # -------------------------------------------------

        payment_reference = (
            f"{order.order_number}-"
            f"{uuid.uuid4().hex[:12].upper()}"
        )

        # -------------------------------------------------
        # CALLBACK URL
        # -------------------------------------------------

        callback_url = getattr(
            settings,
            "PAYSTACK_CALLBACK_URL",
            None,
        )

        if not callback_url:

            return Response(
                {
                    "error": (
                        "PAYSTACK_CALLBACK_URL is not configured."
                    )
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # -------------------------------------------------
        # PAYLOAD
        # -------------------------------------------------

        payload = {
            "email": order.email,
            "amount": str(
                int(order.total_amount * 100)
            ),
            "currency": "NGN",
            "reference": payment_reference,
            "callback_url": callback_url,
            "metadata": {
                "order_id": order.id,
                "order_number": order.order_number,
                "checkout_token": str(
                    order.checkout_token
                ),
            },
        }

        try:

            response = requests.post(
                "https://api.paystack.co/transaction/initialize",
                headers={
                    "Authorization": (
                        f"Bearer "
                        f"{settings.PAYSTACK_SECRET_KEY}"
                    ),
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )

            data = response.json()

        except requests.RequestException:

            return Response(
                {
                    "error": (
                        "Could not connect to Paystack."
                    )
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if (
            not response.ok
            or not data.get("status")
            or not data.get("data")
        ):

            return Response(
                {
                    "error": data.get(
                        "message",
                        "Paystack initialization failed.",
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        paystack_data = data["data"]

        paystack_reference = paystack_data.get(
            "reference"
        )

        access_code = paystack_data.get(
            "access_code"
        )

        authorization_url = paystack_data.get(
            "authorization_url"
        )

        if not all([
            paystack_reference,
            access_code,
            authorization_url,
        ]):

            return Response(
                {
                    "error": (
                        "Paystack returned an incomplete "
                        "payment initialization response."
                    )
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        order.payment_reference = (
            paystack_reference
        )

        order.payment_status = "pending"

        order.save(
            update_fields=[
                "payment_reference",
                "payment_status",
                "updated_at",
            ]
        )

        return Response({
            "order_id": order.id,
            "order_number": order.order_number,
            "checkout_token": str(
                order.checkout_token
            ),
            "reference": paystack_reference,
            "access_code": access_code,
            "authorization_url": authorization_url,
        })


# =========================================================
# VERIFY PAYMENT
# =========================================================

class VerifyPaymentView(APIView):

    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):

        reference = (
            request.data.get("reference")
            or ""
        ).strip()

        checkout_token = (
            request.data.get("checkout_token")
            or ""
        ).strip()

        if not reference:

            return Response(
                {
                    "error": "reference is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not checkout_token:

            return Response(
                {
                    "error": "checkout_token is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -------------------------------------------------
        # FIND ORDER BY CHECKOUT TOKEN
        #
        # Do NOT require the submitted reference to equal
        # the current DB reference. Paystack may have a
        # legitimate older transaction reference.
        # -------------------------------------------------

        try:

            order = (
                Order.objects
                .select_for_update()
                .get(
                    checkout_token=checkout_token,
                )
            )

        except Order.DoesNotExist:

            return Response(
                {
                    "error": "Order not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # -------------------------------------------------
        # IDEMPOTENCY
        # -------------------------------------------------

        if order.payment_status == "paid":

            return Response({
                "message": "Payment already verified.",
                "order": OrderSerializer(order).data,
            })

        if order.payment_status == "refunded":

            return Response(
                {
                    "error": (
                        "This order has already been refunded."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if order.status == "cancelled":

            return Response(
                {
                    "error": (
                        "Cancelled orders cannot be paid."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -------------------------------------------------
        # PAYSTACK KEY
        # -------------------------------------------------

        if not settings.PAYSTACK_SECRET_KEY:

            return Response(
                {
                    "error": (
                        "Paystack secret key is not configured."
                    )
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # -------------------------------------------------
        # VERIFY WITH PAYSTACK
        # -------------------------------------------------

        try:

            response = requests.get(
                (
                    "https://api.paystack.co/"
                    f"transaction/verify/{reference}"
                ),
                headers={
                    "Authorization": (
                        f"Bearer "
                        f"{settings.PAYSTACK_SECRET_KEY}"
                    ),
                },
                timeout=30,
            )

            data = response.json()

        except requests.RequestException:

            return Response(
                {
                    "error": (
                        "Could not connect to Paystack."
                    )
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if (
            not response.ok
            or not data.get("status")
        ):

            return Response(
                {
                    "error": data.get(
                        "message",
                        "Payment verification failed.",
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment = data.get(
            "data",
            {}
        )

        # -------------------------------------------------
        # VERIFY REFERENCE
        # -------------------------------------------------

        if payment.get("reference") != reference:

            return Response(
                {
                    "error": (
                        "Paystack payment reference "
                        "does not match the requested reference."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -------------------------------------------------
        # VERIFY METADATA
        # -------------------------------------------------

        if not _payment_metadata_matches_order(
            order,
            payment,
        ):

            return Response(
                {
                    "error": (
                        "Payment metadata does not match "
                        "this order."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -------------------------------------------------
        # VERIFY STATUS
        # -------------------------------------------------

        if payment.get("status") != "success":

            payment_status = payment.get(
                "status"
            )

            if payment_status in [
                "failed",
                "abandoned",
            ]:

                order.payment_status = "failed"

                order.save(
                    update_fields=[
                        "payment_status",
                        "updated_at",
                    ]
                )

            return Response(
                {
                    "error": (
                        "Payment was not successful."
                    ),
                    "payment_status": payment_status,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -------------------------------------------------
        # FINALIZE
        # -------------------------------------------------

        try:

            _finalize_successful_payment(
                order,
                payment,
            )

        except Exception as exc:

            from rest_framework.exceptions import ValidationError

            if isinstance(
                exc,
                ValidationError,
            ):

                detail = exc.detail

                return Response(
                    {
                        "error": detail
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            raise

        return Response({
            "message": (
                "Payment verified successfully."
            ),
            "order": OrderSerializer(order).data,
        })


# =========================================================
# ADMIN REFUND
# =========================================================

class AdminRefundPaymentView(APIView):

    permission_classes = [IsAdminUser]

    @transaction.atomic
    def post(self, request, order_id):

        try:

            order = (
                Order.objects
                .select_for_update()
                .prefetch_related("items")
                .select_related("user", "coupon")
                .get(
                    id=order_id
                )
            )

        except Order.DoesNotExist:

            return Response(
                {
                    "error": "Order not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # -------------------------------------------------
        # ONLY PAID ORDERS
        # -------------------------------------------------

        if order.payment_status != "paid":

            return Response(
                {
                    "error": (
                        "Only paid orders can be refunded."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -------------------------------------------------
        # PAYMENT REFERENCE
        # -------------------------------------------------

        if not order.payment_reference:

            return Response(
                {
                    "error": (
                        "This order has no payment reference."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -------------------------------------------------
        # BLOCK DUPLICATE REFUNDS
        # -------------------------------------------------

        existing_refund = (
            Refund.objects
            .filter(
                order=order,
                status__in=[
                    "pending",
                    "processed",
                ],
            )
            .first()
        )

        if existing_refund:

            return Response(
                {
                    "error": (
                        "A refund for this order already "
                        "exists or is being processed."
                    ),
                    "refund_id": existing_refund.id,
                },
                status=status.HTTP_409_CONFLICT,
            )

        # -------------------------------------------------
        # PAYSTACK KEY
        # -------------------------------------------------

        if not settings.PAYSTACK_SECRET_KEY:

            return Response(
                {
                    "error": (
                        "Paystack secret key is not configured."
                    )
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        reason = (
            request.data.get(
                "reason",
                "Refund processed by admin",
            )
            or "Refund processed by admin"
        ).strip()

        if len(reason) > 500:

            return Response(
                {
                    "error": (
                        "Refund reason cannot exceed "
                        "500 characters."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        refund = Refund.objects.create(
            order=order,
            amount=order.total_amount,
            reason=reason,
            processed_by=request.user,
            status="pending",
        )

        payload = {
            "transaction": order.payment_reference,
            "amount": int(
                order.total_amount * 100
            ),
        }

        try:

            response = requests.post(
                "https://api.paystack.co/refund",
                headers={
                    "Authorization": (
                        f"Bearer "
                        f"{settings.PAYSTACK_SECRET_KEY}"
                    ),
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )

            data = response.json()

        except requests.RequestException:

            refund.status = "failed"

            refund.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

            return Response(
                {
                    "error": (
                        "Could not connect to Paystack."
                    ),
                    "refund_id": refund.id,
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if (
            not response.ok
            or not data.get("status")
        ):

            refund.status = "failed"

            refund.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

            return Response(
                {
                    "error": data.get(
                        "message",
                        "Refund request failed.",
                    ),
                    "refund_id": refund.id,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -------------------------------------------------
        # SAVE REFUND
        # -------------------------------------------------

        refund_data = data.get(
            "data",
            {}
        )

        refund.status = "processed"

        refund.paystack_reference = (
            refund_data.get(
                "transaction_reference"
            )
            or refund_data.get(
                "reference"
            )
            or order.payment_reference
        )

        refund.save(
            update_fields=[
                "status",
                "paystack_reference",
                "updated_at",
            ]
        )

        # -------------------------------------------------
        # RESTORE STOCK + COUPON
        # -------------------------------------------------

        _restore_order_inventory_and_coupon(
            order
        )

        # -------------------------------------------------
        # UPDATE ORDER
        # -------------------------------------------------

        order.payment_status = "refunded"
        order.status = "cancelled"

        order.save(
            update_fields=[
                "payment_status",
                "status",
                "updated_at",
            ]
        )

        # -------------------------------------------------
        # STATUS HISTORY
        # -------------------------------------------------

        OrderStatusHistory.objects.create(
            order=order,
            status="cancelled",
            changed_by=request.user,
            note="Payment refunded by admin.",
        )

        # -------------------------------------------------
        # REFUND EMAIL
        # -------------------------------------------------

        def send_refund_email_after_commit():
            try:
                from .email import send_order_refund_email

                send_order_refund_email(
                    order,
                    refund,
                )

            except Exception as exc:
                print(
                    "REFUND EMAIL ERROR:",
                    repr(exc),
                )

            

        transaction.on_commit(
            send_refund_email_after_commit
        )

        return Response({
            "message": (
                "Payment refunded successfully."
            ),
            "refund_id": refund.id,
            "order_id": order.id,
            "payment_status": order.payment_status,
            "status": order.status,
        })


# =========================================================
# ADMIN REFUND LIST
# =========================================================

class AdminRefundListView(
    generics.ListAPIView
):

    serializer_class = RefundSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):

        queryset = (
            Refund.objects
            .select_related(
                "order",
                "processed_by",
            )
            .all()
            .order_by("-created_at")
        )

        status_filter = (
            self.request.query_params.get(
                "status"
            )
        )

        if status_filter:

            queryset = queryset.filter(
                status=status_filter
            )

        return queryset


# =========================================================
# PAYSTACK WEBHOOK
# =========================================================

class PaystackWebhookView(APIView):

    permission_classes = [AllowAny]

    authentication_classes = []

    @transaction.atomic
    def post(self, request):

        # -------------------------------------------------
        # PAYSTACK SIGNATURE
        # -------------------------------------------------

        signature = request.headers.get(
            "x-paystack-signature"
        )

        if not signature:

            return Response(
                {
                    "error": "Missing Paystack signature."
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not settings.PAYSTACK_SECRET_KEY:

            return Response(
                {
                    "error": (
                        "Paystack secret key is not configured."
                    )
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        expected_signature = hmac.new(
            settings.PAYSTACK_SECRET_KEY.encode(
                "utf-8"
            ),
            request.body,
            hashlib.sha512,
        ).hexdigest()

        if not hmac.compare_digest(
            signature,
            expected_signature,
        ):

            return Response(
                {
                    "error": "Invalid webhook signature."
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # -------------------------------------------------
        # PARSE BODY
        # -------------------------------------------------

        try:

            import json

            payload = json.loads(
                request.body.decode("utf-8")
            )

        except (
            ValueError,
            UnicodeDecodeError,
        ):

            return Response(
                {
                    "error": "Invalid webhook payload."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        event = payload.get(
            "event"
        )

        # -------------------------------------------------
        # ONLY PROCESS SUCCESSFUL CHARGES
        # -------------------------------------------------

        if event != "charge.success":

            return Response(
                {
                    "message": "Event ignored."
                },
                status=status.HTTP_200_OK,
            )

        payment = payload.get(
            "data",
            {}
        )

        reference = payment.get(
            "reference"
        )

        if not reference:

            return Response(
                {
                    "error": (
                        "Payment reference is missing."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -------------------------------------------------
        # FIND ORDER
        # -------------------------------------------------

        order = (
            Order.objects
            .select_for_update()
            .filter(
                payment_reference=reference
            )
            .first()
        )

        # -------------------------------------------------
        # FALLBACK TO METADATA
        #
        # This allows a legitimate Paystack payment to
        # still resolve even if the order reference was
        # changed before webhook processing.
        # -------------------------------------------------

        if not order:

            metadata = _get_payment_metadata(
                payment
            )

            order_id = metadata.get(
                "order_id"
            )

            checkout_token = metadata.get(
                "checkout_token"
            )

            if (
                not order_id
                or not checkout_token
            ):

                return Response(
                    {
                        "error": (
                            "Order could not be identified "
                            "from payment metadata."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:

                order = (
                    Order.objects
                    .select_for_update()
                    .get(
                        id=order_id,
                        checkout_token=checkout_token,
                    )
                )

            except Order.DoesNotExist:

                return Response(
                    {
                        "error": "Order not found."
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

        # -------------------------------------------------
        # IDEMPOTENCY
        # -------------------------------------------------

        if order.payment_status == "paid":

            return Response(
                {
                    "message": "Webhook already processed."
                },
                status=status.HTTP_200_OK,
            )

        if order.payment_status == "refunded":

            return Response(
                {
                    "message": (
                        "Order has already been refunded."
                    )
                },
                status=status.HTTP_200_OK,
            )

        if order.status == "cancelled":

            return Response(
                {
                    "message": (
                        "Cancelled order ignored."
                    )
                },
                status=status.HTTP_200_OK,
            )

        # -------------------------------------------------
        # VERIFY REFERENCE
        # -------------------------------------------------

        if payment.get("reference") != reference:

            return Response(
                {
                    "error": (
                        "Invalid payment reference."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -------------------------------------------------
        # VERIFY PAYMENT STATUS
        # -------------------------------------------------

        if payment.get("status") != "success":

            return Response(
                {
                    "message": (
                        "Payment is not successful."
                    )
                },
                status=status.HTTP_200_OK,
            )

        # -------------------------------------------------
        # VERIFY METADATA
        # -------------------------------------------------

        if not _payment_metadata_matches_order(
            order,
            payment,
        ):

            return Response(
                {
                    "error": (
                        "Payment metadata does not match "
                        "the order."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -------------------------------------------------
        # VERIFY AMOUNT
        # -------------------------------------------------

        expected_amount = int(
            order.total_amount * 100
        )

        if payment.get("amount") != expected_amount:

            return Response(
                {
                    "error": (
                        "Payment amount does not match "
                        "the order amount."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -------------------------------------------------
        # VERIFY CURRENCY
        # -------------------------------------------------

        if payment.get("currency") != "NGN":

            return Response(
                {
                    "error": (
                        "Payment currency does not match "
                        "the order currency."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -------------------------------------------------
        # FINALIZE PAYMENT
        # -------------------------------------------------

        from rest_framework.exceptions import ValidationError

        try:

            _finalize_successful_payment(
                order,
                payment,
            )

        except ValidationError as exc:

            return Response(
                {
                    "error": exc.detail
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -------------------------------------------------
        # SUCCESS
        # -------------------------------------------------

        return Response(
            {
                "message": (
                    "Webhook processed successfully."
                )
            },
            status=status.HTTP_200_OK,
        )
class OrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(
            user=self.request.user
        ).prefetch_related("items")


class OrderDetailView(generics.RetrieveAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(
            user=self.request.user
        ).prefetch_related("items")

class OrderTrackingView(generics.RetrieveAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(
            user=self.request.user
        ).prefetch_related(
            "items",
            "status_history"
        )
class CreateOrderView(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        try:
            browser_cart = request.data.get("cart_items")

            if not isinstance(browser_cart, list) or not browser_cart:
                return Response(
                    {"error": "Cart is empty or invalid."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            customer = request.data.get("customer") or {}

            first_name = str(
                customer.get("firstName") or ""
            ).strip()

            last_name = str(
                customer.get("lastName") or ""
            ).strip()

            full_name = f"{first_name} {last_name}".strip()

            email = str(
                customer.get("email") or ""
            ).strip()

            phone = str(
                customer.get("phone") or ""
            ).strip()

            address = str(
                customer.get("address") or ""
            ).strip()

            city = str(
                customer.get("city") or ""
            ).strip()

            state = str(
                customer.get("state") or ""
            ).strip()

            country = str(
                customer.get("country") or "Nigeria"
            ).strip()

            if not full_name:
                return Response(
                    {"error": "Customer name is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not email:
                return Response(
                    {"error": "Customer email is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            delivery_method = request.data.get(
                "delivery_method"
            )

            if delivery_method not in [
                "delivery",
                "pickup",
            ]:
                return Response(
                    {"error": "Invalid delivery method."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if delivery_method == "delivery":
                if not address or not city or not state:
                    return Response(
                        {
                            "error": (
                                "Delivery address, city and "
                                "state are required."
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            pickup_address = (
                request.data.get("pickup_address")
                or ""
            )

            products_total = Decimal("0.00")

            order_items = []

            # ---------------------------------
            # VALIDATE BROWSER CART
            # ---------------------------------

            for browser_item in browser_cart:

                if not isinstance(
                    browser_item,
                    dict
                ):
                    return Response(
                        {"error": "Invalid cart item."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                product_id = browser_item.get(
                    "product_id"
                )

                quantity = browser_item.get(
                    "quantity"
                )

                try:
                    product_id = int(product_id)
                    quantity = int(quantity)

                except (
                    TypeError,
                    ValueError,
                ):
                    return Response(
                        {
                            "error": "Invalid cart item.",
                            "item": browser_item,
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                if quantity <= 0:
                    return Response(
                        {
                            "error": (
                                "Quantity must be greater "
                                "than zero."
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # ---------------------------------
                # GET PRODUCT FROM DATABASE
                # ---------------------------------

                try:
                    product = Product.objects.get(
                        id=product_id
                    )

                except Product.DoesNotExist:
                    return Response(
                        {
                            "error": (
                                f"Product with ID "
                                f"{product_id} does not exist."
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # ---------------------------------
                # CHECK VARIANT
                # ---------------------------------

                variant = None

                variant_id = browser_item.get(
                    "variant_id"
                )

                if variant_id not in [
                    None,
                    "",
                    0,
                    "0",
                ]:

                    try:
                        variant_id = int(
                            variant_id
                        )

                    except (
                        TypeError,
                        ValueError,
                    ):
                        return Response(
                            {
                                "error": (
                                    "Invalid variant ID."
                                )
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    try:
                        variant = (
                            ProductVariant.objects.get(
                                id=variant_id,
                                product=product,
                            )
                        )

                    except ProductVariant.DoesNotExist:
                        return Response(
                            {
                                "error": (
                                    f"Variant {variant_id} "
                                    f"does not belong to "
                                    f"product {product_id}."
                                )
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                # ---------------------------------
                # VARIANT STOCK
                # ---------------------------------

                if variant:

                    if not variant.in_stock:
                        return Response(
                            {
                                "error": (
                                    f"{product.name} "
                                    f"({variant.size}) "
                                    "is out of stock."
                                )
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    if (
                        quantity
                        > variant.stock_quantity
                    ):
                        return Response(
                            {
                                "error": (
                                    f"Only "
                                    f"{variant.stock_quantity} "
                                    f"units of "
                                    f"{product.name} "
                                    f"({variant.size}) "
                                    "are available."
                                )
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    item_price = variant.price

                    item_size = variant.size

                # ---------------------------------
                # PRODUCT STOCK
                # ---------------------------------

                else:

                    if not product.in_stock:
                        return Response(
                            {
                                "error": (
                                    f"{product.name} "
                                    "is out of stock."
                                )
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    if (
                        quantity
                        > product.stock_quantity
                    ):
                        return Response(
                            {
                                "error": (
                                    f"Only "
                                    f"{product.stock_quantity} "
                                    f"units of "
                                    f"{product.name} "
                                    "are available."
                                )
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    item_price = product.price

                    item_size = (
                        browser_item.get("size")
                        or ""
                    )

                # ---------------------------------
                # CALCULATE ITEM PRICE
                # ---------------------------------

                item_price = Decimal(
                    str(item_price)
                )

                item_subtotal = (
                    item_price * quantity
                )

                products_total += item_subtotal

                order_items.append(
                    {
                        "product": product,
                        "variant": variant,
                        "quantity": quantity,
                        "unit_price": item_price,
                        "subtotal": item_subtotal,
                        "size": item_size,
                    }
                )

            # ---------------------------------
            # SHIPPING
            # ---------------------------------

            shipping_rate = None

            delivery_fee = Decimal(
                "0.00"
            )

            if delivery_method == "pickup":

                shipping_rate = (
                    ShippingRate.objects
                    .filter(
                        delivery_type="pickup",
                        is_active=True,
                    )
                    .order_by(
                        "delivery_fee"
                    )
                    .first()
                )

            else:

                # Normalize the state entered
                # by the customer.
                normalized_state = state.strip()

                shipping_rate = (
                    ShippingRate.objects
                    .filter(
                        delivery_type="state",
                        is_active=True,
                        state__iexact=normalized_state,
                    )
                    .order_by(
                        "delivery_fee"
                    )
                    .first()
                )

            if not shipping_rate:
                return Response(
                    {
                        "error": (
                            "No shipping rate is "
                            "available for the selected "
                            "delivery method and state."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            delivery_fee = Decimal(
                str(
                    shipping_rate.delivery_fee
                    or 0
                )
            )

            if delivery_method == "pickup":

                pickup_address = (
                    shipping_rate.pickup_address
                    or pickup_address
                )

            # ---------------------------------
            # COUPON
            # ---------------------------------

            coupon = None

            discount = Decimal(
                "0.00"
            )

            coupon_code = request.data.get(
                "coupon_code"
            )

            if coupon_code:

                coupon_code = str(
                    coupon_code
                ).strip()

                if coupon_code:

                    try:
                        coupon = (
                            Coupon.objects.get(
                                code__iexact=coupon_code
                            )
                        )

                    except Coupon.DoesNotExist:
                        return Response(
                            {
                                "error": (
                                    "Invalid coupon code."
                                )
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    if not coupon.is_active:
                        return Response(
                            {
                                "error": (
                                    "This coupon is "
                                    "no longer active."
                                )
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    if (
                        coupon.expires_at
                        and coupon.expires_at
                        <= timezone.now()
                    ):
                        return Response(
                            {
                                "error": (
                                    "This coupon has expired."
                                )
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    if (
                        coupon.usage_limit
                        is not None
                        and coupon.used_count
                        >= coupon.usage_limit
                    ):
                        return Response(
                            {
                                "error": (
                                    "This coupon has "
                                    "reached its usage limit."
                                )
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    if (
                        coupon.discount_type
                        == "percentage"
                    ):

                        discount = (
                            products_total
                            * Decimal(
                                str(
                                    coupon.discount_value
                                )
                            )
                            / Decimal("100")
                        )

                    else:

                        discount = Decimal(
                            str(
                                coupon.discount_value
                            )
                        )

                    discount = min(
                        discount,
                        products_total,
                    )

            # ---------------------------------
            # FINAL TOTAL
            # ---------------------------------

            total_amount = max(
                Decimal("0.00"),
                products_total
                - discount
                + delivery_fee,
            )

            # ---------------------------------
            # USER
            # ---------------------------------

            user = (
                request.user
                if request.user.is_authenticated
                else None
            )

            # ---------------------------------
            # CREATE ORDER
            # ---------------------------------

            order = Order.objects.create(
                user=user,
                full_name=full_name,
                email=email,
                phone=phone,
                address=address,
                city=city,
                state=state,
                delivery_method=delivery_method,
                pickup_address=(
                    pickup_address
                    if delivery_method == "pickup"
                    else None
                ),
                coupon=coupon,
                delivery_fee=delivery_fee,
                total_amount=total_amount,
                payment_status="pending",
                status="pending",
            )

            # ---------------------------------
            # CREATE ORDER ITEMS
            # ---------------------------------

            for item in order_items:

                OrderItem.objects.create(
                    order=order,
                    product=item["product"],
                    variant=item["variant"],
                    quantity=item["quantity"],
                    product_price=item["unit_price"],
                    subtotal=item["subtotal"],
                    product_name=item[
                        "product"
                    ].name,
                    variant_size=item[
                        "size"
                    ],
                )

            # ---------------------------------
            # SUCCESS
            # ---------------------------------

            return Response(
                {
                    "message": (
                        "Order created successfully."
                    ),
                    "order": (
                        OrderSerializer(
                            order
                        ).data
                    ),
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:

            print(
                "CREATE ORDER ERROR:",
                repr(e)
            )

            return Response(
                {
                    "error": (
                        "Unable to create order."
                    )
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        
class MyOrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Order.objects
            .filter(user=self.request.user)
            .prefetch_related("items", "status_history")
            .select_related("coupon")
            .order_by("-created_at")
        )    
