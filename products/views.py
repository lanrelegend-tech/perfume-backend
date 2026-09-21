from rest_framework import generics, status
from rest_framework.permissions import IsAdminUser
from .models import (
    Category,
    Product,
    ProductVariant,
    ProductImage,
)
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import (
    ProductSerializer,
    CategorySerializer,
    AdminProductSerializer,
    AdminInventorySerializer,
    AdminProductVariantSerializer,
    AdminProductImageSerializer,
)

class ProductListView(generics.ListAPIView):
    queryset = Product.objects.all().order_by("-created_at")
    serializer_class = ProductSerializer

    filterset_fields = [
        "category",
        "brand",
        "in_stock",
        "featured",
    ]

    search_fields = [
        "name",
        "brand",
        "description",
        "fragrance_notes",
    ]

    ordering_fields = [
        "price",
        "created_at",
        "name",
    ]

class ProductDetailView(generics.RetrieveAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer


class CategoryListView(generics.ListAPIView):
    queryset = Category.objects.all().order_by("name")
    serializer_class = CategorySerializer

class AdminProductListCreateView(generics.ListCreateAPIView):
    serializer_class = AdminProductSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        queryset = Product.objects.all().order_by("-created_at")

        category = self.request.query_params.get("category")
        brand = self.request.query_params.get("brand")
        in_stock = self.request.query_params.get("in_stock")
        featured = self.request.query_params.get("featured")
        search = self.request.query_params.get("search")

        if category:
            queryset = queryset.filter(
                category_id=category
            )

        if brand:
            queryset = queryset.filter(
                brand__iexact=brand
            )

        if in_stock is not None:
            queryset = queryset.filter(
                in_stock=in_stock.lower() == "true"
            )

        if featured is not None:
            queryset = queryset.filter(
                featured=featured.lower() == "true"
            )

        if search:
            from django.db.models import Q

            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(brand__icontains=search)
                | Q(description__icontains=search)
                | Q(fragrance_notes__icontains=search)
            )

        return queryset

class AdminProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Product.objects.all()
    serializer_class = AdminProductSerializer
    permission_classes = [IsAdminUser]

class AdminCategoryListCreateView(generics.ListCreateAPIView):
    queryset = Category.objects.all().order_by("name")
    serializer_class = CategorySerializer
    permission_classes = [IsAdminUser]


class AdminCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminUser]   
class AdminInventoryView(generics.ListAPIView):
    serializer_class = AdminInventorySerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        queryset = Product.objects.all().order_by(
            "stock_quantity"
        )

        stock_status = self.request.query_params.get(
            "stock_status"
        )

        if stock_status == "out_of_stock":
            queryset = queryset.filter(
                stock_quantity=0
            )

        elif stock_status == "low_stock":
            queryset = queryset.filter(
                stock_quantity__gt=0,
                stock_quantity__lte=5
            )

        elif stock_status == "in_stock":
            queryset = queryset.filter(
                stock_quantity__gt=5
            )

        return queryset  

class AdminProductVariantListCreateView(
    generics.ListCreateAPIView
):
    serializer_class = AdminProductVariantSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        queryset = ProductVariant.objects.all().select_related(
            "product"
        ).order_by("product", "price")

        product = self.request.query_params.get("product")

        if product:
            queryset = queryset.filter(
                product_id=product
            )

        return queryset


class AdminProductVariantDetailView(
    generics.RetrieveUpdateDestroyAPIView
):
    queryset = ProductVariant.objects.all()
    serializer_class = AdminProductVariantSerializer
    permission_classes = [IsAdminUser]   

class AdminProductImageListCreateView(generics.ListCreateAPIView):
    queryset = ProductImage.objects.select_related("product").all()
    serializer_class = AdminProductImageSerializer
    permission_classes = [IsAdminUser]

    def perform_create(self, serializer):
        product = serializer.validated_data["product"]
        is_primary = serializer.validated_data.get(
            "is_primary",
            False
        )

        if is_primary:
            ProductImage.objects.filter(
                product=product
            ).update(is_primary=False)

        serializer.save()
class AdminProductImageDetailView(
    generics.RetrieveDestroyAPIView
):
    queryset = ProductImage.objects.select_related(
        "product"
    ).all()

    serializer_class = AdminProductImageSerializer
    permission_classes = [IsAdminUser]

    def perform_destroy(self, instance):
        product = instance.product
        was_primary = instance.is_primary

        instance.delete()

        if was_primary:
            next_image = (
                product.images
                .order_by("created_at", "id")
                .first()
            )

            if next_image:
                # Make the next image the primary
                product.images.update(
                    is_primary=False
                )

                next_image.is_primary = True
                next_image.save(
                    update_fields=["is_primary"]
                )

                # Make the same image the actual
                # Product.image used by the big card.
                product.image.name = (
                    next_image.image.name
                )

                product.save(
                    update_fields=[
                        "image",
                        "updated_at",
                    ]
                )
            else:
                # No images remain.
                product.image = None

                product.save(
                    update_fields=[
                        "image",
                        "updated_at",
                    ]
                )
    
class AdminProductBulkImageUploadView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        product_id = request.data.get("product")
        images = request.FILES.getlist("images")

        if not product_id:
            return Response(
                {"error": "Product ID is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not images:
            return Response(
                {"error": "At least one image is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            product = Product.objects.get(
                id=product_id
            )
        except Product.DoesNotExist:
            return Response(
                {"error": "Product not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        created_images = []

        has_primary = product.images.filter(
            is_primary=True
        ).exists()

        for index, image in enumerate(images):
            product_image = ProductImage.objects.create(
                product=product,
                image=image,
                is_primary=(
                    not has_primary
                    and index == 0
                )
            )

            if product_image.is_primary:
                has_primary = True

            created_images.append(product_image)

        serializer = AdminProductImageSerializer(
            created_images,
            many=True,
            context={"request": request}
        )

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )
class AdminLowStockView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        try:
            threshold = int(
                request.query_params.get(
                    "threshold",
                    5
                )
            )
        except ValueError:
            return Response(
                {
                    "error": (
                        "threshold must be a valid number"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if threshold < 0:
            return Response(
                {
                    "error": (
                        "threshold cannot be negative"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        products = Product.objects.filter(
            stock_quantity__gt=0,
            stock_quantity__lte=threshold
        ).order_by(
            "stock_quantity"
        )

        variants = ProductVariant.objects.filter(
            stock_quantity__gt=0,
            stock_quantity__lte=threshold
        ).select_related(
            "product"
        ).order_by(
            "stock_quantity"
        )

        out_of_stock_products = Product.objects.filter(
            stock_quantity=0
        ).order_by(
            "name"
        )

        out_of_stock_variants = ProductVariant.objects.filter(
            stock_quantity=0
        ).select_related(
            "product"
        ).order_by(
            "product__name"
        )

        return Response({
            "threshold": threshold,

            "low_stock_products": [
                {
                    "id": product.id,
                    "name": product.name,
                    "brand": product.brand,
                    "stock_quantity": product.stock_quantity,
                    "in_stock": product.in_stock,
                }
                for product in products
            ],

            "low_stock_variants": [
                {
                    "id": variant.id,
                    "product_id": variant.product.id,
                    "product_name": variant.product.name,
                    "size": variant.size,
                    "stock_quantity": variant.stock_quantity,
                    "in_stock": variant.in_stock,
                }
                for variant in variants
            ],

            "out_of_stock_products": [
                {
                    "id": product.id,
                    "name": product.name,
                    "brand": product.brand,
                    "stock_quantity": product.stock_quantity,
                    "in_stock": product.in_stock,
                }
                for product in out_of_stock_products
            ],

            "out_of_stock_variants": [
                {
                    "id": variant.id,
                    "product_id": variant.product.id,
                    "product_name": variant.product.name,
                    "size": variant.size,
                    "stock_quantity": variant.stock_quantity,
                    "in_stock": variant.in_stock,
                }
                for variant in out_of_stock_variants
            ],

            "summary": {
                "low_stock_products": products.count(),
                "low_stock_variants": variants.count(),
                "out_of_stock_products": (
                    out_of_stock_products.count()
                ),
                "out_of_stock_variants": (
                    out_of_stock_variants.count()
                ),
            },
        })             