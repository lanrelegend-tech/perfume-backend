from django.db import models
from django.contrib.auth.models import User
from products.models import Product


class Order(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("processing", "Processing"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    ]

    PAYMENT_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    ]
    user = models.ForeignKey(
    User,
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name="orders"
)

    order_number = models.CharField(
        max_length=30,
        unique=True,
        editable=False
    )

    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )
    delivery_fee = models.DecimalField(
    max_digits=12,
    decimal_places=2,
    default=0
    )

    coupon = models.ForeignKey(
    "coupons.Coupon",
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name="orders"
    )

    discount_amount = models.DecimalField(
    max_digits=12,
    decimal_places=2,
    default=0
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default="pending"
    )

    payment_reference = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )
    delivery_method = models.CharField(
    max_length=20,
    choices=[
        ("delivery", "Home Delivery"),
        ("pickup", "Pickup"),
    ],
    default="delivery"
)

    pickup_address = models.TextField(
    blank=True,
    null=True
)

    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=30)
    email = models.EmailField()
    address = models.TextField(
    blank=True,
    null=True
)

    city = models.CharField(
    max_length=100,
    blank=True,
    null=True
)

    state = models.CharField(
    max_length=100,
    blank=True,
    null=True
)
    notes = models.TextField(blank=True)
    courier = models.CharField(
        max_length=100,
        blank=True
    )

    tracking_number = models.CharField(
        max_length=100,
        blank=True
    )

    shipped_at = models.DateTimeField(
        null=True,
        blank=True
    )

    delivered_at = models.DateTimeField(
        null=True,
        blank=True
    )    

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        from django.utils import timezone

        if not self.order_number:
            import uuid
            self.order_number = f"VELRA-{uuid.uuid4().hex[:10].upper()}"

        if self.status == "shipped" and not self.shipped_at:
            self.shipped_at = timezone.now()

        if self.status == "delivered" and not self.delivered_at:
            self.delivered_at = timezone.now()

        super().save(*args, **kwargs)

    def __str__(self):
        return self.order_number


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items"
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items"
    )

    variant = models.ForeignKey(
        "products.ProductVariant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items"
    )

    product_name = models.CharField(
        max_length=200
    )

    product_brand = models.CharField(
        max_length=100,
        blank=True
    )

    variant_size = models.CharField(
        max_length=50,
        blank=True
    )

    product_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    quantity = models.PositiveIntegerField(
        default=1
    )

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    def save(self, *args, **kwargs):
        self.subtotal = self.product_price * self.quantity

        super().save(*args, **kwargs)

class Refund(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processed", "Processed"),
        ("failed", "Failed"),
    ]

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="refunds"
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    reason = models.TextField(
        blank=True
    )

    processed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processed_refunds"
    )

    paystack_reference = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"Refund for {self.order.order_number}"
            
class OrderStatusHistory(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="status_history"
    )

    status = models.CharField(
        max_length=20,
        choices=Order.STATUS_CHOICES
    )

    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_status_changes"
    )

    note = models.TextField(blank=True)

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return (
            f"{self.order.order_number} - "
            f"{self.status}"
        )     