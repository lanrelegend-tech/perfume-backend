from django.db import models


class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)

    first_name = models.CharField(
        max_length=100,
        blank=True,
    )

    last_name = models.CharField(
        max_length=100,
        blank=True,
    )

    is_subscribed = models.BooleanField(
        default=True,
    )

    brevo_contact_id = models.PositiveBigIntegerField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return self.email


class NewsletterCampaign(models.Model):
    brevo_campaign_id = models.PositiveBigIntegerField(
        unique=True,
        null=True,
        blank=True,
    )

    name = models.CharField(
        max_length=255,
    )

    subject = models.CharField(
        max_length=255,
    )

    preview = models.TextField(
        blank=True,
    )

    template_id = models.PositiveBigIntegerField(
        null=True,
        blank=True,
    )

    sender_name = models.CharField(
        max_length=255,
    )

    sender_email = models.EmailField()

    recipients = models.PositiveIntegerField(
        default=0,
    )

    status = models.CharField(
        max_length=50,
        default="draft",
    )

    opened_rate = models.CharField(
        max_length=50,
        blank=True,
    )

    click_rate = models.CharField(
        max_length=50,
        blank=True,
    )

    sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # Newsletter builder content
    hero_image = models.URLField(
        blank=True,
    )

    heading = models.CharField(
        max_length=255,
        blank=True,
    )

    body = models.TextField(
        blank=True,
    )

    button_text = models.CharField(
        max_length=100,
        blank=True,
    )

    button_url = models.URLField(
        blank=True,
    )
        # Campaign audience settings
    recipient_type = models.CharField(
        max_length=50,
        default="subscribers",
    )

    audience_config = models.JSONField(
        default=dict,
        blank=True,
    )

    recipient_emails = models.JSONField(
        default=list,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return self.name