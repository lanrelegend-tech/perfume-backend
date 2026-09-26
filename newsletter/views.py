from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone
from django.utils.html import escape
from django.core.files.storage import default_storage

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Order

from .brevo import (
    add_brevo_contacts_to_list,
    create_brevo_html_campaign,
    create_brevo_list,
    create_brevo_contact,
    delete_brevo_campaign,
    delete_brevo_list,
    get_brevo_campaign,
    get_brevo_campaigns,
    get_brevo_list,
    remove_all_brevo_contacts_from_list,
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


User = get_user_model()


# =========================================================
# GENERAL HELPERS
# =========================================================

def normalize_email(email):
    return (
        str(email or "")
        .strip()
        .lower()
    )


def normalize_email_set(values):
    result = set()

    for email in values:
        email = normalize_email(email)

        if email:
            result.add(email)

    return result


def brevo_error_response(error):
    return Response(
        {
            "error": str(error),
            "message": str(error),
        },
        status=status.HTTP_502_BAD_GATEWAY,
    )


# =========================================================
# AUDIENCE ENGINE
# =========================================================

def get_subscriber_emails():
    return normalize_email_set(
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
    return normalize_email_set(
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
    return normalize_email_set(
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


def get_selected_subscriber_emails(
    selected_ids,
):
    clean_ids = []

    for value in selected_ids or []:
        try:
            clean_ids.append(
                int(value)
            )
        except (
            TypeError,
            ValueError,
        ):
            continue

    if not clean_ids:
        return set()

    return normalize_email_set(
        NewsletterSubscriber.objects
        .filter(
            id__in=clean_ids,
            is_subscribed=True,
        )
        .values_list(
            "email",
            flat=True,
        )
    )


def normalize_audience_list(
    value,
):
    if value is None:
        return []

    if isinstance(
        value,
        str,
    ):
        value = [
            value
        ]

    return [
        str(item)
        .strip()
        .lower()
        for item in value
        if str(item).strip()
    ]


def get_audience_config(
    data,
):
    recipient_type = (
        str(
            data.get(
                "recipient_type",
                "",
            )
        )
        .strip()
        .lower()
    )

    include = normalize_audience_list(
        data.get("include")
    )

    exclude = normalize_audience_list(
        data.get("exclude")
    )

    exclude_emails = normalize_email_set(
        data.get(
            "exclude_emails",
            [],
        )
        or []
    )

    selected_ids = (
        data.get(
            "selected_subscriber_ids",
            [],
        )
        or data.get(
            "recipient_ids",
            [],
        )
        or []
    )

    # Frontend sends recipient_type, so use it
    # when include is missing.
    if not include:
        if recipient_type:
            include = [
                recipient_type
            ]
        else:
            include = [
                "subscribers"
            ]
# "both" means newsletter subscribers + paid customers.
if "both" in include:
    include = [
        item
        for item in include
        if item != "both"
    ]

    include.extend(
        [
            "subscribers",
            "customers",
        ]
    )

    # "everyone" already represents the complete
    # available audience, so don't combine it with
    # other include groups.
    if "everyone" in include:
        include = [
            "everyone"
        ]

    allowed = {
        "subscribers",
        "users",
        "customers",
        "everyone",
        "selected",
    }

    include = [
        item
        for item in include
        if item in allowed
    ]

    exclude = [
        item
        for item in exclude
        if item in allowed
        and item != "everyone"
    ]

    return {
        "recipient_type": (
            recipient_type
            or include[0]
        ),
        "include": list(
            dict.fromkeys(include)
        ),
        "exclude": list(
            dict.fromkeys(exclude)
        ),
        "exclude_emails": sorted(
            exclude_emails
        ),
        "selected_subscriber_ids": [
            value
            for value in selected_ids
        ],
    }


def calculate_audience(
    data,
):
    config = get_audience_config(
        data
    )

    subscriber_emails = (
        get_subscriber_emails()
    )

    user_emails = (
        get_registered_user_emails()
    )

    customer_emails = (
        get_customer_emails()
    )

    selected_emails = (
        get_selected_subscriber_emails(
            config[
                "selected_subscriber_ids"
            ]
        )
    )

    counts = {
        "subscribers": len(
            subscriber_emails
        ),

        "users": len(
            user_emails
        ),

        "customers": len(
            customer_emails
        ),
        "both": len(
    subscriber_emails |
    customer_emails
        ),



        "everyone": len(
            subscriber_emails |
            user_emails |
            customer_emails
        ),

        "selected": len(
            selected_emails
        ),
    }

    audience_sets = {
        "subscribers": subscriber_emails,
        "users": user_emails,
        "customers": customer_emails,
        "selected": selected_emails,
    }

    recipient_emails = set()

    for group in config[
        "include"
    ]:
        if group == "everyone":
            recipient_emails.update(
                subscriber_emails |
                user_emails |
                customer_emails
            )
        elif group in audience_sets:
            recipient_emails.update(
                audience_sets[group]
            )

    before_exclusion_count = len(
        recipient_emails
    )

    # Remove whole audience groups.
    for group in config[
        "exclude"
    ]:
        if group == "subscribers":
            recipient_emails -= (
                subscriber_emails
            )

        elif group == "users":
            recipient_emails -= (
                user_emails
            )

        elif group == "customers":
            recipient_emails -= (
                customer_emails
            )

        elif group == "selected":
            recipient_emails -= (
                selected_emails
            )

    # Remove individual emails.
    recipient_emails -= set(
        config[
            "exclude_emails"
        ]
    )

    recipient_emails = sorted(
        recipient_emails
    )

    excluded_count = (
        before_exclusion_count
        - len(recipient_emails)
    )

    return {
        "recipient_emails": (
            recipient_emails
        ),

        "recipient_count": len(
            recipient_emails
        ),

        "excluded_count": (
            excluded_count
        ),

        "counts": counts,

        "audience_config": config,
    }


# =========================================================
# NEWSLETTER HTML
# =========================================================

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
    You are receiving this email from ORENTEMIST.
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


# =========================================================
# SUBSCRIBE
# =========================================================

class NewsletterSubscribeView(APIView):
    permission_classes = [
        AllowAny
    ]

    def post(
        self,
        request,
    ):
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
                    "error": (
                        "Email is required."
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
                        "Enter a valid email address."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        subscriber, created = (
            NewsletterSubscriber.objects
            .get_or_create(
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
            brevo_result = (
                create_brevo_contact(
                    email=email,
                    first_name=(
                        subscriber.first_name
                    ),
                    last_name=(
                        subscriber.last_name
                    ),
                )
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
                    "You have successfully "
                    "subscribed to the "
                    "ORENTEMIST newsletter."
                ),
                "subscriber": (
                    NewsletterSubscriberSerializer(
                        subscriber
                    ).data
                ),
            },
            status=status.HTTP_201_CREATED,
        )


# =========================================================
# UNSUBSCRIBE
# =========================================================

class NewsletterUnsubscribeView(APIView):
    permission_classes = [
        AllowAny
    ]

    def post(
        self,
        request,
    ):
        email = normalize_email(
            request.data.get(
                "email",
                "",
            )
        )

        if not email:
            return Response(
                {
                    "error": (
                        "Email is required."
                    )
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


# =========================================================
# SUBSCRIBERS
# =========================================================

class NewsletterSubscribersView(APIView):
    permission_classes = [
        IsAdminUser
    ]

    def get(
        self,
        request,
    ):
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


# =========================================================
# AUDIENCE PREVIEW
# =========================================================

class NewsletterAudiencePreviewView(APIView):
    permission_classes = [
        IsAdminUser
    ]

    def post(
        self,
        request,
    ):
        try:
            audience = calculate_audience(
                request.data
            )

            return Response(
                {
                    "recipient_count": (
                        audience[
                            "recipient_count"
                        ]
                    ),
                    "counts": (
                        audience["counts"]
                    ),
                    "excluded_count": (
                        audience[
                            "excluded_count"
                        ]
                    ),
                    "audience_config": (
                        audience[
                            "audience_config"
                        ]
                    ),
                },
                status=status.HTTP_200_OK,
            )

        except Exception as error:
            return Response(
                {
                    "error": str(error),
                    "message": str(error),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =========================================================
# TEMPLATES
# =========================================================

class NewsletterTemplatesView(APIView):
    permission_classes = [
        IsAdminUser
    ]

    def get(
        self,
        request,
    ):
        return Response(
            {
                "templates": []
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# CAMPAIGNS
# =========================================================

class NewsletterCampaignsView(APIView):
    permission_classes = [
        IsAdminUser
    ]

    def get(
        self,
        request,
    ):
        try:
            brevo_data = (
                get_brevo_campaigns()
            )

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
                            else recipients_data.get(
                                "recipients",
                                0,
                            )
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

                        "sender_name": (
                            local.sender_name
                        ),

                        "sender_email": (
                            local.sender_email
                        ),

                        "recipients": (
                            local.recipients
                        ),

                        "recipient_type": (
                            local.recipient_type
                        ),

                        "audience_config": (
                            local.audience_config
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
            return brevo_error_response(
                error
            )

    def post(
        self,
        request,
    ):
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

        audience = calculate_audience(
            request.data
        )

        recipient_emails = (
            audience[
                "recipient_emails"
            ]
        )

        if not recipient_emails:
            return Response(
                {
                    "error": (
                        "No eligible newsletter "
                        "recipients were found "
                        "for this audience."
                    ),
                    "counts": (
                        audience["counts"]
                    ),
                    "audience_config": (
                        audience[
                            "audience_config"
                        ]
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        html_content = (
            build_newsletter_html(
                hero_image=hero_image,
                heading=heading,
                body=body,
                button_text=button_text,
                button_url=button_url,
            )
        )

        temp_list_id = None
        brevo_campaign_id = None

        try:
            # Use the existing ORENTEMIST list's
            # folder as the parent for campaign lists.
            base_list_id = int(
                settings.BREVO_LIST_ID
            )

            base_list = (
                get_brevo_list(
                    base_list_id
                )
            )

            folder_id = (
                base_list.get(
                    "folderId"
                )
            )

            if not folder_id:
                raise RuntimeError(
                    "Brevo could not determine "
                    "the folder for BREVO_LIST_ID."
                )

            list_name = (
                f"ORENTEMIST Campaign - "
                f"{name[:150]}"
            )

            temp_list = (
                create_brevo_list(
                    name=list_name,
                    folder_id=folder_id,
                )
            )

            temp_list_id = (
                temp_list.get("id")
            )

            if not temp_list_id:
                raise RuntimeError(
                    "Brevo did not return a "
                    "recipient list ID."
                )

            # The selected users/customers may not
            # already exist in Brevo.
            #
            # First try to add them to the list.
            add_result = (
                add_brevo_contacts_to_list(
                    temp_list_id,
                    recipient_emails,
                )
            )

            failed_emails = set(
                normalize_email_set(
                    add_result.get(
                        "failure",
                        [],
                    )
                )
            )

            # If an address doesn't exist in Brevo,
            # create it directly in the campaign list.
            for email in failed_emails:
                try:
                    create_brevo_contact(
                        email=email,
                        first_name="",
                        last_name="",
                    )

                    add_brevo_contacts_to_list(
                        temp_list_id,
                        [email],
                    )

                except Exception:
                    pass

            # Verify that every requested recipient was
            # successfully added.
            final_add = (
                add_brevo_contacts_to_list(
                    temp_list_id,
                    recipient_emails,
                )
            )

            final_failures = (
                normalize_email_set(
                    final_add.get(
                        "failure",
                        [],
                    )
                )
            )

            if final_failures:
                missing = sorted(
                    final_failures
                )

                raise RuntimeError(
                    "Brevo could not add "
                    f"{len(missing)} recipient(s) "
                    "to the campaign list."
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
                        temp_list_id
                    ],
                )
            )

            brevo_campaign_id = (
                campaign_data.get("id")
            )

            if not brevo_campaign_id:
                raise RuntimeError(
                    "Brevo did not return "
                    "a campaign ID."
                )

            saved_audience_config = (
                audience[
                    "audience_config"
                ].copy()
            )

            saved_audience_config[
                "brevo_list_id"
            ] = temp_list_id

            saved_audience_config[
                "recipient_count"
            ] = len(
                recipient_emails
            )

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
                        audience[
                            "audience_config"
                        ][
                            "recipient_type"
                        ]
                    ),

                    audience_config=(
                        saved_audience_config
                    ),

                    recipient_emails=(
                        recipient_emails
                    ),
                )
            )

            return Response(
                {
                    "message": (
                        "Newsletter draft "
                        "created successfully."
                    ),

                    "campaign": (
                        NewsletterCampaignSerializer(
                            local_campaign
                        ).data
                    ),

                    "id": (
                        brevo_campaign_id
                    ),

                    "brevo_campaign_id": (
                        brevo_campaign_id
                    ),

                    "recipient_count": (
                        len(
                            recipient_emails
                        )
                    ),

                    "audience": audience,

                    "html_content": (
                        html_content
                    ),
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as error:
            # Clean up a list if campaign creation failed.
            if (
                temp_list_id
                and not brevo_campaign_id
            ):
                try:
                    delete_brevo_list(
                        temp_list_id
                    )
                except Exception:
                    pass

            return brevo_error_response(
                error
            )


# =========================================================
# SEND DRAFT
# =========================================================

class NewsletterCampaignSendDraftView(
    APIView
):
    permission_classes = [
        IsAdminUser
    ]

    def post(
        self,
        request,
        pk,
    ):
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
                        "Newsletter campaign "
                        "was not found."
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
                        "This newsletter "
                        "has already been sent."
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
                        "This campaign has "
                        "no saved recipients."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        audience_config = (
            campaign.audience_config
            or {}
        )

        temp_list_id = (
            audience_config.get(
                "brevo_list_id"
            )
        )

        if not temp_list_id:
            return Response(
                {
                    "error": (
                        "This campaign does "
                        "not have a recipient list."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Rebuild the campaign list immediately
            # before sending so manually unsubscribed
            # newsletter contacts are not sent a campaign.
            #
            # For campaigns whose audience is users/customers,
            # the saved audience remains the source of truth.
            remove_all_brevo_contacts_from_list(
                temp_list_id
            )

            add_result = (
                add_brevo_contacts_to_list(
                    temp_list_id,
                    recipient_emails,
                )
            )

            failures = (
                normalize_email_set(
                    add_result.get(
                        "failure",
                        [],
                    )
                )
            )

            if failures:
                raise RuntimeError(
                    "Brevo could not prepare "
                    "all campaign recipients."
                )

            result = (
                send_brevo_draft_campaign(
                    pk
                )
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

                    "recipient_count": (
                        len(
                            recipient_emails
                        )
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




class NewsletterImageUploadView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        image = request.FILES.get("image")

        if not image:
            return Response(
                {"error": "Image file is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            filename = default_storage.save(
                f"newsletter/{image.name}",
                image,
            )

            image_url = default_storage.url(filename)

            return Response(
                {
                    "url": image_url,
                    "filename": filename,
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as error:
            return Response(
                {
                    "error": "Unable to upload newsletter image.",
                    "message": str(error),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        
# =========================================================
# TEST EMAIL
# =========================================================

class NewsletterCampaignTestView(
    APIView
):
    permission_classes = [
        IsAdminUser
    ]

    def post(
        self,
        request,
    ):
        email = normalize_email(
            request.data.get(
                "email",
                "",
            )
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

        # -------------------------------------------------
        # VALIDATION
        # -------------------------------------------------

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

        if not subject:
            return Response(
                {
                    "error": (
                        "Subject is required."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not heading:
            return Response(
                {
                    "error": (
                        "Heading is required."
                    )
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

        # -------------------------------------------------
        # BUILD NEWSLETTER HTML
        # -------------------------------------------------

        try:
            html_content = build_newsletter_html(
                hero_image=hero_image,
                heading=heading,
                body=body,
                button_text=button_text,
                button_url=button_url,
            )

            # Add inbox preview text when provided.
            if preview:
                safe_preview = escape(
                    preview
                )

                html_content = html_content.replace(
                    "<body",
                    (
                        '<div style="display:none;'
                        'max-height:0;'
                        'overflow:hidden;'
                        'opacity:0;'
                        'color:transparent;'
                        'font-size:1px;'
                        'line-height:1px;">'
                        f"{safe_preview}"
                        "</div>"
                        "<body"
                    ),
                    1,
                )

        except Exception as error:
            return Response(
                {
                    "error": (
                        "Unable to build "
                        "test newsletter."
                    ),
                    "message": str(error),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # -------------------------------------------------
        # SEND DIRECTLY THROUGH BREVO TRANSACTIONAL EMAIL
        # -------------------------------------------------

        try:
            result = send_brevo_test(
                email=email,
                subject=subject,
                html_content=html_content,
                sender_name=sender_name,
                sender_email=sender_email,
            )

            return Response(
                {
                    "message": (
                        "Test newsletter "
                        "sent successfully."
                    ),
                    "email": email,
                    "brevo": result,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as error:
            return brevo_error_response(
                error
            )


# =========================================================
# REFRESH CAMPAIGN
# =========================================================

class NewsletterCampaignRefreshView(
    APIView
):
    permission_classes = [
        IsAdminUser
    ]

    def post(
        self,
        request,
        pk,
    ):
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

            if campaign:
                campaign.status = (
                    data.get(
                        "status",
                        campaign.status,
                    )
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
            return brevo_error_response(
                error
            )


