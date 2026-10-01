import logging
import requests

from django.conf import settings


def purge_products_cache():
    """Purge the public products API cache from Cloudflare."""

    logger = logging.getLogger(__name__)

    zone_id = getattr(
        settings,
        "CLOUDFLARE_ZONE_ID",
        None
    )

    api_token = getattr(
        settings,
        "CLOUDFLARE_API_TOKEN",
        None
    )

    if not zone_id:
        logger.error(
            "Cloudflare purge failed: "
            "CLOUDFLARE_ZONE_ID is missing."
        )
        return

    if not api_token:
        logger.error(
            "Cloudflare purge failed: "
            "CLOUDFLARE_API_TOKEN is missing."
        )
        return

    try:
        response = requests.post(
            (
                "https://api.cloudflare.com/client/v4/"
                f"zones/{zone_id}/purge_cache"
            ),
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            },
            json={
                "purge_everything": True,
            },
            timeout=10,
        )

        if response.ok:
            logger.info(
                "Cloudflare products cache "
                "purged successfully."
            )
        else:
            logger.error(
                "Cloudflare cache purge failed: %s %s",
                response.status_code,
                response.text,
            )

    except requests.RequestException as exc:
        logger.error(
            "Cloudflare cache purge request failed: %s",
            exc,
        )