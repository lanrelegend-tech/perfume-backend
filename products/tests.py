from rest_framework.test import APITestCase

from products.models import Product


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
