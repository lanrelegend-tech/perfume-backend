from django.conf import settings
from django.db import transaction
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import (
    AllowAny,
    IsAdminUser,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from .brevo import (
    create_brevo_campaign,
    create_brevo_contact,
    delete_brevo_campaign,
    get_brevo_campaign,
    get_brevo_campaigns,
    get_brevo_templates,
    send_brevo_campaign,
    send_brevo_test,
    unsubscribe_brevo_contact,
)

from .models import (
    NewsletterCampaign,
    NewsletterSubscriber,
)

from .serializers import (
    NewsletterCampaignSerializer,
    NewsletterSubscriberSerializer,
)


def brevo_error_response(error):
    return Response(
        {
            "error": str(error),
            "message": str(error),
        },
        status=status.HTTP_502_BAD_GATEWAY,
    )


class NewsletterSubscribeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = (
            request.data.get("email", "")
            .strip()
            .lower()
        )

        first_name = (
            request.data.get(
                "first_name",
                "",
            )
            .strip()
        )

        last_name = (
            request.data.get(
                "last_name",
                "",
            )
            .strip()
        )

        if not email:
            return Response(
                {
                    "error": "Email is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError

        try:
            validate_email(email)
        except ValidationError:
            return Response(
                {
                    "error": "Enter a valid email address."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        subscriber, created = (
            NewsletterSubscriber.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "is_subscribed": True,
                },
            )
        )

        if not created:
            subscriber.first_name = (
                first_name
                or subscriber.first_name
            )

            subscriber.last_name = (
                last_name
                or subscriber.last_name
            )

            subscriber.is_subscribed = True

            subscriber.save()

        try:
            brevo_result = create_brevo_contact(
                email=email,
                first_name=subscriber.first_name,
                last_name=subscriber.last_name,
            )

            if brevo_result.get("id"):
                subscriber.brevo_contact_id = (
                    brevo_result["id"]
                )
                subscriber.save(
                    update_fields=[
                        "brevo_contact_id",
                        "updated_at",
                    ]
                )

        except Exception as error:
            subscriber.delete()

            return brevo_error_response(error)

        return Response(
            {
                "message": (
                    "You have successfully "
                    "subscribed to the ORENTEMIST newsletter."
                ),
                "subscriber": NewsletterSubscriberSerializer(
                    subscriber
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )


class NewsletterUnsubscribeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = (
            request.data.get("email", "")
            .strip()
            .lower()
        )

        if not email:
            return Response(
                {
                    "error": "Email is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        subscriber = (
            NewsletterSubscriber.objects.filter(
                email=email
            ).first()
        )

        if subscriber:
            subscriber.is_subscribed = False
            subscriber.save(
                update_fields=[
                    "is_subscribed",
                    "updated_at",
                ]
            )

        try:
            unsubscribe_brevo_contact(
                email
            )
        except Exception as error:
            print(
                "BREVO UNSUBSCRIBE ERROR:",
                error,
            )

        return Response(
            {
                "message": (
                    "You have been unsubscribed "
                    "from the ORENTEMIST newsletter."
                )
            },
            status=status.HTTP_200_OK,
        )


class NewsletterSubscribersView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        subscribers = (
            NewsletterSubscriber.objects
            .all()
            .order_by("-created_at")
        )

        serializer = (
            NewsletterSubscriberSerializer(
                subscribers,
                many=True,
            )
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class NewsletterTemplatesView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        try:
            data = get_brevo_templates()

            return Response(
                data.get("templates", []),
                status=status.HTTP_200_OK,
            )

        except Exception as error:
            return brevo_error_response(error)


class NewsletterCampaignsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        try:
            brevo_data = get_brevo_campaigns()

            brevo_campaigns = (
                brevo_data.get(
                    "campaigns",
                    [],
                )
            )

            local_campaigns = (
                NewsletterCampaign.objects
                .all()
                .order_by("-created_at")
            )

            local_by_brevo_id = {
                campaign.brevo_campaign_id: campaign
                for campaign in local_campaigns
            }

            results = []

            for campaign in brevo_campaigns:
                campaign_id = campaign.get("id")

                local = local_by_brevo_id.get(
                    campaign_id
                )

                statistics = (
                    campaign.get(
                        "statistics",
                        {},
                    )
                    or {}
                )

                results.append(
                    {
                        "id": campaign_id,
                        "brevo_campaign_id": campaign_id,
                        "name": campaign.get(
                            "name",
                            "",
                        ),
                        "subject": campaign.get(
                            "subject",
                            "",
                        ),
                        "preview": campaign.get(
                            "previewText",
                            "",
                        ),
                        "template_id": (
                            local.template_id
                            if local
                            else campaign.get(
                                "templateId"
                            )
                        ),
                        "sender_name": (
                            local.sender_name
                            if local
                            else (
                                campaign.get(
                                    "sender",
                                    {},
                                )
                                or {}
                            ).get(
                                "name",
                                "",
                            )
                        ),
                        "sender_email": (
                            local.sender_email
                            if local
                            else (
                                campaign.get(
                                    "sender",
                                    {},
                                )
                                or {}
                            ).get(
                                "email",
                                "",
                            )
                        ),
                        "recipients": (
                            campaign.get(
                                "recipients",
                                {},
                            )
                            or {}
                        ).get(
                            "recipients",
                            (
                                local.recipients
                                if local
                                else 0
                            ),
                        ),
                        "status": campaign.get(
                            "status",
                            "draft",
                        ),
                        "opened": (
                            f"{statistics.get('openRate', 0)}%"
                            if statistics.get(
                                "openRate"
                            ) is not None
                            else "—"
                        ),
                        "openedRate": (
                            f"{statistics.get('openRate', 0)}%"
                            if statistics.get(
                                "openRate"
                            ) is not None
                            else "—"
                        ),
                        "clicked": (
                            f"{statistics.get('clickRate', 0)}%"
                            if statistics.get(
                                "clickRate"
                            ) is not None
                            else "—"
                        ),
                        "clickRate": (
                            f"{statistics.get('clickRate', 0)}%"
                            if statistics.get(
                                "clickRate"
                            ) is not None
                            else "—"
                        ),
                        "sentAt": campaign.get(
                            "scheduledAt"
                        )
                        or campaign.get(
                            "createdAt"
                        ),
                        "created_at": campaign.get(
                            "createdAt"
                        ),
                    }
                )

            return Response(
                results,
                status=status.HTTP_200_OK,
            )

        except Exception as error:
            return brevo_error_response(error)

    def post(self, request):
        name = (
            request.data.get(
                "name",
                "",
            )
            .strip()
        )

        subject = (
            request.data.get(
                "subject",
                "",
            )
            .strip()
        )

        preview = (
            request.data.get(
                "preview",
                "",
            )
            .strip()
        )

        template_id = request.data.get(
            "template_id"
        )

        sender_name = (
            request.data.get(
                "sender_name"
            )
            or settings.BREVO_DEFAULT_SENDER_NAME
        ).strip()

        sender_email = (
            request.data.get(
                "sender_email"
            )
            or settings.BREVO_DEFAULT_SENDER_EMAIL
        ).strip()

        if not name:
            return Response(
                {
                    "error": "Campaign name is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not subject:
            return Response(
                {
                    "error": "Subject is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not template_id:
            return Response(
                {
                    "error": "Template is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        subscriber_count = (
            NewsletterSubscriber.objects
            .filter(
                is_subscribed=True
            )
            .count()
        )

        if subscriber_count == 0:
            return Response(
                {
                    "error": (
                        "There are no active "
                        "newsletter subscribers."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            template_id = int(
                template_id
            )
        except (
            TypeError,
            ValueError,
        ):
            return Response(
                {
                    "error": "Invalid template ID."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            campaign_data = (
                create_brevo_campaign(
                    name=name,
                    subject=subject,
                    preview=preview,
                    template_id=template_id,
                    sender_name=sender_name,
                    sender_email=sender_email,
                )
            )

            brevo_campaign_id = (
                campaign_data.get("id")
            )

            if not brevo_campaign_id:
                raise RuntimeError(
                    "Brevo did not return a campaign ID."
                )

            local_campaign = (
                NewsletterCampaign.objects.create(
                    brevo_campaign_id=brevo_campaign_id,
                    name=name,
                    subject=subject,
                    preview=preview,
                    template_id=template_id,
                    sender_name=sender_name,
                    sender_email=sender_email,
                    recipients=subscriber_count,
                    status="draft",
                )
            )

            try:
                send_brevo_campaign(
                    brevo_campaign_id
                )
            except Exception:
                local_campaign.status = (
                    "failed"
                )
                local_campaign.save(
                    update_fields=[
                        "status",
                        "updated_at",
                    ]
                )
                raise

            local_campaign.status = "sent"
            local_campaign.sent_at = timezone.now()

            local_campaign.save(
                update_fields=[
                    "status",
                    "sent_at",
                    "updated_at",
                ]
            )

            return Response(
                {
                    "message": (
                        "Newsletter campaign "
                        "sent successfully."
                    ),
                    "campaign": (
                        NewsletterCampaignSerializer(
                            local_campaign
                        ).data
                    ),
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as error:
            return brevo_error_response(error)


class NewsletterCampaignTestView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        email = (
            request.data.get(
                "email",
                "",
            )
            .strip()
            .lower()
        )

        template_id = request.data.get(
            "template_id"
        )

        subject = (
            request.data.get(
                "subject",
                "",
            )
            .strip()
        )

        preview = (
            request.data.get(
                "preview",
                "",
            )
            .strip()
        )

        if not email:
            return Response(
                {
                    "error": (
                        "Test email is required."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not template_id:
            return Response(
                {
                    "error": (
                        "Template is required."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            template_id = int(
                template_id
            )
        except (
            TypeError,
            ValueError,
        ):
            return Response(
                {
                    "error": "Invalid template ID."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        temporary_campaign_id = None

        try:
            temporary_campaign = (
                create_brevo_campaign(
                    name=(
                        f"ORENTEMIST TEST - "
                        f"{timezone.now().strftime('%Y%m%d%H%M%S')}"
                    ),
                    subject=(
                        subject
                        or "ORENTEMIST Newsletter Test"
                    ),
                    preview=preview,
                    template_id=template_id,
                    sender_name=(
                        settings.BREVO_DEFAULT_SENDER_NAME
                    ),
                    sender_email=(
                        settings.BREVO_DEFAULT_SENDER_EMAIL
                    ),
                )
            )

            temporary_campaign_id = (
                temporary_campaign.get("id")
            )

            if not temporary_campaign_id:
                raise RuntimeError(
                    "Brevo did not return a test campaign ID."
                )

            send_brevo_test(
                temporary_campaign_id,
                email,
            )

            try:
                delete_brevo_campaign(
                    temporary_campaign_id
                )
            except Exception as cleanup_error:
                print(
                    "BREVO TEST CLEANUP ERROR:",
                    cleanup_error,
                )

            return Response(
                {
                    "message": (
                        "Test newsletter sent successfully."
                    )
                },
                status=status.HTTP_200_OK,
            )

        except Exception as error:
            if temporary_campaign_id:
                try:
                    delete_brevo_campaign(
                        temporary_campaign_id
                    )
                except Exception:
                    pass

            return brevo_error_response(error)


class NewsletterCampaignRefreshView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        campaign = (
            NewsletterCampaign.objects.filter(
                brevo_campaign_id=pk
            ).first()
        )

        try:
            data = get_brevo_campaign(pk)

            statistics = (
                data.get(
                    "statistics",
                    {},
                )
                or {}
            )

            if campaign:
                campaign.status = data.get(
                    "status",
                    campaign.status,
                )

                campaign.opened_rate = (
                    f"{statistics.get('openRate', 0)}%"
                )

                campaign.click_rate = (
                    f"{statistics.get('clickRate', 0)}%"
                )

                campaign.save(
                    update_fields=[
                        "status",
                        "opened_rate",
                        "click_rate",
                        "updated_at",
                    ]
                )

            return Response(
                data,
                status=status.HTTP_200_OK,
            )

        except Exception as error:
            return brevo_error_response(error)