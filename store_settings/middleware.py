from django.http import JsonResponse

from .models import StoreSettings


class MaintenanceModeMiddleware:
    """
    Block public API traffic while maintenance mode is enabled.

    Admin, auth, settings, static media, and admin-only operational
    endpoints stay reachable so staff can sign in and turn maintenance
    mode back off.
    """

    ALLOWED_PREFIXES = (
        "/admin/",
        "/api/auth/",
        "/api/settings/",
        "/api/users/me/",
        "/api/users/admin/",
        "/api/products/admin/",
        "/api/orders/admin/",
        "/api/reviews/admin/",
        "/api/coupons/admin/",
        "/api/notifications/admin/",
        "/api/newsletter/subscribers/",
        "/api/newsletter/templates/",
        "/api/newsletter/audience/",
        "/api/newsletter/campaigns/",
        "/api/newsletter/upload-image/",
        "/static/",
        "/media/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._should_block(request):
            return JsonResponse(
                {
                    "detail": (
                        "The store is temporarily unavailable "
                        "for maintenance. Please check back soon."
                    ),
                    "code": "maintenance_mode",
                },
                status=503,
            )

        return self.get_response(request)

    def _should_block(self, request):
        path = request.path_info or ""

        if not path.startswith("/api/"):
            return False

        if any(path.startswith(prefix) for prefix in self.ALLOWED_PREFIXES):
            return False

        try:
            settings = StoreSettings.objects.only(
                "maintenance_mode"
            ).first()
        except Exception:
            return False

        return bool(settings and settings.maintenance_mode)
