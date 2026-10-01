from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase


class NewsletterImageUploadTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="newsletter-admin",
            email="newsletter-admin@example.com",
            password="password",
        )
        self.client.force_authenticate(self.admin)

    @patch("newsletter.views.default_storage")
    @patch("newsletter.views.upload_brevo_campaign_image")
    def test_upload_moves_image_to_brevo_and_removes_temporary_file(
        self,
        mocked_upload,
        mocked_storage,
    ):
        mocked_storage.save.return_value = "newsletter/banner.jpg"
        mocked_storage.url.return_value = (
            "https://res.cloudinary.com/example/banner.jpg"
        )
        mocked_upload.return_value = (
            "https://img.mailinblue.com/example/banner.jpg"
        )

        response = self.client.post(
            "/api/newsletter/upload-image/",
            {
                "image": SimpleUploadedFile(
                    "banner.jpg",
                    b"image content",
                    content_type="image/jpeg",
                )
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.data["url"],
            "https://img.mailinblue.com/example/banner.jpg",
        )
        mocked_upload.assert_called_once_with(
            "https://res.cloudinary.com/example/banner.jpg",
            "banner.jpg",
        )
        mocked_storage.delete.assert_called_once_with(
            "newsletter/banner.jpg"
        )

# Create your tests here.
