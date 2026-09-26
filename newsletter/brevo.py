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


def create_brevo_campaign(
    name,
    subject,
    preview,
    template_id,
    sender_name,
    sender_email,
):
    list_id = settings.BREVO_LIST_ID

    if not list_id:
        raise RuntimeError(
            "BREVO_LIST_ID is not configured."
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
        "recipients": {
            "listIds": [
                int(list_id)
            ],
        },
        "type": "classic",
    }

    return brevo_request(
        "POST",
        "/emailCampaigns",
        data=data,
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


def delete_brevo_campaign(
    campaign_id,
):
    return brevo_request(
        "DELETE",
        f"/emailCampaigns/{campaign_id}",
    )