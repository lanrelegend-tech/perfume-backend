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


# ---------------------------------------------------------
# CONTACTS
# ---------------------------------------------------------

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


def unsubscribe_brevo_contact(
    email,
):
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


# ---------------------------------------------------------
# BREVO LISTS
# ---------------------------------------------------------

def get_brevo_list(
    list_id,
):
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
    emails = [
        str(email).strip().lower()
        for email in emails
        if email
    ]

    emails = list(dict.fromkeys(emails))

    if not emails:
        return {
            "success": [],
            "failure": [],
        }

    all_success = []
    all_failure = []

    # Keep batches reasonably sized.
    for index in range(
        0,
        len(emails),
        500,
    ):
        batch = emails[
            index:index + 500
        ]

        result = brevo_request(
            "POST",
            f"/contacts/lists/{int(list_id)}/contacts/add",
            data={
                "emails": batch,
            },
        )

        all_success.extend(
            result.get(
                "success",
                [],
            )
        )

        all_failure.extend(
            result.get(
                "failure",
                [],
            )
        )

    return {
        "success": all_success,
        "failure": all_failure,
    }


def remove_all_brevo_contacts_from_list(
    list_id,
):
    return brevo_request(
        "POST",
        f"/contacts/lists/{int(list_id)}/contacts/remove",
        data={
            "all": True,
        },
    )


def delete_brevo_list(
    list_id,
):
    return brevo_request(
        "DELETE",
        f"/contacts/lists/{int(list_id)}",
    )


# ---------------------------------------------------------
# CAMPAIGNS
# ---------------------------------------------------------

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


def get_brevo_campaign(
    campaign_id,
):
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


def create_brevo_campaign(
    name,
    subject,
    preview,
    html_content,
    sender_name,
    sender_email,
    list_ids,
):
    if not list_ids:
        raise RuntimeError(
            "At least one Brevo recipient list is required."
        )

    data = {
        "name": name,
        "subject": subject,
        "previewText": preview,
        "sender": {
            "name": sender_name,
            "email": sender_email,
        },
        "recipients": {
            "listIds": [
                int(list_id)
                for list_id in list_ids
            ],
        },
        "htmlContent": html_content,
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
):
    if list_ids is None:
        list_ids = [
            int(settings.BREVO_LIST_ID)
        ]

    return create_brevo_campaign(
        name=name,
        subject=subject,
        preview=preview,
        html_content=html_content,
        sender_name=sender_name,
        sender_email=sender_email,
        list_ids=list_ids,
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
                    int(list_id)
                    for list_id in list_ids
                ],
            },
        },
    )


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


def send_brevo_campaign(
    campaign_id,
):
    return brevo_request(
        "POST",
        f"/emailCampaigns/{campaign_id}/sendNow",
    )


def send_brevo_draft_campaign(
    campaign_id,
):
    return send_brevo_campaign(
        campaign_id
    )


def delete_brevo_campaign(
    campaign_id,
):
    return brevo_request(
        "DELETE",
        f"/emailCampaigns/{campaign_id}",
    )