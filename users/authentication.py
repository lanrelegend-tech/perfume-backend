from rest_framework.authentication import CSRFCheck
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication


def enforce_csrf(request):
    """
    Enforce Django CSRF protection for unsafe requests
    when authentication is performed through HttpOnly cookies.
    """

    check = CSRFCheck(lambda request: None)

    check.process_request(request)

    reason = check.process_view(
        request,
        lambda request: None,
        (),
        {},
    )

    if reason:
        raise PermissionDenied(
            f"CSRF Failed: {reason}"
        )


class VersionedJWTAuthentication(JWTAuthentication):

    def authenticate(self, request):

        raw_token = request.COOKIES.get(
            "access_token"
        )

        if not raw_token:
            return None

        try:

            validated_token = (
                self.get_validated_token(
                    raw_token
                )
            )

        except Exception:

            raise AuthenticationFailed(
                "Invalid or expired token.",
                code="token_not_valid",
            )

        user = self.get_user(
            validated_token
        )

        # =====================================================
        # CSRF PROTECTION
        # =====================================================
        #
        # JWT is stored in an HttpOnly cookie.
        # Therefore the browser automatically sends it.
        #
        # Unsafe requests must also provide a valid
        # X-CSRFToken header.
        #

        if request.method not in (
            "GET",
            "HEAD",
            "OPTIONS",
            "TRACE",
        ):

            enforce_csrf(request)

        return (
            user,
            validated_token,
        )

    def get_user(self, validated_token):

        user = super().get_user(
            validated_token
        )

        profile = getattr(
            user,
            "profile",
            None,
        )

        if profile is None:

            raise AuthenticationFailed(
                "User profile not found.",
                code="profile_not_found",
            )

        token_version = (
            validated_token.get(
                "session_version"
            )
        )

        if token_version is None:

            raise AuthenticationFailed(
                "Invalid session.",
                code="invalid_session",
            )

        try:

            token_version = int(
                token_version
            )

        except (
            TypeError,
            ValueError,
        ):

            raise AuthenticationFailed(
                "Invalid session.",
                code="invalid_session",
            )

        if (
            token_version
            != profile.session_version
        ):

            raise AuthenticationFailed(
                "Session has been revoked.",
                code="session_revoked",
            )

        return user