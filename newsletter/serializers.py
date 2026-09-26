from rest_framework import serializers

from .models import (
    NewsletterSubscriber,
    NewsletterCampaign,
)


class NewsletterSubscriberSerializer(
    serializers.ModelSerializer
):
    name = serializers.SerializerMethodField()

    status = serializers.SerializerMethodField()

    joined = serializers.DateTimeField(
        source="created_at",
        read_only=True,
    )

    class Meta:
        model = NewsletterSubscriber
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "name",
            "status",
            "is_subscribed",
            "created_at",
            "joined",
            "updated_at",
        ]

    def get_name(self, obj):
        full_name = (
            f"{obj.first_name} {obj.last_name}"
        ).strip()

        return (
            full_name
            or obj.email
        )

    def get_status(self, obj):
        return (
            "Subscribed"
            if obj.is_subscribed
            else "Unsubscribed"
        )


class NewsletterCampaignSerializer(
    serializers.ModelSerializer
):
    recipientsCount = serializers.IntegerField(
        source="recipients",
        read_only=True,
    )

    sentAt = serializers.DateTimeField(
        source="sent_at",
        read_only=True,
    )

    openedRate = serializers.CharField(
        source="opened_rate",
        read_only=True,
    )

    clickRate = serializers.CharField(
        source="click_rate",
        read_only=True,
    )

    class Meta:
        model = NewsletterCampaign
        fields = [
            "id",
            "brevo_campaign_id",
            "name",
            "subject",
            "preview",
            "template_id",
            "sender_name",
            "sender_email",
            "recipients",
            "recipientsCount",
            "status",
            "opened_rate",
            "openedRate",
            "click_rate",
            "clickRate",
            "sent_at",
            "sentAt",
            "created_at",
            "updated_at",
        ]