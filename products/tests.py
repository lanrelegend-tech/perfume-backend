from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from products.models import Product, ProductImage


class ProductDetailTests(APITestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name="Test Fragrance",
            brand="ORENTEMIST",
            description="A test fragrance.",
            price="25000.00",
        )

    def test_product_is_available_by_slug(self):
        response = self.client.get(f"/api/products/{self.product.slug}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.product.id)

    def test_product_is_available_by_numeric_id_for_existing_cart_links(self):
        response = self.client.get(f"/api/products/{self.product.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.product.id)


class ProductListTests(APITestCase):
    def test_product_list_returns_products_beyond_the_default_page_size(self):
        for index in range(13):
            Product.objects.create(
                name=f"Fragrance {index}",
                brand="ORENTEMIST",
                description="A test fragrance.",
                price="25000.00",
            )

        response = self.client.get("/api/products/")

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 13)


class ProductBulkImportTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="password",
        )
        self.client.force_authenticate(self.admin)

    @patch.object(
        ProductImage._meta.get_field("image").storage,
        "save",
        side_effect=lambda name, content, max_length=None: name,
    )
    def test_bulk_import_uses_attached_image_and_product_defaults(
        self,
        mocked_save,
    ):
        csv_file = SimpleUploadedFile(
            "products.csv",
            (
                "name,brand,description,price,image\n"
                "Test Fragrance,ORENTEMIST,A test fragrance.,25000,test.jpg\n"
            ).encode(),
            content_type="text/csv",
        )
        image_file = SimpleUploadedFile(
            "test.jpg",
            BytesIO(b"test image").getvalue(),
            content_type="image/jpeg",
        )

        response = self.client.post(
            "/api/products/admin/bulk-import/",
            {
                "csv_file": csv_file,
                "images": image_file,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)

        product = Product.objects.get(name="Test Fragrance")
        self.assertEqual(product.gender, "unisex")
        self.assertEqual(product.concentration, "")
        self.assertTrue(product.image.name.endswith("/test.jpg"))
        self.assertTrue(product.images.get().is_primary)
        mocked_save.assert_called_once()

    def test_admin_image_upload_rejects_more_than_four_images(self):
        product = Product.objects.create(
            name="Limited Fragrance",
            brand="ORENTEMIST",
            description="A test fragrance.",
            price="25000.00",
        )
        images = [
            SimpleUploadedFile(
                f"test-{index}.jpg",
                b"test image",
                content_type="image/jpeg",
            )
            for index in range(5)
        ]

        response = self.client.post(
            "/api/products/admin/images/bulk/",
            {
                "product": product.id,
                "images": images,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["error"],
            "A product can have a maximum of 4 images.",
        )

    @patch.object(
        ProductImage._meta.get_field("image").storage,
        "save",
        side_effect=lambda name, content, max_length=None: name,
    )
    def test_admin_image_upload_sets_the_primary_product_image(
        self,
        mocked_save,
    ):
        product = Product.objects.create(
            name="Gallery Fragrance",
            brand="ORENTEMIST",
            description="A test fragrance.",
            price="25000.00",
        )

        response = self.client.post(
            "/api/products/admin/images/bulk/",
            {
                "product": product.id,
                "images": SimpleUploadedFile(
                    "gallery.jpg",
                    b"test image",
                    content_type="image/jpeg",
                ),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        product.refresh_from_db()
        self.assertTrue(product.image.name.endswith("/gallery.jpg"))
        self.assertTrue(product.images.get().is_primary)
        mocked_save.assert_called_once()
