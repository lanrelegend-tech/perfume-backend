from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from orders.models import Order
from coupons.models import Coupon
from products.models import Product
from shipping.models import ShippingRate


class CheckoutTests(APITestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name="Test Fragrance",
            brand="ORENTEMIST",
            description="A test fragrance.",
            price=Decimal("25000.00"),
            stock_quantity=5,
            in_stock=True,
        )
        ShippingRate.objects.create(
            state="Lagos",
            delivery_type="state",
            delivery_fee=Decimal("2500.00"),
        )
        self.payload = {
            "cart_items": [
                {
                    "product_id": self.product.id,
                    "quantity": 1,
                }
            ],
            "customer": {
                "firstName": "Ada",
                "lastName": "Customer",
                "email": "ada@example.com",
                "phone": "08000000000",
                "address": "1 Test Street",
                "city": "Ikeja",
                "state": "Lagos",
            },
            "delivery_method": "delivery",
        }

    def test_guest_can_create_an_order(self):
        response = self.client.post(
            "/api/orders/create/",
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(pk=response.data["order"]["id"])
        self.assertIsNone(order.user)

    def test_authenticated_customer_order_is_linked_to_user(self):
        user = User.objects.create_user(
            username="ada",
            email="ada@example.com",
            password="secure-password",
        )
        self.client.force_authenticate(user=user)

        response = self.client.post(
            "/api/orders/create/",
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(pk=response.data["order"]["id"])
        self.assertEqual(order.user, user)

    def test_coupon_code_reduces_the_saved_order_total(self):
        Coupon.objects.create(
            code="SAVE10",
            discount_type="percentage",
            discount_value=Decimal("10.00"),
        )
        payload = {
            **self.payload,
            "coupon_code": "SAVE10",
        }

        response = self.client.post(
            "/api/orders/create/",
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(pk=response.data["order"]["id"])
        self.assertEqual(order.discount_amount, Decimal("2500.00"))
        self.assertEqual(order.total_amount, Decimal("25000.00"))

    def test_pickup_order_response_includes_pickup_address(self):
        pickup_address = "ORENTEMIST Studio, Lekki Phase 1"
        ShippingRate.objects.create(
            delivery_type="pickup",
            delivery_fee=Decimal("0.00"),
            pickup_address=pickup_address,
        )
        payload = {
            **self.payload,
            "customer": {
                **self.payload["customer"],
                "address": "",
                "city": "",
                "state": "",
            },
            "delivery_method": "pickup",
        }

        response = self.client.post(
            "/api/orders/create/",
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        order_data = response.data["order"]
        self.assertEqual(order_data["delivery_method"], "pickup")
        self.assertEqual(order_data["pickup_address"], pickup_address)
