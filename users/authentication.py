from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication


class VersionedJWTAuthentication(JWTAuthentication):

    def get_user(self, validated_token):
        user = super().get_user(validated_token)

        profile = getattr(user, "profile", None)

        if profile is None:
            raise AuthenticationFailed(
                "User profile not found.",
                code="profile_not_found",
            )

        token_version = validated_token.get(
            "session_version"
        )

        if token_version is None:
            raise AuthenticationFailed(
                "Invalid session.",
                code="invalid_session",
            )

        try:
            token_version = int(token_version)
        except (TypeError, ValueError):
            raise AuthenticationFailed(
                "Invalid session.",
                code="invalid_session",
            )

        if token_version != profile.session_version:
            raise AuthenticationFailed(
                "Session has been revoked.",
                code="session_revoked",
            )

        return user