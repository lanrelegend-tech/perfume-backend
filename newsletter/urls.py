from django.urls import path

from .views import (
    NewsletterAudiencePreviewView,
    NewsletterCampaignRefreshView,
    NewsletterCampaignSendDraftView,
    NewsletterCampaignTestView,
    NewsletterCampaignsView,
    NewsletterSubscribeView,
    NewsletterSubscribersView,
    NewsletterTemplatesView,
    NewsletterUnsubscribeView,
)


urlpatterns = [
    path(
        "subscribe/",
        NewsletterSubscribeView.as_view(),
        name="newsletter-subscribe",
    ),

    path(
        "unsubscribe/",
        NewsletterUnsubscribeView.as_view(),
        name="newsletter-unsubscribe",
    ),

    path(
        "subscribers/",
        NewsletterSubscribersView.as_view(),
        name="newsletter-subscribers",
    ),

    path(
        "templates/",
        NewsletterTemplatesView.as_view(),
        name="newsletter-templates",
    ),

    path(
        "audience/preview/",
        NewsletterAudiencePreviewView.as_view(),
        name="newsletter-audience-preview",
    ),

    path(
        "campaigns/",
        NewsletterCampaignsView.as_view(),
        name="newsletter-campaigns",
    ),

    path(
        "campaigns/<int:pk>/send/",
        NewsletterCampaignSendDraftView.as_view(),
        name="newsletter-campaign-send-draft",
    ),

    path(
        "campaigns/test/",
        NewsletterCampaignTestView.as_view(),
        name="newsletter-campaign-test",
    ),

    path(
        "campaigns/<int:pk>/refresh/",
        NewsletterCampaignRefreshView.as_view(),
        name="newsletter-campaign-refresh",
    ),
]