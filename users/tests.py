from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from rest_framework.test import APITestCase

from orders.models import Order
from users.models import EmailVerificationCode
from users.views import (
    claim_guest_orders_for_user,
    claim_guest_orders_for_verified_users,
)


class CurrentUserTests(APITestCase):
    def test_current_user_response_includes_staff_status(self):
        user = User.objects.create_user(
            username="staff-user",
            email="staff@example.com",
            password="secure-password",
            is_staff=True,
        )
        self.client.force_authenticate(user=user)

        response = self.client.get("/api/users/me/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_staff"])


class GuestOrderClaimTests(APITestCase):
    def test_claim_guest_orders_for_user_matches_email(self):
        user = User.objects.create_user(
            username="ada",
            email="ada@example.com",
            password="secure-password",
        )
        order = Order.objects.create(
            full_name="Ada Customer",
            phone="08000000000",
            email="ADA@example.com",
            address="1 Test Street",
            city="Ikeja",
            state="Lagos",
            total_amount="25000.00",
        )

        claimed_count = claim_guest_orders_for_user(
            user
        )

        order.refresh_from_db()
        self.assertEqual(claimed_count, 1)
        self.assertEqual(order.user, user)

    def test_admin_claim_only_uses_verified_users(self):
        verified_user = User.objects.create_user(
            username="verified",
            email="verified@example.com",
            password="secure-password",
        )
        unverified_user = User.objects.create_user(
            username="unverified",
            email="unverified@example.com",
            password="secure-password",
        )

        EmailVerificationCode.objects.create(
            user=verified_user,
            code=make_password("123456"),
            expires_at=timezone.now(),
            verified_at=timezone.now(),
        )
        EmailVerificationCode.objects.create(
            user=unverified_user,
            code=make_password("123456"),
            expires_at=timezone.now(),
        )

        verified_order = Order.objects.create(
            full_name="Verified Customer",
            phone="08000000000",
            email="verified@example.com",
            total_amount="25000.00",
        )
        unverified_order = Order.objects.create(
            full_name="Unverified Customer",
            phone="08000000001",
            email="unverified@example.com",
            total_amount="15000.00",
        )

        claimed_count = (
            claim_guest_orders_for_verified_users()
        )

        verified_order.refresh_from_db()
        unverified_order.refresh_from_db()

        self.assertEqual(claimed_count, 1)
        self.assertEqual(
            verified_order.user,
            verified_user,
        )
        self.assertIsNone(
            unverified_order.user
        )
