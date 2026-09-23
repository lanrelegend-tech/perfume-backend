from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework import generics
from rest_framework.throttling import UserRateThrottle
from rest_framework.permissions import (
    IsAuthenticatedOrReadOnly,
    IsAuthenticated,
    IsAdminUser,
)

from .models import Review
from .serializers import ReviewSerializer
from orders.models import OrderItem

class ReviewCreateThrottle(UserRateThrottle):
    rate = "3/hour"

class ProductReviewListView(generics.ListAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        product_id = self.kwargs["product_id"]

        return Review.objects.filter(
            product_id=product_id
        ).select_related("user")


class CreateReviewView(generics.CreateAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]
    throttle_classes = [ReviewCreateThrottle]

    def perform_create(self, serializer):
        product_id = self.kwargs["product_id"]

        has_purchased = OrderItem.objects.filter(
            order__user=self.request.user,
            order__payment_status="paid",
            product_id=product_id
        ).exists()

        if not has_purchased:
            raise PermissionDenied(
                "You can only review products you have purchased."
            )

        already_reviewed = Review.objects.filter(
            user=self.request.user,
            product_id=product_id
        ).exists()

        if already_reviewed:
            raise ValidationError({
                "detail": "You have already reviewed this product."
            })

        serializer.save(
            user=self.request.user,
            product_id=product_id
        )


class ReviewDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Review.objects.filter(
            user=self.request.user
        )


class AdminReviewListView(generics.ListAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        return Review.objects.all().select_related(
            "user",
            "product"
        ).order_by("-created_at")


class AdminReviewDeleteView(generics.DestroyAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        return Review.objects.all()