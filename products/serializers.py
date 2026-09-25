from rest_framework import serializers
from django.db.models import Avg
from .models import Category, Product, ProductVariant, ProductImage


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
        ]

class ProductVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = [
            "id",
            "size",
            "price",
            "stock_quantity",
            "in_stock",
        ]
class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = [
            "id",
            "image",
            "is_primary",
            "created_at",
        ]

class AdminProductImageSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(
        source="product.name",
        read_only=True
    )

    class Meta:
        model = ProductImage
        fields = [
            "id",
            "product",
            "product_name",
            "image",
            "is_primary",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "product_name",
            "created_at",
        ]        

class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)

    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    variants = ProductVariantSerializer(
    many=True,
    read_only=True
    )
    images = ProductImageSerializer(
        many=True,
        read_only=True
    )

    def get_average_rating(self, obj):
        result = obj.reviews.aggregate(
            average=Avg("rating")
        )

        return round(result["average"], 1) if result["average"] else 0

    def get_review_count(self, obj):
        return obj.reviews.count()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "brand",
            "description",
            "category",
            "price",
            "size",
            "fragrance_notes",
            "image",
            "stock_quantity",
"in_stock",
"is_preorder",
"preorder_release_date",
"preorder_message",
"featured",
            "average_rating",
            "review_count",
            "created_at",
            "updated_at",
            "variants",
            "images",
        ]

class AdminProductVariantSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(
        source="product.name",
        read_only=True
    )

    class Meta:
        model = ProductVariant
        fields = [
            "id",
            "product",
            "product_name",
            "size",
            "price",
            "stock_quantity",
            "in_stock",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "product_name",
            "in_stock",
            "created_at",
            "updated_at",
        ]


class AdminProductSerializer(serializers.ModelSerializer):
    category_id = serializers.PrimaryKeyRelatedField(
        source="category",
        queryset=Category.objects.all(),
        allow_null=True,
        required=False
    )

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "brand",
            "description",
            "category_id",
            "price",
            "size",
            "fragrance_notes",
            "image",
            "stock_quantity",
            "in_stock",
            "featured",
            "created_at",
            "updated_at",
            "is_preorder",

"preorder_release_date",

"preorder_message",
        ]

        read_only_fields = [
            "id",
            "in_stock",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        stock_quantity = validated_data.get(
            "stock_quantity",
            0
        )

        validated_data["in_stock"] = (
            stock_quantity > 0
        )

        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "stock_quantity" in validated_data:
            stock_quantity = validated_data[
                "stock_quantity"
            ]

            validated_data["in_stock"] = (
                stock_quantity > 0
            )

        return super().update(
            instance,
            validated_data
        )
class AdminInventorySerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(
        source="category.name",
        read_only=True
    )

    stock_status = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "brand",
            "category_name",
            "price",
            "stock_quantity",
            "in_stock",
            "stock_status",
            "updated_at",
        ]

    def get_stock_status(self, obj):
        if obj.stock_quantity == 0:
            return "out_of_stock"

        if obj.stock_quantity <= 5:
            return "low_stock"

        return "in_stock"          