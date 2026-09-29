from django.test import SimpleTestCase
from rest_framework import serializers

from .serializers import CouponSerializer


class CouponSerializerTests(SimpleTestCase):
    def test_zero_usage_limit_requires_a_positive_value_or_blank(self):
        serializer = CouponSerializer()

        with self.assertRaises(serializers.ValidationError):
            serializer.validate_usage_limit(0)

    def test_zero_maximum_discount_requires_a_positive_value_or_blank(self):
        serializer = CouponSerializer()

        with self.assertRaises(serializers.ValidationError):
            serializer.validate_maximum_discount(0)
