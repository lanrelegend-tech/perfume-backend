from django.db import models


class StoreSettings(models.Model):
    store_name = models.CharField(
        max_length=200,
        default="VELRA"
    )

    store_email = models.EmailField(
        blank=True
    )

    store_phone = models.CharField(
        max_length=30,
        blank=True
    )

    store_address = models.TextField(
        blank=True
    )

    currency = models.CharField(
        max_length=10,
        default="NGN"
    )

    free_shipping_threshold = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    maintenance_mode = models.BooleanField(
        default=False
    )

    instagram_url = models.URLField(
        blank=True
    )

    facebook_url = models.URLField(
        blank=True
    )

    tiktok_url = models.URLField(
        blank=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        verbose_name = "Store Settings"
        verbose_name_plural = "Store Settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return self.store_name