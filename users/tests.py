from django.contrib.auth.models import User
from rest_framework.test import APITestCase


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
