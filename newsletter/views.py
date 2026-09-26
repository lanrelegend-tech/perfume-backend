from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone
from django.utils.html import escape

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Order

from .brevo import (
    add_brevo_contacts_to_list,
    create_brevo_contact,
    create_brevo_html_campaign,
    create_brevo_list,
    delete_brevo_list,
    get_brevo_campaign,
    get_brevo_campaigns,
    get_brevo_list,
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


# ============================================================
# HELPERS
# ============================================================

def brevo_error_response(error):
    return Response(
        {
            "error": str(error),
            "message": str(error),
        },
        status=status.HTTP_502_BAD_GATEWAY,
    )


def normalize_email(email):
    return (
        str(email or "")
        .strip()
        .lower()
    )


def clean_email_set(emails):
    return {
        normalize_email(email)
        for email in emails
        if normalize_email(email)
    }


def get_active_subscriber_emails():
    return clean_email_set(
        NewsletterSubscriber.objects
        .filter(
            is_subscribed=True
        )
        .values_list(
            "email",
            flat=True,
        )
    )


def get_registered_user_emails():
    return clean_email_set(
        User.objects
        .exclude(
            email=""
        )
        .values_list(
            "email",
            flat=True,
        )
    )


def get_customer_emails():
    return clean_email_set(
        Order.objects
        .filter(
            payment_status="paid"
        )
        .exclude(
            email=""
        )
        .values_list(
            "email",
            flat=True,
        )
    )


def get_audience_emails(
    include,
    selected_subscriber_ids=None,
    exclude_emails=None,
):
    """
    Marketing-consent rule:

    Only active NewsletterSubscriber contacts are eligible
    for promotional campaigns.

    Registered users and customers are therefore filters
    inside the consented newsletter population.
    """

    active_subscribers = (
        get_active_subscriber_emails()
    )

    registered_users = (
        get_registered_user_emails()
    )

    customers = (
        get_customer_emails()
    )

    include = set(
        include or []
    )

    selected_subscriber_ids = (
        selected_subscriber_ids or []
    )

    exclude_emails = clean_email_set(
        exclude_emails or []
    )

    if "selected" in include:
        selected_ids = set()

        for value in selected_subscriber_ids:
            try:
                selected_ids.add(
                    int(value)
                )
            except (
                TypeError,
                ValueError,
            ):
                continue

        selected_emails = clean_email_set(
            NewsletterSubscriber.objects
            .filter(
                id__in=selected_ids,
                is_subscribed=True,
            )
            .values_list(
                "email",
                flat=True,
            )
        )

        audience = selected_emails

    else:
        audience = set()

        if "subscribers" in include:
            audience.update(
                active_subscribers
            )

        if "users" in include:
            audience.update(
                active_subscribers
                & registered_users
            )

        if "customers" in include:
            audience.update(
                active_subscribers
                & customers
            )

        if "everyone" in include:
            audience.update(
                active_subscribers
            )

    before_exclusion = set(
        audience
    )

    audience -= exclude_emails

    return {
        "emails": audience,
        "excluded_count": (
            len(before_exclusion)
            - len(audience)
        ),
        "available": {
            "subscribers": len(
                active_subscribers
            ),
            "users": len(
                active_subscribers
                & registered_users
            ),
            "customers": len(
                active_subscribers
                & customers
            ),
            "everyone": len(
                active_subscribers
            ),
        },
    }


def get_folder_id_for_newsletter_list():
    """
    Use the folder containing the existing
    BREVO_LIST_ID so campaign-specific lists
    are kept alongside the newsletter list.
    """

    configured_list_id = (
        settings.BREVO_LIST_ID
    )

    if not configured_list_id:
        raise RuntimeError(
            "BREVO_LIST_ID is not configured."
        )

    list_data = get_brevo_list(
        int(configured_list_id)
    )

    folder_id = list_data.get(
        "folderId"
    )

    if not folder_id:
        raise RuntimeError(
            "Unable to determine the Brevo folder for the newsletter list."
        )

    return int(folder_id)


def create_campaign_recipient_list(
    campaign_name,
    emails,
):
    """
    Creates a dedicated Brevo list containing the
    exact recipients for this campaign.

    This gives every campaign its own recipient snapshot.
    """

    if not emails:
        raise RuntimeError(
            "Cannot create a recipient list with zero recipients."
        )

    folder_id = (
        get_folder_id_for_newsletter_list()
    )

    safe_name = (
        str(campaign_name)
        .strip()
        .replace(
            "\n",
            " ",
        )
        .replace(
            "\r",
            " ",
        )
    )

    if len(safe_name) > 150:
        safe_name = safe_name[:150]

    list_data = create_brevo_list(
        name=(
            f"ORENTEMIST Campaign - "
            f"{safe_name}"
        ),
        folder_id=folder_id,
    )

    list_id = list_data.get(
        "id"
    )

    if not list_id:
        raise RuntimeError(
            "Brevo did not return the new recipient list ID."
        )

    result = add_brevo_contacts_to_list(
        list_id=list_id,
        emails=emails,
    )

    failed = result.get(
        "failure",
        [],
    )

    if failed:
        delete_brevo_list(
            list_id
        )

        raise RuntimeError(
            "Brevo could not add all campaign recipients. "
            f"Failed contacts: {len(failed)}."
        )

    return int(list_id)


def build_newsletter_html(
    hero_image="",
    heading="",
    body="",
    button_text="",
    button_url="",
):
    safe_hero_image = escape(
        hero_image or ""
    )

    safe_heading = escape(
        heading or ""
    )

    safe_button_text = escape(
        button_text or ""
    )

    safe_button_url = escape(
        button_url or ""
    )

    body_lines = (
        body or ""
    ).splitlines()

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

    if (
        safe_button_text
        and safe_button_url
    ):
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


# ============================================================
# SUBSCRIBE
# ============================================================

class NewsletterSubscribeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = normalize_email(
            request.data.get(
                "email",
                "",
            )
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

            return brevo_error_response(
                error
            )

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


# ============================================================
# UNSUBSCRIBE
# ============================================================

class NewsletterUnsubscribeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = normalize_email(
            request.data.get(
                "email",
                "",
            )
        )

        if not email:
            return Response(
                {
                    "error": "Email is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        subscriber = (
            NewsletterSubscriber.objects
            .filter(
                email=email
            )
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


# ============================================================
# SUBSCRIBERS
# ============================================================

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


# ============================================================
# TEMPLATES
# ============================================================

class NewsletterTemplatesView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response(
            {
                "templates": []
            },
            status=status.HTTP_200_OK,
        )


# ============================================================
# AUDIENCE PREVIEW
# ============================================================

class NewsletterAudiencePreviewView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        include = request.data.get(
            "include",
            [],
        )

        if not isinstance(
            include,
            list,
        ):
            include = [include]

        selected_subscriber_ids = (
            request.data.get(
                "selected_subscriber_ids",
                [],
            )
        )

        exclude_emails = (
            request.data.get(
                "exclude_emails",
                [],
            )
        )

        allowed_groups = {
            "subscribers",
            "users",
            "customers",
            "everyone",
            "selected",
        }

        include = [
            item
            for item in include
            if item in allowed_groups
        ]

        if not include:
            include = [
                "subscribers"
            ]

        audience = get_audience_emails(
            include=include,
            selected_subscriber_ids=(
                selected_subscriber_ids
            ),
            exclude_emails=exclude_emails,
        )

        return Response(
            {
                "recipient_count": len(
                    audience["emails"]
                ),

                "counts": (
                    audience["available"]
                ),

                "excluded_count": (
                    audience["excluded_count"]
                ),
            },
            status=status.HTTP_200_OK,
        )


# ============================================================
# CAMPAIGNS
# ============================================================

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
                campaign_id = campaign.get(
                    "id"
                )

                if not campaign_id:
                    continue

                seen_ids.add(
                    campaign_id
                )

                local = (
                    local_by_brevo_id.get(
                        campaign_id
                    )
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

                        "brevo_campaign_id": (
                            campaign_id
                        ),

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
                            local.recipients
                            if local
                            else (
                                recipients_data.get(
                                    "recipients",
                                    0,
                                )
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

                        "recipient_type": (
                            local.recipient_type
                            if local
                            else "subscribers"
                        ),

                        "audience_config": (
                            local.audience_config
                            if local
                            else {}
                        ),
                    }
                )

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

                        "recipient_type": (
                            local.recipient_type
                        ),

                        "audience_config": (
                            local.audience_config
                        ),
                    }
                )

            return Response(
                results,
                status=status.HTTP_200_OK,
            )

        except Exception as error:
            return brevo_error_response(
                error
            )

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

        recipient_type = (
            request.data.get(
                "recipient_type",
                "subscribers",
            )
            .strip()
            .lower()
        )

        include = request.data.get(
            "include",
            [],
        )

        if not isinstance(
            include,
            list,
        ):
            include = [include]

        exclude_emails = (
            request.data.get(
                "exclude_emails",
                [],
            )
        )

        selected_subscriber_ids = (
            request.data.get(
                "selected_subscriber_ids",
                [],
            )
        )

        allowed_types = {
            "subscribers": [
                "subscribers"
            ],
            "users": [
                "users"
            ],
            "customers": [
                "customers"
            ],
            "both": [
                "subscribers",
                "customers",
            ],
            "everyone": [
                "everyone"
            ],
            "selected": [
                "selected"
            ],
        }

        if recipient_type in allowed_types:
            include = allowed_types[
                recipient_type
            ]

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

        if (
            button_text
            and not button_url
        ):
            return Response(
                {
                    "error": (
                        "Button URL is required "
                        "when button text is provided."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        audience = get_audience_emails(
            include=include,
            selected_subscriber_ids=(
                selected_subscriber_ids
            ),
            exclude_emails=exclude_emails,
        )

        recipient_emails = sorted(
            audience["emails"]
        )

        if not recipient_emails:
            return Response(
                {
                    "error": (
                        "No eligible newsletter recipients "
                        "were found for this audience."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        html_content = build_newsletter_html(
            hero_image=hero_image,
            heading=heading,
            body=body,
            button_text=button_text,
            button_url=button_url,
        )

        brevo_list_id = None
        brevo_campaign_id = None

        try:
            brevo_list_id = (
                create_campaign_recipient_list(
                    campaign_name=name,
                    emails=recipient_emails,
                )
            )

            campaign_data = (
                create_brevo_html_campaign(
                    name=name,
                    subject=subject,
                    preview=preview,
                    html_content=html_content,
                    sender_name=sender_name,
                    sender_email=sender_email,
                    list_ids=[
                        brevo_list_id
                    ],
                )
            )

            brevo_campaign_id = (
                campaign_data.get(
                    "id"
                )
            )

            if not brevo_campaign_id:
                raise RuntimeError(
                    "Brevo did not return a campaign ID."
                )

            audience_config = {
                "include": include,
                "exclude": [],
                "exclude_emails": (
                    sorted(
                        clean_email_set(
                            exclude_emails
                        )
                    )
                ),
                "selected_subscriber_ids": (
                    selected_subscriber_ids
                ),
                "brevo_list_id": (
                    brevo_list_id
                ),
            }

            local_campaign = (
                NewsletterCampaign.objects.create(
                    brevo_campaign_id=(
                        brevo_campaign_id
                    ),

                    name=name,

                    subject=subject,

                    preview=preview,

                    template_id=None,

                    sender_name=sender_name,

                    sender_email=sender_email,

                    recipients=len(
                        recipient_emails
                    ),

                    status="draft",

                    hero_image=hero_image,

                    heading=heading,

                    body=body,

                    button_text=button_text,

                    button_url=button_url,

                    recipient_type=(
                        recipient_type
                    ),

                    audience_config=(
                        audience_config
                    ),

                    recipient_emails=(
                        recipient_emails
                    ),
                )
            )

            return Response(
                {
                    "message": (
                        "Newsletter draft created successfully."
                    ),

                    "id": (
                        brevo_campaign_id
                    ),

                    "brevo_campaign_id": (
                        brevo_campaign_id
                    ),

                    "html_content": (
                        html_content
                    ),

                    "recipient_count": (
                        len(
                            recipient_emails
                        )
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

            if brevo_list_id:
                try:
                    delete_brevo_list(
                        brevo_list_id
                    )
                except Exception:
                    pass

            return brevo_error_response(
                error
            )


# ============================================================
# SEND CAMPAIGN
# ============================================================

class NewsletterCampaignSendDraftView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
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

        if (
            campaign.status
            and campaign.status.lower()
            == "sent"
        ):
            return Response(
                {
                    "error": (
                        "This newsletter has already been sent."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        recipient_emails = (
            campaign.recipient_emails
            or []
        )

        if not recipient_emails:
            return Response(
                {
                    "error": (
                        "This campaign has no saved recipients."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        audience_config = (
            campaign.audience_config
            or {}
        )

        brevo_list_id = (
            audience_config.get(
                "brevo_list_id"
            )
        )

        if not brevo_list_id:
            return Response(
                {
                    "error": (
                        "This campaign does not have "
                        "a recipient list."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = send_brevo_draft_campaign(
                pk
            )

            campaign.recipients = len(
                recipient_emails
            )

            campaign.status = "sent"

            campaign.sent_at = (
                timezone.now()
            )

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

            return brevo_error_response(
                error
            )


# ============================================================
# TEST EMAIL
# ============================================================

class NewsletterCampaignTestView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        email = normalize_email(
            request.data.get(
                "email",
                "",
            )
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

        try:
            validate_email(email)

        except ValidationError:
            return Response(
                {
                    "error": (
                        "Enter a valid test email address."
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

                    "campaign_id": (
                        campaign_id
                    ),

                    "brevo": result,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as error:
            return brevo_error_response(
                error
            )


# ============================================================
# REFRESH CAMPAIGN
# ============================================================

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
            data = get_brevo_campaign(
                pk
            )

            statistics = (
                data.get(
                    "statistics",
                    {},
                )
                or {}
            )

            global_stats = (
                statistics.get(
                    "globalStats",
                    {},
                )
                or {}
            )

            open_rate = (
                global_stats.get(
                    "openRate"
                )
                or global_stats.get(
                    "opensRate"
                )
                or 0
            )

            click_rate = (
                global_stats.get(
                    "clickRate"
                )
                or 0
            )

            if campaign:
                campaign.status = data.get(
                    "status",
                    campaign.status,
                )

                campaign.opened_rate = (
                    f"{open_rate}%"
                )

                campaign.click_rate = (
                    f"{click_rate}%"
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
            return brevo_error_response(
                error
            )