from rest_framework import generics, status
from django.conf import settings

from .bulk_importer import import_products
from .cache_utils import purge_products_cache
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAdminUser
from django.shortcuts import get_object_or_404
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

LOW_STOCK_THRESHOLD = 3

class ProductListView(generics.ListAPIView):
    queryset = Product.objects.all().order_by("-created_at")
    serializer_class = ProductSerializer
    pagination_class = None

    filterset_fields = [
        "category",
        "brand",
        "in_stock",
        "featured",
         "is_preorder",
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
    lookup_field = "slug"

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        lookup_value = self.kwargs[self.lookup_field]
        lookup = (
            {"pk": lookup_value}
            if str(lookup_value).isdigit()
            else {self.lookup_field: lookup_value}
        )
        obj = get_object_or_404(queryset, **lookup)
        self.check_object_permissions(self.request, obj)
        return obj


class CategoryListView(generics.ListAPIView):
    queryset = Category.objects.all().order_by("name")
    serializer_class = CategorySerializer

class AdminProductListCreateView(generics.ListCreateAPIView):
    serializer_class = AdminProductSerializer
    permission_classes = [IsAdminUser]
    pagination_class = None

    def get_queryset(self):
        queryset = Product.objects.all().order_by("-created_at")

        category = self.request.query_params.get("category")
        brand = self.request.query_params.get("brand")
        in_stock = self.request.query_params.get("in_stock")
        featured = self.request.query_params.get("featured")
        is_preorder = self.request.query_params.get("is_preorder")
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

        if is_preorder is not None:
             queryset = queryset.filter(
                 is_preorder=is_preorder.lower() == "true"
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
    def perform_create(self, serializer):
        serializer.save()
        purge_products_cache()

class AdminProductDetailView(
    generics.RetrieveUpdateDestroyAPIView
):
    queryset = Product.objects.all()
    serializer_class = AdminProductSerializer
    permission_classes = [IsAdminUser]
    def perform_update(self, serializer):
        serializer.save()
        purge_products_cache()    
    def perform_destroy(self, instance):
        # Collect unique image names first because Product.image
        # and the primary ProductImage can point to the same
        # Cloudinary asset.
        image_names = set()

        if instance.image and instance.image.name:
            image_names.add(instance.image.name)

        for product_image in instance.images.all():
            if product_image.image and product_image.image.name:
                image_names.add(product_image.image.name)

        # Delete each Cloudinary asset only once.
        for image_name in image_names:
            instance.image.storage.delete(image_name)

        # Finally delete the product and its related database records.
        instance.delete()  
        purge_products_cache()  

    
        
class AdminCategoryListCreateView(generics.ListCreateAPIView):
    queryset = Category.objects.all().order_by("name")
    serializer_class = CategorySerializer
    permission_classes = [IsAdminUser]
    def perform_create(self, serializer):
        serializer.save()
        purge_products_cache()    


class AdminCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminUser]   
    def perform_update(self, serializer):
        serializer.save()
        purge_products_cache()

    def perform_destroy(self, instance):
        instance.delete()
        purge_products_cache()    
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
    def perform_create(self, serializer):
        serializer.save()
        purge_products_cache()    

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
    def perform_update(self, serializer):
        serializer.save()
        purge_products_cache()

    def perform_destroy(self, instance):
        instance.delete()
        purge_products_cache()      

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
        purge_products_cache()
class AdminProductImageDetailView(
    generics.RetrieveDestroyAPIView
):
    queryset = ProductImage.objects.select_related(
        "product"
    ).all()
    serializer_class = AdminProductImageSerializer
    permission_classes = [IsAdminUser]

    def post(self, request, *args, **kwargs):
        instance = self.get_object()
        product = instance.product

        product.images.update(
            is_primary=False
        )

        instance.is_primary = True
        instance.save(
            update_fields=["is_primary"]
        )

        product.image.name = instance.image.name

        product.save(
            update_fields=[
                "image",
                "updated_at",
            ]
        )
        purge_products_cache()

        serializer = self.get_serializer(instance)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    def perform_destroy(self, instance):
        product = instance.product
        was_primary = instance.is_primary
        image_name = (
            instance.image.name
            if instance.image
            else None
        )

        # Delete the actual Cloudinary asset before deleting
        # the ProductImage database record.
        if image_name:
            instance.image.storage.delete(image_name)

        # Delete the ProductImage database record.
        instance.delete()

        if was_primary:
            next_image = (
                product.images
                .order_by("created_at", "id")
                .first()
            )

            if next_image:
                # Make the next image the primary image.
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
            purge_products_cache()
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
            purge_products_cache()

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

class AdminProductBulkImportView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]

    def post(self, request):
        return import_products(request)