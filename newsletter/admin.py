from django.contrib import admin

from .models import (
    NewsletterCampaign,
    NewsletterSubscriber,
)


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(
    admin.ModelAdmin
):
    list_display = (
        "email",
        "first_name",
        "last_name",
        "is_subscribed",
        "created_at",
    )

    list_filter = (
        "is_subscribed",
        "created_at",
    )

    search_fields = (
        "email",
        "first_name",
        "last_name",
    )


@admin.register(NewsletterCampaign)
class NewsletterCampaignAdmin(
    admin.ModelAdmin
):
    list_display = (
        "name",
        "subject",
        "recipients",
        "status",
        "sent_at",
        "created_at",
    )

    list_filter = (
        "status",
        "created_at",
    )

    search_fields = (
        "name",
        "subject",
    )