"""Shared-secret auth for incoming client requests.

main.py's startup check refuses to run the server at all if SERVER_API_KEY
is empty, so by the time require_api_key() runs it's guaranteed non-empty --
this still checks defensively rather than trusting that invariant blindly.
"""

import hmac

from fastapi import Header, HTTPException, status

import config


def require_api_key(x_api_key: str = Header(default="", alias="X-API-Key")) -> None:
    if not config.SERVER_API_KEY:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "server is missing SERVER_API_KEY")
    if not hmac.compare_digest(x_api_key, config.SERVER_API_KEY):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or missing X-API-Key header")
