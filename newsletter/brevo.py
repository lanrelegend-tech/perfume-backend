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

    # -----------------------------------------------------
    # Make sure every recipient exists in Brevo first.
    #
    # We do NOT add them to the main newsletter list here.
    # We only make sure the contact exists so the temporary
    # campaign list can accept them.
    # -----------------------------------------------------

    for email in emails:
        try:
            brevo_request(
                "POST",
                "/contacts",
                data={
                    "email": email,
                    "updateEnabled": True,
                },
            )
        except RuntimeError as error:
            error_message = str(error).lower()

            # A contact that already exists is fine.
            if (
                "already exist" in error_message
                or "already exists" in error_message
            ):
                continue

            all_failure.append(email)

    # -----------------------------------------------------
    # Add the contacts to the temporary campaign list.
    # -----------------------------------------------------

    contacts_to_add = [
        email
        for email in emails
        if email not in all_failure
    ]

    for index in range(
        0,
        len(contacts_to_add),
        500,
    ):
        batch = contacts_to_add[
            index:index + 500
        ]

        try:
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

        except RuntimeError as error:
            error_message = str(error).lower()

            # Brevo can return this when a contact is already
            # in the list. That is not a campaign failure.
            if (
                "already in list" in error_message
                or "contact already in list" in error_message
            ):
                # Treat the entire batch as usable. Brevo has
                # already accepted the contacts into the list
                # or they were already there.
                all_success.extend(batch)
                continue

            # If Brevo still rejects the batch, try the
            # contacts individually so one problematic email
            # does not break the entire campaign.
            for email in batch:
                try:
                    brevo_request(
                        "POST",
                        f"/contacts/lists/{int(list_id)}/contacts/add",
                        data={
                            "emails": [email],
                        },
                    )

                    all_success.append(email)

                except RuntimeError as individual_error:
                    individual_message = str(
                        individual_error
                    ).lower()

                    if (
                        "already in list"
                        in individual_message
                        or "contact already in list"
                        in individual_message
                    ):
                        all_success.append(email)
                    else:
                        all_failure.append(email)

    return {
        "success": list(
            dict.fromkeys(all_success)
        ),
        "failure": list(
            dict.fromkeys(all_failure)
        ),
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
    email,
    subject,
    html_content,
    sender_name,
    sender_email,
):
    return brevo_request(
        "POST",
        "/smtp/email",
        data={
            "sender": {
                "name": sender_name,
                "email": sender_email,
            },
            "to": [
                {
                    "email": email,
                }
            ],
            "subject": subject,
            "htmlContent": html_content,
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