from datetime import timedelta
import secrets

from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class CustomerProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile"
    )

    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)

    # Used to immediately revoke existing JWT sessions.
    session_version = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"


class EmailVerificationCode(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="email_verification"
    )

    # Stores a Django password hash, NOT the plaintext code.
    code = models.CharField(max_length=128)

    expires_at = models.DateTimeField()

    verified_at = models.DateTimeField(
        null=True,
        blank=True
    )

    attempts = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    MAX_ATTEMPTS = 5

    def is_valid(self):
        return (
            timezone.now() < self.expires_at
            and self.attempts < self.MAX_ATTEMPTS
            and self.verified_at is None
        )

    def generate_code(self):
        code = str(
            secrets.randbelow(900000) + 100000
        )

        self.code = make_password(code)

        self.expires_at = (
            timezone.now()
            + timedelta(minutes=10)
        )

        self.attempts = 0
        self.verified_at = None

        self.save(
            update_fields=[
                "code",
                "expires_at",
                "attempts",
                "verified_at",
            ]
        )

        return code

    def __str__(self):
        return f"{self.user.email} verification"


class PasswordResetCode(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="password_reset"
    )

    # Stores a Django password hash, NOT the plaintext code.
    code = models.CharField(max_length=128)

    expires_at = models.DateTimeField()

    attempts = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    MAX_ATTEMPTS = 5

    def is_valid(self):
        return (
            timezone.now() < self.expires_at
            and self.attempts < self.MAX_ATTEMPTS
        )

    def generate_code(self):
        code = str(
            secrets.randbelow(900000) + 100000
        )

        self.code = make_password(code)

        self.expires_at = (
            timezone.now()
            + timedelta(minutes=10)
        )

        self.attempts = 0

        self.save(
            update_fields=[
                "code",
                "expires_at",
                "attempts",
            ]
        )

        return code

    def __str__(self):
        return f"{self.user.email} password reset"