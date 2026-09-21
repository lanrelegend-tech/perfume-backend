from django.db import models


class ShippingRate(models.Model):
    DELIVERY_TYPE_CHOICES = [
        ("state", "State"),
        ("pickup", "Pickup"),
    ]

    state = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
        null=True,
    )

    delivery_type = models.CharField(
        max_length=20,
        choices=DELIVERY_TYPE_CHOICES,
        default="state",
    )

    delivery_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    pickup_address = models.TextField(
        blank=True,
        default="",
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["delivery_type", "state"]

    def __str__(self):
        if self.delivery_type == "pickup":
            return f"Pickup - ₦{self.delivery_fee}"

        return f"{self.state} - ₦{self.delivery_fee}"