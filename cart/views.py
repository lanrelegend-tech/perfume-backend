from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Cart, CartItem
from .serializers import CartSerializer

from products.models import Product, ProductVariant


class CartView(APIView):
    permission_classes = [IsAuthenticated]

    def get_cart(self, user):
        cart, created = Cart.objects.get_or_create(user=user)
        return cart

    def get(self, request):
        cart = self.get_cart(request.user)

        serializer = CartSerializer(cart)

        return Response(serializer.data)


class AddToCartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        product_id = request.data.get("product_id")
        variant_id = request.data.get("variant_id")
        quantity = request.data.get("quantity", 1)

        if not product_id:
            return Response(
                {"error": "product_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            quantity = int(quantity)

            if quantity < 1:
                raise ValueError

        except (ValueError, TypeError):
            return Response(
                {"error": "quantity must be a positive number"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            product = Product.objects.get(id=product_id)

        except Product.DoesNotExist:
            return Response(
                {"error": "Product not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        variant = None

        if variant_id:
            try:
                variant = ProductVariant.objects.get(
                    id=variant_id,
                    product=product
                )

            except ProductVariant.DoesNotExist:
                return Response(
                    {"error": "Product variant not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

        else:
            if product.variants.exists():
                return Response(
                    {
                        "error": "variant_id is required for this product"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        if variant:
            if not variant.in_stock:
                return Response(
                    {"error": "This variant is out of stock"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if quantity > variant.stock_quantity:
                return Response(
                    {"error": "Not enough stock available"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        else:
            if not product.in_stock:
                return Response(
                    {"error": "Product is out of stock"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if quantity > product.stock_quantity:
                return Response(
                    {"error": "Not enough stock available"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        cart, created = Cart.objects.get_or_create(
            user=request.user
        )

        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            variant=variant,
            defaults={"quantity": quantity}
        )

        if not created:
            new_quantity = cart_item.quantity + quantity

            if variant:
                if new_quantity > variant.stock_quantity:
                    return Response(
                        {"error": "Not enough stock available"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                if new_quantity > product.stock_quantity:
                    return Response(
                        {"error": "Not enough stock available"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            cart_item.quantity = new_quantity
            cart_item.save()

        serializer = CartSerializer(cart)

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )


class UpdateCartItemView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, item_id):
        try:
            quantity = int(request.data.get("quantity"))

            if quantity < 1:
                raise ValueError

        except (ValueError, TypeError):
            return Response(
                {"error": "quantity must be a positive number"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            cart_item = CartItem.objects.select_related(
                "product",
                "variant"
            ).get(
                id=item_id,
                cart__user=request.user
            )

        except CartItem.DoesNotExist:
            return Response(
                {"error": "Cart item not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        if cart_item.variant:
            if quantity > cart_item.variant.stock_quantity:
                return Response(
                    {"error": "Not enough stock available"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            if quantity > cart_item.product.stock_quantity:
                return Response(
                    {"error": "Not enough stock available"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        cart_item.quantity = quantity
        cart_item.save()

        serializer = CartSerializer(cart_item.cart)

        return Response(serializer.data)


class RemoveFromCartView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, item_id):
        try:
            cart_item = CartItem.objects.get(
                id=item_id,
                cart__user=request.user
            )

        except CartItem.DoesNotExist:
            return Response(
                {"error": "Cart item not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        cart = cart_item.cart

        cart_item.delete()

        serializer = CartSerializer(cart)

        return Response(serializer.data)