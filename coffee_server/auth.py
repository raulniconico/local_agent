"""Two independent things guard this server, and they answer different questions.

`require_api_key` / `require_read_key` ask "is this one of our clients?" -- a
shared secret compiled into the APK. It is not a strong secret (anyone can
decompile an APK) and was never meant to be: it keeps casual traffic off the
endpoint and lets a leak be rotated per endpoint class.

`require_account` asks "*which user* is this?" -- a Google ID token, verified
against Google's own keys. This is the one that carries weight, because it is
what metering, quota and the abuse cutoff key off (specs/legal-accounts.md
rules 58-60). The API key alone must never be enough to reach a metered
endpoint: a key extracted from the APK would then be an anonymous, unlimited
claim on the developer's provider bill.

main.py's startup check refuses to run the server at all if SERVER_API_KEY is
empty, so by the time require_api_key() runs it's guaranteed non-empty -- this
still checks defensively rather than trusting that invariant blindly.
"""

import hmac
import logging

from fastapi import Header, HTTPException, status

import accounts
import config

logger = logging.getLogger("server.auth")


def require_api_key(x_api_key: str = Header(default="", alias="X-API-Key")) -> None:
    if not config.SERVER_API_KEY:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "server is missing SERVER_API_KEY")
    if not hmac.compare_digest(x_api_key, config.SERVER_API_KEY):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or missing X-API-Key header")


def require_read_key(x_api_key: str = Header(default="", alias="X-API-Key")) -> None:
    """The catalogue/news key. Accepts the metered key too, so a single-key
    deployment and a split-key one behave the same for read traffic."""
    if not config.READ_API_KEY:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "server is missing READ_API_KEY")
    if hmac.compare_digest(x_api_key, config.READ_API_KEY):
        return
    if config.SERVER_API_KEY and hmac.compare_digest(x_api_key, config.SERVER_API_KEY):
        return
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or missing X-API-Key header")


def _verify_google_id_token_claims(token: str) -> dict:
    """The verified claim set, or raises HTTPException.

    Verified with Google's own library rather than by hand: signature against
    Google's rotating JWKS, issuer, expiry, and -- the one everybody forgets --
    **audience**. Without the audience check any valid Google ID token issued to
    any app in the world would authenticate here, which is not authentication.
    """
    if not config.GOOGLE_CLIENT_IDS:
        # Fail closed. A deployment with no audience configured cannot verify
        # anything, and serving metered endpoints unauthenticated is the exact
        # failure this whole module exists to prevent.
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "account auth is not configured on this server (GOOGLE_CLIENT_IDS unset)",
        )

    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token as google_id_token
    except ImportError as exc:  # pragma: no cover - dependency is in requirements.txt
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, f"google-auth is not installed: {exc}"
        ) from exc

    request = google_requests.Request()
    for client_id in config.GOOGLE_CLIENT_IDS:
        try:
            claims = google_id_token.verify_oauth2_token(token, request, client_id)
        except ValueError:
            continue
        if not claims.get("sub"):
            break
        return claims

    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid Google ID token")


def sync_allowed(authorization: str = Header(default="", alias="Authorization")) -> str:
    """FastAPI dependency for the test-only sync endpoints: returns the caller's
    `sub`, or refuses.

    THE GATE IS HERE AND NOT IN THE APP, deliberately. The Android client never
    learns its own email address -- `account/GoogleAuth.kt` reads `sub` out of
    the ID token and drops the rest, because `legal-accounts.md` rule 60 keeps
    email addresses off the device. The email claim only exists somewhere that
    already verifies the token, which is here. A client-side allowlist would
    also be no gate at all: anyone could rebuild the app without it, whereas
    this one is checked against a signature Google issued.

    404, NOT 403, WHEN THE FEATURE IS OFF. With `SYNC_ALLOWED_EMAILS` empty --
    the default, and what production runs -- these endpoints must be
    indistinguishable from endpoints that do not exist; a 403 would advertise a
    private feature to everyone who probed for it.

    `email_verified` is required as well as `email`: an unverified claim is a
    string the account holder typed, and matching an allowlist against it would
    let anyone who typed the right address in sync as the developer.
    """
    if not config.SYNC_ALLOWED_EMAILS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "missing Authorization: Bearer <Google ID token>",
        )

    claims = _verify_google_id_token_claims(token)
    email = (claims.get("email") or "").strip().lower()
    if not email or not claims.get("email_verified"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    if email not in config.SYNC_ALLOWED_EMAILS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")

    sub = claims["sub"]
    # `unlimited` IS PASSED HERE TOO, AND OMITTING IT WAS A BUG FOR THE LENGTH
    # OF ONE EDIT. `touch` writes the flag on every call so the allowlist stays
    # authoritative -- which means a `touch` that does not compute it writes
    # the default, `False`. Syncing would have silently cleared the developer's
    # own quota exemption until their next metered request re-set it. Any new
    # caller of `touch` has to answer this question; there is no safe default.
    accounts.touch(sub, unlimited=_quota_exempt(claims))
    return sub


def require_account(authorization: str = Header(default="", alias="Authorization")) -> str:
    """FastAPI dependency returning the caller's Google `sub`.

    Every metered endpoint depends on this *and* on require_api_key. The `sub`
    it returns is the only user identifier that exists anywhere in this
    codebase; it is pseudonymous personal data, never "anonymous" (rule 61).

    IT ALSO DECIDES THE QUOTA EXEMPTION, because this is the only place in a
    metered request where the verified claim set exists at all. `meter()` is
    handed a `sub` and nothing else, and re-verifying the token there to read
    an email would mean checking the same signature twice per request. So the
    email is matched here, the answer is written to the account row as a
    boolean, and `accounts.check_and_count` reads the boolean.

    `email_verified` is required, exactly as in `sync_allowed`: without it the
    address is a string the account holder typed, and anyone who typed the
    developer's address would get unlimited calls on the developer's bill.
    """
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "missing Authorization: Bearer <Google ID token>",
        )

    claims = _verify_google_id_token_claims(token)
    sub = claims["sub"]
    accounts.touch(sub, unlimited=_quota_exempt(claims))
    return sub


def _quota_exempt(claims: dict) -> bool:
    """Whether the daily cap should be lifted for this verified token.

    Fails closed on every doubt: an empty allowlist, an absent email claim, or
    an unverified one all mean "no". The cost of a wrong `False` is that the
    developer hits a limit on their own server; the cost of a wrong `True` is
    an unmetered stranger on a metered provider account.
    """
    if not config.QUOTA_EXEMPT_EMAILS:
        return False
    email = (claims.get("email") or "").strip().lower()
    if not email or not claims.get("email_verified"):
        return False
    return email in config.QUOTA_EXEMPT_EMAILS


def meter(sub: str, op: str) -> None:
    """Charges one call of `op` to `sub`, mapping the store's refusals onto the
    HTTP codes a client can act on: 429 means try later, 403 means stop."""
    try:
        accounts.check_and_count(sub, op)
    except accounts.RateLimitedError as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc
    except accounts.QuotaExceededError as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc
    except accounts.AccountBannedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
