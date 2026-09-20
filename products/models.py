from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    GENDER_CHOICES = [
        ("men", "Men"),
        ("women", "Women"),
        ("unisex", "Unisex"),
    ]

    CONCENTRATION_CHOICES = [
        ("edp", "Eau de Parfum (EDP)"),
        ("edt", "Eau de Toilette (EDT)"),
        ("parfum", "Parfum / Extrait"),
        ("edc", "Eau de Cologne (EDC)"),
        ("mist", "Body Mist"),
    ]

    name = models.CharField(max_length=200)
    brand = models.CharField(max_length=100)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, default="unisex")
    concentration = models.CharField(max_length=20, choices=CONCENTRATION_CHOICES, blank=True)
    description = models.TextField()

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products"
    )

    price = models.DecimalField(max_digits=10, decimal_places=2)

    size = models.CharField(max_length=50, blank=True)

    fragrance_notes = models.TextField(blank=True)

    image = models.ImageField(
        upload_to="products/",
        blank=True,
        null=True
    )

    stock_quantity = models.PositiveIntegerField(default=0)

    in_stock = models.BooleanField(default=True)
    featured = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class ProductVariant(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="variants"
    )

    size = models.CharField(max_length=50)

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    stock_quantity = models.PositiveIntegerField(
        default=0
    )

    in_stock = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        unique_together = ("product", "size")
        ordering = ["price"]

    def save(self, *args, **kwargs):
        if self.stock_quantity <= 0:
            self.stock_quantity = 0
            self.in_stock = False
        else:
            self.in_stock = True

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} - {self.size}"   
class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images"
    )

    image = models.ImageField(
        upload_to="products/"
    )

    is_primary = models.BooleanField(
        default=False
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["-is_primary", "created_at"]

    def __str__(self):
        return f"{self.product.name} image"     