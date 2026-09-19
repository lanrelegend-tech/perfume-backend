from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from products.models import Product
from .models import Wishlist
from .serializers import WishlistSerializer


class WishlistView(APIView):
    permission_classes = [IsAuthenticated]

    def get_wishlist(self, user):
        wishlist, created = Wishlist.objects.get_or_create(
            user=user
        )
        return wishlist

    def get(self, request):
        wishlist = self.get_wishlist(request.user)

        serializer = WishlistSerializer(
            wishlist,
            context={"request": request}
        )

        return Response(serializer.data)


class AddToWishlistView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        product_id = request.data.get("product_id")

        if not product_id:
            return Response(
                {"error": "product_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            product = Product.objects.get(id=product_id)

        except Product.DoesNotExist:
            return Response(
                {"error": "Product not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        wishlist, created = Wishlist.objects.get_or_create(
            user=request.user
        )

        if wishlist.products.filter(id=product.id).exists():
            return Response(
                {"message": "Product is already in your wishlist"},
                status=status.HTTP_400_BAD_REQUEST
            )

        wishlist.products.add(product)

        serializer = WishlistSerializer(
            wishlist,
            context={"request": request}
        )

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )


class RemoveFromWishlistView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, product_id):
        wishlist, created = Wishlist.objects.get_or_create(
            user=request.user
        )

        product = wishlist.products.filter(
            id=product_id
        ).first()

        if not product:
            return Response(
                {"error": "Product is not in your wishlist"},
                status=status.HTTP_404_NOT_FOUND
            )

        wishlist.products.remove(product)

        serializer = WishlistSerializer(
            wishlist,
            context={"request": request}
        )

        return Response(serializer.data)