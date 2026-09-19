from django.db import models
from django.contrib.auth.models import User
import random
from django.utils import timezone
from datetime import timedelta



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

    code = models.CharField(max_length=6)

    expires_at = models.DateTimeField()
    verified_at = models.DateTimeField(
    null=True,
    blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        return (
            timezone.now() < self.expires_at
        )

    def generate_code(self):
        self.code = str(
            random.randint(100000, 999999)
        )

        self.expires_at = (
            timezone.now()
            + timedelta(minutes=10)
        )

        self.save()

    def __str__(self):
        return f"{self.user.email} verification"
class PasswordResetCode(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="password_reset"
    )

    code = models.CharField(max_length=6)

    expires_at = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        return timezone.now() < self.expires_at

    def generate_code(self):
        self.code = str(
            random.randint(100000, 999999)
        )

        self.expires_at = (
            timezone.now()
            + timedelta(minutes=10)
        )

        self.save()

    def __str__(self):
        return f"{self.user.email} password reset"    