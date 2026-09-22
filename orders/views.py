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
    serializer_class = OrderSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        queryset = Order.objects.all().prefetch_related(
            "items",
              "status_history"
        ).select_related(
            "user",
            "coupon"
        )

        status_filter = self.request.query_params.get("status")
        payment_status = self.request.query_params.get("payment_status")
        search = self.request.query_params.get("search")

        if status_filter:
            queryset = queryset.filter(
                status=status_filter
            )

        if payment_status:
            queryset = queryset.filter(
                payment_status=payment_status
            )

        if search:
            queryset = queryset.filter(
                Q(
                    order_number__icontains=search
                )
                | Q(
                    full_name__icontains=search
                )
                | Q(
                    email__icontains=search
                )
                | Q(
                    phone__icontains=search
                )
                | Q(
                    tracking_number__icontains=search
                )
            )

        return queryset

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
                "status_history"
            )
            .select_related(
                "user",
                "coupon"
            )
        )

    def perform_update(self, serializer):
        order = self.get_object()

        old_status = order.status

        new_status = serializer.validated_data.get(
            "status",
            old_status
        )

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
                "cancelled",
            ],
            "shipped": [
                "delivered",
            ],
            "delivered": [],
            "cancelled": [],
        }

        allowed_statuses = allowed_transitions.get(
            old_status,
            []
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

        updated_order = serializer.save()

        new_status = updated_order.status

        if old_status != new_status:
            OrderStatusHistory.objects.create(
                order=updated_order,
                status=new_status,
                changed_by=self.request.user,
            )

        if (
            old_status != "shipped"
            and new_status == "shipped"
        ):
            from .email import (
                send_order_shipped_email
            )

            try:
                send_order_shipped_email(
                    updated_order
                )
            except Exception as e:
                print(
                    "SHIPPED EMAIL ERROR:",
                    repr(e)
                )

        elif (
            old_status != "delivered"
            and new_status == "delivered"
        ):
            from .email import (
                send_order_delivered_email
            )

            try:
                send_order_delivered_email(
                    updated_order
                )
            except Exception as e:
                print(
                    "DELIVERED EMAIL ERROR:",
                    repr(e)
                )

class InitializePaymentView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, order_id):
        try:
            order = Order.objects.get(
                id=order_id
            )
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        if order.payment_status == "paid":
            return Response(
                {
                    "error": (
                        "This order has already been paid for"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if not settings.PAYSTACK_SECRET_KEY:
            return Response(
                {
                    "error": (
                        "Paystack secret key is not configured"
                    )
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        payment_reference = (
            f"{order.order_number}-"
            f"{uuid.uuid4().hex[:12].upper()}"
        )

        payload = {
            "email": order.email,
            "amount": str(
                int(order.total_amount * 100)
            ),
            "currency": "NGN",
            "reference": payment_reference,

            "callback_url": (
                "http://localhost:3000/payment-callback"
            ),

            "metadata": {
                "order_id": order.id,
                "order_number": order.order_number,
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
                        "Could not connect to Paystack"
                    )
                },
                status=status.HTTP_502_BAD_GATEWAY
            )

        if not response.ok or not data.get("status"):
            return Response(
                {
                    "error": data.get(
                        "message",
                        "Paystack initialization failed"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        order.payment_reference = (
            data["data"]["reference"]
        )

        order.save(
            update_fields=[
                "payment_reference",
                "updated_at",
            ]
        )

        return Response({
            "order_id": order.id,
            "order_number": order.order_number,
            "reference": data["data"]["reference"],
            "access_code": data["data"]["access_code"],
            "authorization_url": (
                data["data"]["authorization_url"]
            ),
        })

    
class VerifyPaymentView(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        reference = request.data.get("reference")

        if not reference:
            return Response(
                {"error": "reference is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            order = (
                Order.objects
                .select_for_update()
                .get(
                    payment_reference=reference
                )
            )
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        if order.payment_status == "paid":
            return Response({
                "message": "Payment already verified",
                "order": OrderSerializer(order).data,
            })

        if not settings.PAYSTACK_SECRET_KEY:
            return Response(
                {
                    "error": (
                        "Paystack secret key is not configured"
                    )
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # ---------------------------------
        # VERIFY PAYMENT WITH PAYSTACK
        # ---------------------------------

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
                        "Could not connect to Paystack"
                    )
                },
                status=status.HTTP_502_BAD_GATEWAY
            )

        if not response.ok or not data.get("status"):
            return Response(
                {
                    "error": data.get(
                        "message",
                        "Payment verification failed"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        payment = data.get("data", {})

        # ---------------------------------
        # CHECK PAYMENT STATUS
        # ---------------------------------

        if payment.get("status") != "success":
            payment_status = payment.get("status")

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
                    "error": "Payment was not successful",
                    "payment_status": payment_status,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # ---------------------------------
        # VERIFY PAYMENT AMOUNT
        # ---------------------------------

        if payment.get("amount") != int(
            order.total_amount * 100
        ):
            return Response(
                {
                    "error": (
                        "Payment amount does not match "
                        "the order amount"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # ---------------------------------
        # VERIFY CURRENCY
        # ---------------------------------

        if payment.get("currency") != "NGN":
            return Response(
                {
                    "error": (
                        "Payment currency does not match "
                        "the order currency"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # ---------------------------------
        # CHECK AND LOCK STOCK
        # ---------------------------------

        for item in order.items.select_related(
            "product",
            "variant"
        ).all():

            if item.variant:
                variant = (
                    ProductVariant.objects
                    .select_for_update()
                    .get(pk=item.variant.pk)
                )

                if (
                    not variant.in_stock
                    or variant.stock_quantity < item.quantity
                ):
                    return Response(
                        {
                            "error": (
                                f"Not enough stock for "
                                f"{item.product_name} "
                                f"{item.variant_size}"
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

            elif item.product:
                product = (
                    item.product.__class__.objects
                    .select_for_update()
                    .get(pk=item.product.pk)
                )

                if (
                    not product.in_stock
                    or product.stock_quantity < item.quantity
                ):
                    return Response(
                        {
                            "error": (
                                f"Not enough stock for "
                                f"{item.product_name}"
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

        # ---------------------------------
        # REDUCE STOCK
        # ---------------------------------

        for item in order.items.select_related(
            "product",
            "variant"
        ).all():

            if item.variant:
                variant = (
                    ProductVariant.objects
                    .select_for_update()
                    .get(pk=item.variant.pk)
                )

                variant.stock_quantity -= item.quantity

                if variant.stock_quantity <= 0:
                    variant.stock_quantity = 0
                    variant.in_stock = False

                variant.save(
                    update_fields=[
                        "stock_quantity",
                        "in_stock",
                    ]
                )

            elif item.product:
                product = (
                    item.product.__class__.objects
                    .select_for_update()
                    .get(pk=item.product.pk)
                )

                product.stock_quantity -= item.quantity

                if product.stock_quantity <= 0:
                    product.stock_quantity = 0
                    product.in_stock = False

                product.save(
                    update_fields=[
                        "stock_quantity",
                        "in_stock",
                    ]
                )

        # ---------------------------------
        # INCREASE COUPON USAGE
        # ---------------------------------

        if order.coupon_id:
            coupon = (
                Coupon.objects
                .select_for_update()
                .get(pk=order.coupon_id)
            )

            if (
                coupon.usage_limit is not None
                and coupon.used_count
                >= coupon.usage_limit
            ):
                return Response(
                    {
                        "error": (
                            "This coupon has reached "
                            "its usage limit"
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            coupon.used_count += 1

            coupon.save(
                update_fields=[
                    "used_count"
                ]
            )

            if order.user:
                coupon.used_by.add(order.user)

        # ---------------------------------
        # MARK ORDER AS PAID
        # ---------------------------------

        old_status = order.status

        order.payment_status = "paid"
        order.status = "confirmed"
        order.payment_reference = (
            payment.get(
                "reference",
                reference
            )
        )

        order.save(
            update_fields=[
                "payment_status",
                "status",
                "payment_reference",
                "updated_at",
            ]
        )

        # ---------------------------------
        # ORDER STATUS HISTORY
        # ---------------------------------

        if old_status != order.status:
            OrderStatusHistory.objects.create(
                order=order,
                status=order.status,
                changed_by=None,
                note="Payment confirmed",
            )

         # ---------------------------------
         # SEND CONFIRMATION EMAIL
         # ---------------------------------

        print("ABOUT TO SEND ORDER EMAIL")
        print("ORDER EMAIL:", order.email)

        try:
            send_order_confirmation_email(order)
            print("ORDER EMAIL FUNCTION FINISHED")
        except Exception as e:
            print("EMAIL ERROR:", repr(e))
            
        

        # ---------------------------------
        # CLEAR CART
        # ---------------------------------

        guest_session_id = request.headers.get(
            "X-Guest-Session-ID"
        )

        if order.user:
            cart = Cart.objects.filter(
                user=order.user
            ).first()

        elif guest_session_id:
            cart = Cart.objects.filter(
                session_id=guest_session_id
            ).first()

        else:
            cart = None

        if cart:
            cart.items.all().delete()

        # ---------------------------------
        # SUCCESS RESPONSE
        # ---------------------------------

        return Response({
            "message": "Payment verified successfully",
            "order": OrderSerializer(order).data,
        })
class AdminRefundPaymentView(APIView):
    permission_classes = [IsAdminUser]

    @transaction.atomic
    def post(self, request, order_id):
        try:
            order = (
                Order.objects
                .select_for_update()
                .get(id=order_id)
            )
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        if order.payment_status != "paid":
            return Response(
                {
                    "error": (
                        "Only paid orders can be refunded"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if not order.payment_reference:
            return Response(
                {
                    "error": (
                        "This order has no payment reference"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if not settings.PAYSTACK_SECRET_KEY:
            return Response(
                {
                    "error": (
                        "Paystack secret key is not configured"
                    )
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        reason = request.data.get(
            "reason",
            ""
        ).strip()

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
                        "Could not connect to Paystack"
                    ),
                    "refund_id": refund.id,
                },
                status=status.HTTP_502_BAD_GATEWAY
            )

        if not response.ok or not data.get("status"):
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
                        "Refund request failed"
                    ),
                    "refund_id": refund.id,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

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

        order.payment_status = "refunded"

        order.save(
            update_fields=[
                "payment_status",
                "updated_at",
            ]
        )

        return Response({
            "message": "Refund processed successfully",
            "refund": {
                "id": refund.id,
                "amount": str(refund.amount),
                "reason": refund.reason,
                "status": refund.status,
                "paystack_reference": (
                    refund.paystack_reference
                ),
                "created_at": refund.created_at,
            },
            "order": OrderSerializer(order).data,
        })

class AdminRefundListView(generics.ListAPIView):
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

        status_filter = self.request.query_params.get(
            "status"
        )

        if status_filter:
            queryset = queryset.filter(
                status=status_filter
            )

        return queryset
        
class PaystackWebhookView(APIView):
    authentication_classes = []
    permission_classes = []

    @transaction.atomic
    def post(self, request):

        # -----------------------------
        # VERIFY PAYSTACK SIGNATURE
        # -----------------------------

        signature = request.headers.get(
            "x-paystack-signature"
        )

        if not signature:
            return HttpResponse(
                "Missing signature",
                status=400
            )

        if not settings.PAYSTACK_SECRET_KEY:
            return HttpResponse(
                "Paystack secret key is not configured",
                status=500
            )

        expected_signature = hmac.new(
            settings.PAYSTACK_SECRET_KEY.encode("utf-8"),
            request.body,
            hashlib.sha512
        ).hexdigest()

        if not hmac.compare_digest(
            signature,
            expected_signature
        ):
            return HttpResponse(
                "Invalid signature",
                status=401
            )

        # -----------------------------
        # GET PAYSTACK EVENT
        # -----------------------------

        event = request.data

        if event.get("event") != "charge.success":
            return HttpResponse(
                "Event ignored",
                status=200
            )

        payment = event.get("data", {})

        reference = payment.get("reference")

        if not reference:
            return HttpResponse(
                "Missing payment reference",
                status=400
            )

        # -----------------------------
        # FIND ORDER
        # -----------------------------

        try:
            order = (
                Order.objects
                .select_for_update()
                .get(
                    payment_reference=reference
                )
            )

        except Order.DoesNotExist:

            try:
                order = (
                    Order.objects
                    .select_for_update()
                    .get(
                        order_number=reference
                    )
                )

            except Order.DoesNotExist:
                return HttpResponse(
                    "Order not found",
                    status=404
                )

        # -----------------------------
        # PREVENT DUPLICATE PROCESSING
        # -----------------------------

        if order.payment_status == "paid":
            return HttpResponse(
                "Payment already processed",
                status=200
            )

        # -----------------------------
        # VERIFY PAYMENT STATUS
        # -----------------------------

        if payment.get("status") != "success":
            return HttpResponse(
                "Payment was not successful",
                status=400
            )

        # -----------------------------
        # VERIFY AMOUNT
        # -----------------------------

        expected_amount = int(
            order.total_amount * 100
        )

        if payment.get("amount") != expected_amount:
            return HttpResponse(
                "Payment amount does not match order",
                status=400
            )

        # -----------------------------
        # VERIFY CURRENCY
        # -----------------------------

        if payment.get("currency") != "NGN":
            return HttpResponse(
                "Payment currency does not match order",
                status=400
            )

        # -----------------------------
        # CHECK AND LOCK STOCK
        # -----------------------------

        for item in order.items.select_related(
            "product",
            "variant"
        ).all():

            if item.variant:

                variant = (
                    ProductVariant.objects
                    .select_for_update()
                    .get(
                        pk=item.variant.pk
                    )
                )

                if (
                    not variant.in_stock
                    or variant.stock_quantity < item.quantity
                ):
                    return HttpResponse(
                        (
                            f"Not enough stock for "
                            f"{item.product_name} "
                            f"{item.variant_size}"
                        ),
                        status=400
                    )

            elif item.product:

                product = (
                    item.product.__class__.objects
                    .select_for_update()
                    .get(
                        pk=item.product.pk
                    )
                )

                if (
                    not product.in_stock
                    or product.stock_quantity < item.quantity
                ):
                    return HttpResponse(
                        (
                            f"Not enough stock for "
                            f"{item.product_name}"
                        ),
                        status=400
                    )

        # -----------------------------
        # REDUCE STOCK
        # -----------------------------

        for item in order.items.select_related(
            "product",
            "variant"
        ).all():

            if item.variant:

                variant = (
                    ProductVariant.objects
                    .select_for_update()
                    .get(
                        pk=item.variant.pk
                    )
                )

                variant.stock_quantity -= item.quantity

                if variant.stock_quantity <= 0:
                    variant.stock_quantity = 0
                    variant.in_stock = False

                variant.save(
                    update_fields=[
                        "stock_quantity",
                        "in_stock",
                    ]
                )

            elif item.product:

                product = (
                    item.product.__class__.objects
                    .select_for_update()
                    .get(
                        pk=item.product.pk
                    )
                )

                product.stock_quantity -= item.quantity

                if product.stock_quantity <= 0:
                    product.stock_quantity = 0
                    product.in_stock = False

                product.save(
                    update_fields=[
                        "stock_quantity",
                        "in_stock",
                    ]
                )

        # -----------------------------
        # INCREASE COUPON USAGE
        # -----------------------------

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
                return HttpResponse(
                    "This coupon has reached its usage limit",
                    status=400
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

        # -----------------------------
        # MARK ORDER AS PAID
        # -----------------------------

        old_status = order.status

        order.payment_status = "paid"
        order.status = "confirmed"
        order.payment_reference = (
            payment.get(
                "reference",
                reference
            )
        )

        order.save(
            update_fields=[
                "payment_status",
                "status",
                "payment_reference",
                "updated_at",
            ]
        )

        # -----------------------------
        # ORDER STATUS HISTORY
        # -----------------------------

        if old_status != order.status:

            OrderStatusHistory.objects.create(
                order=order,
                status=order.status,
                changed_by=None,
                note=(
                    "Payment confirmed "
                    "via Paystack webhook"
                ),
            )

        # -----------------------------
        # SEND CONFIRMATION EMAIL
        # -----------------------------

        try:
          send_order_confirmation_email(order)
        except Exception as e:
          print("EMAIL ERROR:", repr(e))
        

        # -----------------------------
        # CLEAR CART
        # -----------------------------

        if order.user:

            cart = Cart.objects.filter(
                user=order.user
            ).first()

        else:

            # Guest orders are handled by
            # VerifyPaymentView using the
            # guest session header.
            #
            # Paystack webhooks do not contain
            # the browser's guest session ID,
            # so we do not attempt to identify
            # a guest cart here.

            cart = None

        if cart:
            cart.items.all().delete()

        # -----------------------------
        # SUCCESS
        # -----------------------------

        return HttpResponse(
            "Webhook processed successfully",
            status=200
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
                    ShippingRate.objects.filter(
                        delivery_type="pickup",
                        is_active=True,
                    )
                    .order_by(
                        "delivery_fee"
                    )
                    .first()
                )

            else:

                shipping_rate = (
                    ShippingRate.objects.filter(
                        delivery_type__iexact="delivery",
                        state__iexact=state,
                        is_active=True,
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
                    ),
                    "detail": str(e),
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
