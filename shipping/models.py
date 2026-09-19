from django.db import models


class ShippingRate(models.Model):
    state = models.CharField(
        max_length=100,
        unique=True
    )

    delivery_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"{self.state} - ₦{self.delivery_fee:,.2f}"