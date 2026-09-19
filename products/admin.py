from django.contrib import admin
from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "brand",
        "category",
        "price",
        "stock_quantity",
        "in_stock",
        "featured",
        "created_at",
    )

    list_filter = (
        "category",
        "brand",
        "in_stock",
        "featured",
    )

    search_fields = (
        "name",
        "brand",
        "description",
        "fragrance_notes",
    )

    list_editable = (
        "price",
        "stock_quantity",
        "in_stock",
        "featured",
    )