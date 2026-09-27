from django.urls import path

from .views import (
    NotificationListView,
    UnreadNotificationCountView,
    MarkNotificationReadView,
    MarkAllNotificationsReadView,
)



from .push_views import (

    AdminPushSubscribeView,

    AdminPushPublicKeyView,

    AdminTestPushView,

    AdminNotificationPushView,

)


urlpatterns = [
    path(
        "",
        NotificationListView.as_view(),
        name="notifications"
    ),

    path(
        "unread-count/",
        UnreadNotificationCountView.as_view(),
        name="unread-notification-count"
    ),

    path(
        "<int:notification_id>/read/",
        MarkNotificationReadView.as_view(),
        name="mark-notification-read"
    ),

    path(
        "read-all/",
        MarkAllNotificationsReadView.as_view(),
        name="mark-all-notifications-read"
    ),


    path(
    "admin/push/subscribe/",
    AdminPushSubscribeView.as_view(),
    name="admin-push-subscribe",
),

    path(
    "admin/push/public-key/",
    AdminPushPublicKeyView.as_view(),
    name="admin-push-public-key",
),

    path(
    "admin/push/test/",
    AdminTestPushView.as_view(),
    name="admin-push-test",
),

    path(
    "admin/push/send/",
    AdminNotificationPushView.as_view(),
    name="admin-push-send",
),
]