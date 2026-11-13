"""Optional shared-token auth for the control API (pure helpers)."""

import hmac

HEADER_NAME = "X-API-Token"


def extract_token(headers):
    """Returns the token from `X-API-Token` or `Authorization: Bearer <t>`, else ''."""
    token = headers.get(HEADER_NAME)
    if token:
        return token.strip()
    auth = headers.get("Authorization", "")
    if auth[:7].lower() == "bearer ":
        return auth[7:].strip()
    return ""


def is_authorized(headers, expected):
    """No expected token configured means the API is open (backward compatible)."""
    if not expected:
        return True
    provided = extract_token(headers)
    return hmac.compare_digest(provided.encode(), expected.encode())
