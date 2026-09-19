from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAdminUser

from .models import StoreSettings
from .serializers import StoreSettingsSerializer


class StoreSettingsView(generics.RetrieveAPIView):
    serializer_class = StoreSettingsSerializer
    permission_classes = [AllowAny]

    def get_object(self):
        settings, created = StoreSettings.objects.get_or_create(
            pk=1
        )

        return settings


class AdminStoreSettingsView(generics.RetrieveUpdateAPIView):
    serializer_class = StoreSettingsSerializer
    permission_classes = [IsAdminUser]

    def get_object(self):
        settings, created = StoreSettings.objects.get_or_create(
            pk=1
        )

        return settings