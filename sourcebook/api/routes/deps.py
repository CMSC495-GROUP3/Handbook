"""Shared FastAPI dependencies: JWT verification, and the HR-only check on top."""

import hmac
import os

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from sourcebook.api.routes.auth import (
    FINGERPRINT_HEX_LEN,
    HR_PASSWORD_HASH_VAR,
    PASSWORD_HASH_VARS,
    credential_fingerprint,
)
from sourcebook.api.tokens import cred_claim, decode_claims

bearer_scheme = HTTPBearer()

# Membership check before any os.getenv(cred): a JWT must not pick an arbitrary
# environment variable. Tuple membership is fine at this size; the frozenset
# makes the allowlist intent obvious at the call site.
_PASSWORD_HASH_VAR_NAMES = frozenset(PASSWORD_HASH_VARS)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_auth(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> str:
    """The token's ``cred`` claim, once the token is shown to be current. Else 401."""
    payload = decode_claims(credentials.credentials)
    if payload is None:
        raise _unauthorized()

    cred = cred_claim(payload)
    fingerprint = payload.get("fingerprint")
    # Missing fingerprint (legacy tokens) and non-strings are the same failure:
    # the session is not bound to a currently configured hash. Length must match
    # before compare_digest so a malformed claim cannot turn into a 500.
    if cred is None or not isinstance(fingerprint, str):
        raise _unauthorized()
    if len(fingerprint) != FINGERPRINT_HEX_LEN:
        raise _unauthorized()
    if cred not in _PASSWORD_HASH_VAR_NAMES:
        raise _unauthorized()

    current_hash = os.getenv(cred, "")
    if not current_hash:
        raise _unauthorized()

    expected = credential_fingerprint(current_hash)
    if not hmac.compare_digest(fingerprint, expected):
        raise _unauthorized()
    return cred


# For the OpenAPI document: routes behind require_hr can answer 403.
HR_ONLY_RESPONSES = {403: {"description": "Signed in, but not with the HR password."}}


def require_hr(cred: str = Depends(require_auth)) -> None:
    """Pass only a session opened with the HR password (issue #290).

    HR Requests and What People Ask show questions employees typed, so the
    shared password is not enough for them. An expired or rotated token is
    still a 401 from require_auth; a current token from another password is a
    403, so the web app can tell "sign in again" from "not yours to open".
    """
    if cred != HR_PASSWORD_HASH_VAR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Human Resources sign-in required.",
        )
