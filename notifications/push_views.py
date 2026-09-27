import json

from django.conf import settings
from django.db import transaction

from pywebpush import webpush, WebPushException

from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AdminPushSubscription, Notification



def send_admin_push_notification(
    title,
    message,
    url="/admin",
    notification_type="system",
    tag=None,
):
    """
    Send a Web Push notification to every active admin
    subscription and create an in-app Notification for
    every admin user.
    """

    subscriptions = (
        AdminPushSubscription.objects
        .select_related("user")
        .filter(
            user__is_staff=True,
            is_active=True,
        )
    )

    admin_users = {}

    for subscription in subscriptions:
        admin_users[subscription.user_id] = subscription.user

    for admin_user in admin_users.values():
        Notification.objects.create(
            user=admin_user,
            title=title,
            message=message,
            notification_type=notification_type,
        )

    payload = {
        "title": title,
        "body": message,
        "url": url,
        "tag": tag or f"orentemist-{notification_type}",
        "icon": "https://www.orentemist.online/icons/icon-192x192.png",
        "badge": "https://www.orentemist.online/icons/icon-192x192.png",
    
    }

    sent = 0
    removed = 0

    for subscription in subscriptions:
        subscription_info = {
            "endpoint": subscription.endpoint,
            "keys": {
                "p256dh": subscription.p256dh,
                "auth": subscription.auth,
            },
        }

        try:
            webpush(
                subscription_info=subscription_info,
                data=json.dumps(payload),
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={
                    "sub": settings.VAPID_CLAIMS_EMAIL,
                },
                ttl=60 * 60,
            )

            sent += 1

        except WebPushException as exc:
            response = getattr(exc, "response", None)
            status_code = getattr(
                response,
                "status_code",
                None,
            )

            if status_code in [404, 410]:
                subscription.is_active = False

                subscription.save(
                    update_fields=[
                        "is_active",
                    ]
                )

                removed += 1

            print(
                "WEB PUSH ERROR:",
                repr(exc),
            )

    print(
        "ADMIN PUSH RESULT:",
        {
            "sent": sent,
            "removed": removed,
            "admins": len(admin_users),
        },
    )

    
class AdminPushSubscribeView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        endpoint = request.data.get("endpoint")
        keys = request.data.get("keys") or {}

        p256dh = keys.get("p256dh")
        auth = keys.get("auth")

        if not endpoint or not p256dh or not auth:
            return Response(
                {
                    "detail": "Invalid push subscription."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        subscription, created = (
            AdminPushSubscription.objects.update_or_create(
                endpoint=endpoint,
                defaults={
                    "user": request.user,
                    "p256dh": p256dh,
                    "auth": auth,
                    "is_active": True,
                },
            )
        )

        return Response(
            {
                "success": True,
                "created": created,
                "message": "Push notifications enabled.",
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request):
        endpoint = request.data.get("endpoint")

        if not endpoint:
            return Response(
                {
                    "detail": "Endpoint is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        AdminPushSubscription.objects.filter(
            endpoint=endpoint,
            user=request.user,
        ).update(
            is_active=False
        )

        return Response(
            {
                "success": True,
                "message": "Push notifications disabled.",
            }
        )


class AdminPushPublicKeyView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response(
            {
                "public_key": settings.VAPID_PUBLIC_KEY
            }
        )


class AdminTestPushView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        title = request.data.get(
            "title",
            "ORENTEMIST",
        )

        message = request.data.get(
            "message",
            "Push notifications are working.",
        )

        url = request.data.get(
            "url",
            "/admin",
        )

        payload = {
            "title": title,
            "body": message,
            "url": url,
            "tag": "orentemist-admin-test",
            "icon": "https://www.orentemist.online/icons/icon-192x192.png",
            "badge": "https://www.orentemist.online/icons/icon-192x192.png",
        }

        subscriptions = (
            AdminPushSubscription.objects.filter(
                user=request.user,
                is_active=True,
            )
        )

        sent = 0
        removed = 0

        for subscription in subscriptions:
            subscription_info = {
                "endpoint": subscription.endpoint,
                "keys": {
                    "p256dh": subscription.p256dh,
                    "auth": subscription.auth,
                },
            }

            try:
                webpush(
                    subscription_info=subscription_info,
                    data=json.dumps(payload),
                    vapid_private_key=settings.VAPID_PRIVATE_KEY,
                    vapid_claims={
                        "sub": settings.VAPID_CLAIMS_EMAIL,
                    },
                    ttl=60 * 60,
                )

                sent += 1

            except WebPushException as exc:
                response = getattr(
                    exc,
                    "response",
                    None,
                )

                status_code = getattr(
                    response,
                    "status_code",
                    None,
                )

                if status_code in [404, 410]:
                    subscription.is_active = False
                    subscription.save(
                        update_fields=["is_active"]
                    )
                    removed += 1

                print(
                    "Web Push failed:",
                    exc,
                )

        return Response(
            {
                "success": True,
                "sent": sent,
                "removed": removed,
            }
        )


class AdminNotificationPushView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        title = request.data.get(
            "title",
            "ORENTEMIST",
        )

        message = request.data.get(
            "message",
            "",
        )

        notification_type = request.data.get(
            "notification_type",
            "system",
        )

        url = request.data.get(
            "url",
            "/admin",
        )

        if not message:
            return Response(
                {
                    "detail": "Message is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        notification = Notification.objects.create(
            user=request.user,
            title=title,
            message=message,
            notification_type=notification_type,
        )

        payload = {
            "title": title,
            "body": message,
            "url": url,
            "notification_id": notification.id,
            "tag": f"orentemist-{notification_type}",
            "icon": "https://www.orentemist.online/icons/icon-192x192.png",
            "badge": "https://www.orentemist.online/icons/icon-192x192.png",  
        }

        subscriptions = (
            AdminPushSubscription.objects.filter(
                user=request.user,
                is_active=True,
            )
        )

        sent = 0

        for subscription in subscriptions:
            subscription_info = {
                "endpoint": subscription.endpoint,
                "keys": {
                    "p256dh": subscription.p256dh,
                    "auth": subscription.auth,
                },
            }

            try:
                webpush(
                    subscription_info=subscription_info,
                    data=json.dumps(payload),
                    vapid_private_key=settings.VAPID_PRIVATE_KEY,
                    vapid_claims={
                        "sub": settings.VAPID_CLAIMS_EMAIL,
                    },
                    ttl=60 * 60,
                )

                sent += 1

            except WebPushException as exc:
                response = getattr(
                    exc,
                    "response",
                    None,
                )

                status_code = getattr(
                    response,
                    "status_code",
                    None,
                )

                if status_code in [404, 410]:
                    subscription.is_active = False
                    subscription.save(
                        update_fields=["is_active"]
                    )

                print(
                    "Web Push failed:",
                    exc,
                )

        return Response(
            {
                "success": True,
                "notification_id": notification.id,
                "sent": sent,
            },
            status=status.HTTP_201_CREATED,
        )