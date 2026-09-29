from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from orders.models import Order
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
