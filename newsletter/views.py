from django.conf import settings
from django.utils import timezone
from django.utils.html import escape

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .brevo import (
    create_brevo_contact,
    create_brevo_html_campaign,
    get_brevo_campaign,
    get_brevo_campaigns,
    send_brevo_draft_campaign,
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


def build_newsletter_html(
    hero_image="",
    heading="",
    body="",
    button_text="",
    button_url="",
):
    safe_hero_image = escape(hero_image or "")
    safe_heading = escape(heading or "")
    safe_button_text = escape(button_text or "")
    safe_button_url = escape(button_url or "")

    body_lines = (body or "").splitlines()

    safe_body = "<br>".join(
        escape(line)
        for line in body_lines
    )

    hero_html = ""

    if safe_hero_image:
        hero_html = f"""
        <tr>
            <td
                style="
                    padding:0;
                    margin:0;
                "
            >
                <img
                    src="{safe_hero_image}"
                    alt="ORENTEMIST"
                    width="600"
                    style="
                        display:block;
                        width:100%;
                        max-width:600px;
                        height:auto;
                        border:0;
                        margin:0;
                    "
                />
            </td>
        </tr>
        """

    button_html = ""

    if safe_button_text and safe_button_url:
        button_html = f"""
        <tr>
            <td
                align="center"
                style="
                    padding:10px 40px 40px 40px;
                "
            >
                <a
                    href="{safe_button_url}"
                    style="
                        display:inline-block;
                        background:#000000;
                        color:#ffffff;
                        text-decoration:none;
                        padding:14px 28px;
                        border-radius:8px;
                        font-family:Arial,Helvetica,sans-serif;
                        font-size:14px;
                        font-weight:600;
                    "
                >
                    {safe_button_text}
                </a>
            </td>
        </tr>
        """

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >
    <title>ORENTEMIST</title>
</head>

<body
    style="
        margin:0;
        padding:0;
        background:#f5f5f5;
    "
>
    <table
        width="100%"
        cellpadding="0"
        cellspacing="0"
        border="0"
        style="
            width:100%;
            margin:0;
            padding:0;
            background:#f5f5f5;
        "
    >
        <tr>
            <td
                align="center"
                style="
                    padding:30px 15px;
                "
            >
                <table
                    width="600"
                    cellpadding="0"
                    cellspacing="0"
                    border="0"
                    style="
                        width:100%;
                        max-width:600px;
                        background:#ffffff;
                        margin:0 auto;
                    "
                >

                    <tr>
                        <td
                            align="center"
                            style="
                                padding:30px 30px 20px 30px;
                                font-family:Arial,Helvetica,sans-serif;
                            "
                        >
                            <div
                                style="
                                    font-size:20px;
                                    font-weight:700;
                                    letter-spacing:4px;
                                    color:#000000;
                                "
                            >
                                ORENTEMIST
                            </div>
                        </td>
                    </tr>

                    {hero_html}

                    <tr>
                        <td
                            style="
                                padding:40px 40px 20px 40px;
                                font-family:Arial,Helvetica,sans-serif;
                            "
                        >
                            <h1
                                style="
                                    margin:0;
                                    color:#000000;
                                    font-size:30px;
                                    line-height:1.25;
                                    font-weight:700;
                                "
                            >
                                {safe_heading}
                            </h1>
                        </td>
                    </tr>

                    <tr>
                        <td
                            style="
                                padding:0 40px 30px 40px;
                                font-family:Arial,Helvetica,sans-serif;
                            "
                        >
                            <div
                                style="
                                    color:#444444;
                                    font-size:16px;
                                    line-height:1.8;
                                "
                            >
                                {safe_body}
                            </div>
                        </td>
                    </tr>

                    {button_html}

                    <tr>
                        <td
                            align="center"
                            style="
                                padding:30px 40px;
                                border-top:1px solid #eeeeee;
                                font-family:Arial,Helvetica,sans-serif;
                            "
                        >
                            <p
                                style="
                                    margin:0;
                                    color:#999999;
                                    font-size:12px;
                                    line-height:1.6;
                                "
                            >
                                You are receiving this email because
                                you subscribed to the ORENTEMIST newsletter.
                            </p>

                            <p
                                style="
                                    margin:10px 0 0 0;
                                    color:#999999;
                                    font-size:12px;
                                "
                            >
                                ORENTEMIST
                            </p>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""


class NewsletterSubscribeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = (
            request.data.get("email", "")
            .strip()
            .lower()
        )

        first_name = (
            request.data.get("first_name", "")
            .strip()
        )

        last_name = (
            request.data.get("last_name", "")
            .strip()
        )

        if not email:
            return Response(
                {"error": "Email is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError

        try:
            validate_email(email)
        except ValidationError:
            return Response(
                {
                    "error": (
                        "Enter a valid email address."
                    )
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
                    "You have successfully subscribed "
                    "to the ORENTEMIST newsletter."
                ),
                "subscriber": (
                    NewsletterSubscriberSerializer(
                        subscriber
                    ).data
                ),
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
                {"error": "Email is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subscriber = (
            NewsletterSubscriber.objects
            .filter(email=email)
            .first()
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
            unsubscribe_brevo_contact(email)

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

        serializer = NewsletterSubscriberSerializer(
            subscribers,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class NewsletterTemplatesView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        """
        Kept for compatibility with the existing frontend.

        The new newsletter builder does not require
        Brevo templates anymore.
        """

        return Response(
            {
                "templates": []
            },
            status=status.HTTP_200_OK,
        )


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
                if campaign.brevo_campaign_id
            }

            results = []

            seen_ids = set()

            for campaign in brevo_campaigns:
                campaign_id = campaign.get("id")

                if not campaign_id:
                    continue

                seen_ids.add(campaign_id)

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

                recipients_data = (
                    campaign.get(
                        "recipients",
                        {},
                    )
                    or {}
                )

                sender_data = (
                    campaign.get(
                        "sender",
                        {},
                    )
                    or {}
                )

                results.append(
                    {
                        "id": campaign_id,

                        "brevo_campaign_id": campaign_id,

                        "name": (
                            campaign.get(
                                "name",
                                "",
                            )
                            or (
                                local.name
                                if local
                                else ""
                            )
                        ),

                        "subject": (
                            campaign.get(
                                "subject",
                                "",
                            )
                            or (
                                local.subject
                                if local
                                else ""
                            )
                        ),

                        "preview": (
                            campaign.get(
                                "previewText",
                                "",
                            )
                            or (
                                local.preview
                                if local
                                else ""
                            )
                        ),

                        "template_id": (
                            local.template_id
                            if local
                            else None
                        ),

                        "sender_name": (
                            sender_data.get(
                                "name",
                                "",
                            )
                            or (
                                local.sender_name
                                if local
                                else ""
                            )
                        ),

                        "sender_email": (
                            sender_data.get(
                                "email",
                                "",
                            )
                            or (
                                local.sender_email
                                if local
                                else ""
                            )
                        ),

                        "recipients": (
                            recipients_data.get(
                                "recipients",
                                (
                                    local.recipients
                                    if local
                                    else 0
                                ),
                            )
                        ),

                        "status": (
                            campaign.get(
                                "status",
                                "draft",
                            )
                            or (
                                local.status
                                if local
                                else "draft"
                            )
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

                        "sentAt": (
                            campaign.get(
                                "scheduledAt"
                            )
                            or (
                                local.sent_at
                                if local
                                and local.sent_at
                                else None
                            )
                            or campaign.get(
                                "createdAt"
                            )
                        ),

                        "created_at": (
                            campaign.get(
                                "createdAt"
                            )
                            or (
                                local.created_at
                                if local
                                else None
                            )
                        ),

                        "hero_image": (
                            local.hero_image
                            if local
                            else ""
                        ),

                        "heading": (
                            local.heading
                            if local
                            else ""
                        ),

                        "body": (
                            local.body
                            if local
                            else ""
                        ),

                        "button_text": (
                            local.button_text
                            if local
                            else ""
                        ),

                        "button_url": (
                            local.button_url
                            if local
                            else ""
                        ),
                    }
                )

            # Include local drafts that Brevo did not return.
            for local in local_campaigns:
                if (
                    local.brevo_campaign_id
                    and local.brevo_campaign_id
                    in seen_ids
                ):
                    continue

                results.append(
                    {
                        "id": local.id,

                        "brevo_campaign_id": (
                            local.brevo_campaign_id
                        ),

                        "name": local.name,

                        "subject": local.subject,

                        "preview": local.preview,

                        "template_id": (
                            local.template_id
                        ),

                        "sender_name": (
                            local.sender_name
                        ),

                        "sender_email": (
                            local.sender_email
                        ),

                        "recipients": (
                            local.recipients
                        ),

                        "status": local.status,

                        "opened": (
                            local.opened_rate
                            or "—"
                        ),

                        "openedRate": (
                            local.opened_rate
                            or "—"
                        ),

                        "clicked": (
                            local.click_rate
                            or "—"
                        ),

                        "clickRate": (
                            local.click_rate
                            or "—"
                        ),

                        "sentAt": (
                            local.sent_at
                        ),

                        "created_at": (
                            local.created_at
                        ),

                        "hero_image": (
                            local.hero_image
                        ),

                        "heading": (
                            local.heading
                        ),

                        "body": (
                            local.body
                        ),

                        "button_text": (
                            local.button_text
                        ),

                        "button_url": (
                            local.button_url
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
        """
        Create a newsletter directly from the ORENTEMIST builder.

        This creates the campaign in Brevo as a DRAFT.
        It does NOT send it immediately.
        """

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

        hero_image = (
            request.data.get(
                "hero_image",
                "",
            )
            .strip()
        )

        heading = (
            request.data.get(
                "heading",
                "",
            )
            .strip()
        )

        body = (
            request.data.get(
                "body",
                "",
            )
            .strip()
        )

        button_text = (
            request.data.get(
                "button_text",
                "",
            )
            .strip()
        )

        button_url = (
            request.data.get(
                "button_url",
                "",
            )
            .strip()
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
                    "error": (
                        "Newsletter name is required."
                    )
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

        if not heading:
            return Response(
                {
                    "error": "Heading is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not body:
            return Response(
                {
                    "error": (
                        "Newsletter body is required."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if button_text and not button_url:
            return Response(
                {
                    "error": (
                        "Button URL is required "
                        "when button text is provided."
                    )
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

        html_content = build_newsletter_html(
            hero_image=hero_image,
            heading=heading,
            body=body,
            button_text=button_text,
            button_url=button_url,
        )

        try:
            campaign_data = create_brevo_html_campaign(
                name=name,
                subject=subject,
                preview=preview,
                html_content=html_content,
                sender_name=sender_name,
                sender_email=sender_email,
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

                    template_id=None,

                    sender_name=sender_name,

                    sender_email=sender_email,

                    recipients=subscriber_count,

                    status="draft",

                    hero_image=hero_image,

                    heading=heading,

                    body=body,

                    button_text=button_text,

                    button_url=button_url,
                )
            )

            return Response(
                {
                    "message": (
                        "Newsletter draft created successfully."
                    ),

                    "campaign": (
                        NewsletterCampaignSerializer(
                            local_campaign
                        ).data
                    ),

                    "brevo_campaign_id": (
                        brevo_campaign_id
                    ),

                    "html_content": html_content,
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as error:
            return brevo_error_response(error)


class NewsletterCampaignSendDraftView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        """
        Send an existing Brevo draft campaign.
        """

        campaign = (
            NewsletterCampaign.objects
            .filter(
                brevo_campaign_id=pk
            )
            .first()
        )

        if not campaign:
            return Response(
                {
                    "error": (
                        "Newsletter campaign was not found."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if campaign.status.lower() == "sent":
            return Response(
                {
                    "error": (
                        "This newsletter has already been sent."
                    )
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
            result = send_brevo_draft_campaign(
                pk
            )

            campaign.recipients = subscriber_count

            campaign.status = "sent"

            campaign.sent_at = timezone.now()

            campaign.save(
                update_fields=[
                    "recipients",
                    "status",
                    "sent_at",
                    "updated_at",
                ]
            )

            return Response(
                {
                    "message": (
                        "Newsletter sent successfully."
                    ),

                    "campaign": (
                        NewsletterCampaignSerializer(
                            campaign
                        ).data
                    ),

                    "brevo": result,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as error:
            campaign.status = "failed"

            campaign.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

            return brevo_error_response(error)


class NewsletterCampaignTestView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        """
        Send a test email from an existing Brevo draft.
        """

        email = (
            request.data.get(
                "email",
                "",
            )
            .strip()
            .lower()
        )

        campaign_id = request.data.get(
            "campaign_id"
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

        if not campaign_id:
            return Response(
                {
                    "error": (
                        "Campaign ID is required."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            campaign_id = int(
                campaign_id
            )

        except (
            TypeError,
            ValueError,
        ):
            return Response(
                {
                    "error": (
                        "Invalid campaign ID."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        campaign = (
            NewsletterCampaign.objects
            .filter(
                brevo_campaign_id=campaign_id
            )
            .first()
        )

        if not campaign:
            return Response(
                {
                    "error": (
                        "Newsletter campaign was not found."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            result = send_brevo_test(
                campaign_id,
                email,
            )

            return Response(
                {
                    "message": (
                        "Test newsletter sent successfully."
                    ),
                    "email": email,
                    "campaign_id": campaign_id,
                    "brevo": result,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as error:
            return brevo_error_response(error)


class NewsletterCampaignRefreshView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        campaign = (
            NewsletterCampaign.objects
            .filter(
                brevo_campaign_id=pk
            )
            .first()
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