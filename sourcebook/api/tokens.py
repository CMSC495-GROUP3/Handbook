"""JWT signing and verification, shared by login, the auth dependency, and the
rate-limit log line.

One module knows the algorithm and where the secret comes from, so the three
callers cannot drift (issue #146). The secret is read on every call rather
than at import: main.py refuses to start without it, so the read never fails
in a running process, and reading late means a test or the load-test stub can
set the variable without re-importing the package.

This module imports nothing from the rest of the API package on purpose.
auth.py imports the limiter and deps.py imports auth.py, so anything they both
need has to sit below both of them.
"""

import os
import re

import jwt
from fastapi.security.utils import get_authorization_scheme_param

_ALGORITHM = "HS256"

# ``cred`` names the environment variable holding the password hash a session
# was opened with (APP_PASSWORD_HASH, APP_PASSWORD_HASH_2, HR_PASSWORD_HASH, or
# MANAGER_PASSWORD_HASH).
# Anything not shaped like a variable name is not a cred, whatever signed it:
# the auth dependency would reject it against its allowlist, and the 429 log
# line must never receive a value that can carry a newline (issue #153).
_CRED_SHAPE = re.compile(r"[A-Z][A-Z0-9_]{0,63}")


def _secret_key() -> str | None:
    """The signing secret as currently set in the environment, or None."""
    return os.getenv("JWT_SECRET_KEY")


def encode_token(claims: dict) -> str:
    secret = _secret_key()
    if not secret:
        raise RuntimeError("JWT_SECRET_KEY is not set; cannot sign a token")
    return jwt.encode(claims, secret, algorithm=_ALGORITHM)


def decode_claims(token: str) -> dict | None:
    """Return the verified claims of a token, or None.

    None covers every way a token can fail: no secret configured, wrong
    signature, expired, missing or malformed ``exp`` claim, or not a JWT
    at all.
    Callers decide what None means: require_auth answers 401, the 429 log
    line writes "unknown".

    ``exp`` is required, not merely checked when present: every token this
    app issues carries one, and a token without it would otherwise verify
    forever (issue #152).
    """
    secret = _secret_key()
    if not secret:
        return None
    try:
        return jwt.decode(token, secret, algorithms=[_ALGORITHM], options={"require": ["exp"]})
    except (jwt.PyJWTError, TypeError):
        # TypeError: PyJWT casts ``exp`` and ``nbf`` with int() and only catches
        # ValueError, so a signed ``exp: null`` (or a list, or a dict) escapes
        # as TypeError rather than a claims error. Same answer: not a token.
        return None


def cred_claim(claims: dict | None) -> str | None:
    """The ``cred`` claim, or None.

    None when the claim is absent, not a string, or not shaped like an
    environment-variable name (see ``_CRED_SHAPE``).
    """
    if not claims:
        return None
    cred = claims.get("cred")
    if not isinstance(cred, str) or not _CRED_SHAPE.fullmatch(cred):
        return None
    return cred


def bearer_token(authorization: str | None) -> str | None:
    """The token in an ``Authorization: Bearer ...`` header value, or None.

    Parsed with the same helper FastAPI's ``HTTPBearer`` uses, so a header
    that ``require_auth`` accepts (scheme in any case, surrounding whitespace
    stripped) yields the same token here. An empty token is None, not "".
    """
    scheme, token = get_authorization_scheme_param(authorization)
    if scheme.lower() != "bearer" or not token:
        return None
    return token
