import requests

from django.conf import settings


BREVO_BASE_URL = "https://api.brevo.com/v3"


def brevo_headers():
    api_key = settings.BREVO_API_KEY

    if not api_key:
        raise RuntimeError(
            "BREVO_API_KEY is not configured."
        )

    return {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json",
    }


def brevo_request(
    method,
    endpoint,
    data=None,
    params=None,
):
    response = requests.request(
        method=method,
        url=f"{BREVO_BASE_URL}{endpoint}",
        headers=brevo_headers(),
        json=data,
        params=params,
        timeout=30,
    )

    if not response.ok:
        try:
            error_data = response.json()
        except Exception:
            error_data = {}

        message = (
            error_data.get("message")
            or error_data.get("code")
            or response.text
            or "Brevo request failed."
        )

        raise RuntimeError(
            f"Brevo error ({response.status_code}): {message}"
        )

    if response.status_code == 204:
        return {}

    try:
        return response.json()
    except Exception:
        return {}


# ============================================================
# TEMPLATES
# ============================================================

def get_brevo_templates():
    return brevo_request(
        "GET",
        "/smtp/templates",
        params={
            "templateStatus": True,
            "limit": 1000,
            "offset": 0,
            "sort": "desc",
        },
    )


# ============================================================
# CAMPAIGNS
# ============================================================

def get_brevo_campaigns():
    return brevo_request(
        "GET",
        "/emailCampaigns",
        params={
            "limit": 100,
            "offset": 0,
            "sort": "desc",
        },
    )


def get_brevo_campaign(campaign_id):
    return brevo_request(
        "GET",
        f"/emailCampaigns/{campaign_id}",
    )


def get_brevo_draft_campaigns():
    return brevo_request(
        "GET",
        "/emailCampaigns",
        params={
            "status": "draft",
            "type": "classic",
            "limit": 100,
            "offset": 0,
            "sort": "desc",
        },
    )


# ============================================================
# CONTACTS
# ============================================================

def create_brevo_contact(
    email,
    first_name="",
    last_name="",
):
    list_id = settings.BREVO_LIST_ID

    if not list_id:
        raise RuntimeError(
            "BREVO_LIST_ID is not configured."
        )

    data = {
        "email": email,
        "attributes": {
            "FNAME": first_name,
            "LNAME": last_name,
        },
        "listIds": [
            int(list_id)
        ],
        "emailBlacklisted": False,
        "updateEnabled": True,
    }

    return brevo_request(
        "POST",
        "/contacts",
        data=data,
    )


def unsubscribe_brevo_contact(email):
    list_id = settings.BREVO_LIST_ID

    if not list_id:
        raise RuntimeError(
            "BREVO_LIST_ID is not configured."
        )

    return brevo_request(
        "PUT",
        f"/contacts/{email}",
        data={
            "unlinkListIds": [
                int(list_id)
            ],
        },
    )


# ============================================================
# CAMPAIGN CREATION
# ============================================================

def create_brevo_campaign(
    name,
    subject,
    preview,
    template_id,
    sender_name,
    sender_email,
    list_ids=None,
    segment_ids=None,
):
    """
    Create a Brevo campaign using explicit recipient lists.

    list_ids:
        Example: [3]

    segment_ids:
        Example: [12]

    If list_ids/segment_ids are not supplied,
    the configured BREVO_LIST_ID is used.
    """

    if list_ids is None:
        configured_list_id = settings.BREVO_LIST_ID

        if not configured_list_id:
            raise RuntimeError(
                "BREVO_LIST_ID is not configured."
            )

        list_ids = [
            int(configured_list_id)
        ]

    recipients = {}

    if list_ids:
        recipients["listIds"] = [
            int(item)
            for item in list_ids
        ]

    if segment_ids:
        recipients["segmentIds"] = [
            int(item)
            for item in segment_ids
        ]

    if not recipients:
        raise RuntimeError(
            "No Brevo recipients were provided."
        )

    data = {
        "name": name,
        "subject": subject,
        "previewText": preview,
        "sender": {
            "name": sender_name,
            "email": sender_email,
        },
        "templateId": int(template_id),
        "recipients": recipients,
        "type": "classic",
    }

    return brevo_request(
        "POST",
        "/emailCampaigns",
        data=data,
    )


def create_brevo_html_campaign(
    name,
    subject,
    preview,
    html_content,
    sender_name,
    sender_email,
    list_ids=None,
    segment_ids=None,
):
    """
    Create an HTML Brevo campaign.

    Explicit list_ids/segment_ids can be supplied by the
    audience engine.

    If no recipient lists are supplied, the configured
    BREVO_LIST_ID is used as a fallback.
    """

    if list_ids is None:
        configured_list_id = settings.BREVO_LIST_ID

        if not configured_list_id:
            raise RuntimeError(
                "BREVO_LIST_ID is not configured."
            )

        list_ids = [
            int(configured_list_id)
        ]

    recipients = {}

    if list_ids:
        recipients["listIds"] = [
            int(item)
            for item in list_ids
        ]

    if segment_ids:
        recipients["segmentIds"] = [
            int(item)
            for item in segment_ids
        ]

    if not recipients:
        raise RuntimeError(
            "No Brevo recipients were provided."
        )

    data = {
        "name": name,
        "subject": subject,
        "previewText": preview,
        "sender": {
            "name": sender_name,
            "email": sender_email,
        },
        "recipients": recipients,
        "htmlContent": html_content,
        "type": "classic",
    }

    return brevo_request(
        "POST",
        "/emailCampaigns",
        data=data,
    )


# ============================================================
# TEST EMAIL
# ============================================================

def send_brevo_test(
    campaign_id,
    email,
):
    return brevo_request(
        "POST",
        f"/emailCampaigns/{campaign_id}/sendTest",
        data={
            "emailTo": [
                email
            ],
        },
    )


# ============================================================
# SEND
# ============================================================

def send_brevo_campaign(campaign_id):
    return brevo_request(
        "POST",
        f"/emailCampaigns/{campaign_id}/sendNow",
    )


def send_brevo_draft_campaign(campaign_id):
    return brevo_request(
        "POST",
        f"/emailCampaigns/{campaign_id}/sendNow",
    )


# ============================================================
# DELETE
# ============================================================

def delete_brevo_campaign(campaign_id):
    return brevo_request(
        "DELETE",
        f"/emailCampaigns/{campaign_id}",
    )


def get_brevo_list(list_id):
    return brevo_request(
        "GET",
        f"/contacts/lists/{int(list_id)}",
    )


def create_brevo_list(
    name,
    folder_id,
):
    return brevo_request(
        "POST",
        "/contacts/lists",
        data={
            "name": name,
            "folderId": int(folder_id),
        },
    )


def add_brevo_contacts_to_list(
    list_id,
    emails,
):
    clean_emails = [
        str(email).strip().lower()
        for email in emails
        if email
    ]

    clean_emails = list(
        dict.fromkeys(clean_emails)
    )

    if not clean_emails:
        return {
            "success": [],
            "failure": [],
        }

    return brevo_request(
        "POST",
        f"/contacts/lists/{int(list_id)}/contacts/add",
        data={
            "emails": clean_emails,
        },
    )


def delete_brevo_list(
    list_id,
):
    return brevo_request(
        "DELETE",
        f"/contacts/lists/{int(list_id)}",
    )


def update_brevo_campaign_recipients(
    campaign_id,
    list_ids,
):
    return brevo_request(
        "PUT",
        f"/emailCampaigns/{int(campaign_id)}",
        data={
            "recipients": {
                "listIds": [
                    int(item)
                    for item in list_ids
                ],
            },
        },
    )