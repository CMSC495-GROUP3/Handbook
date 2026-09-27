"""Shared-password login and bearer enforcement."""

import json
import logging
import os
import re
from datetime import timedelta

import bcrypt
import pytest
from conftest import HR_TEST_PASSWORD, TEST_PASSWORD

from sourcebook.api.routes import auth as auth_routes
from sourcebook.api.tokens import decode_claims


def _cost4_hash() -> str:
    return bcrypt.hashpw(TEST_PASSWORD.encode(), bcrypt.gensalt(4)).decode()


def test_login_issues_a_usable_token(client):
    response = client.post("/api/auth/login", json={"password": TEST_PASSWORD})
    assert response.status_code == 200
    token = response.json()["access_token"]
    assert (
        client.get("/api/conversations", headers={"Authorization": f"Bearer {token}"}).status_code
        == 200
    )


def test_wrong_password_is_rejected(client):
    assert client.post("/api/auth/login", json={"password": "nope"}).status_code == 401


SECOND_PASSWORD = "professor-review-password"


def _second_hash() -> str:
    return bcrypt.hashpw(SECOND_PASSWORD.encode(), bcrypt.gensalt(4)).decode()


def test_second_password_logs_in_alongside_the_first(client, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD_HASH_2", _second_hash())
    for password in (TEST_PASSWORD, SECOND_PASSWORD):
        response = client.post("/api/auth/login", json={"password": password})
        assert response.status_code == 200, password
        token = response.json()["access_token"]
        assert (
            client.get(
                "/api/conversations", headers={"Authorization": f"Bearer {token}"}
            ).status_code
            == 200
        )
    assert client.post("/api/auth/login", json={"password": "nope"}).status_code == 401


def test_second_password_is_rejected_when_not_configured(client, monkeypatch):
    monkeypatch.delenv("APP_PASSWORD_HASH_2", raising=False)
    assert client.post("/api/auth/login", json={"password": SECOND_PASSWORD}).status_code == 401


def test_empty_second_hash_means_one_password(client, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD_HASH_2", "")
    assert client.post("/api/auth/login", json={"password": TEST_PASSWORD}).status_code == 200
    assert client.post("/api/auth/login", json={"password": SECOND_PASSWORD}).status_code == 401


def test_second_hash_alone_does_not_replace_the_first(client, monkeypatch, caplog):
    monkeypatch.setenv("APP_PASSWORD_HASH", "")
    monkeypatch.setenv("APP_PASSWORD_HASH_2", _second_hash())
    with caplog.at_level(logging.ERROR, logger="sourcebook.api.routes.auth"):
        response = client.post("/api/auth/login", json={"password": SECOND_PASSWORD})
    assert response.status_code == 500
    assert "APP_PASSWORD_HASH is not configured" in caplog.text


def test_malformed_second_hash_is_a_server_error(client, monkeypatch, caplog):
    # A broken second hash must not quietly fall back to the first password.
    monkeypatch.setenv("APP_PASSWORD_HASH_2", "not-a-bcrypt-hash")
    with caplog.at_level(logging.ERROR, logger="sourcebook.api.routes.auth"):
        response = client.post("/api/auth/login", json={"password": TEST_PASSWORD})
    assert response.status_code == 500
    assert "APP_PASSWORD_HASH_2 is not a valid bcrypt hash" in caplog.text


@pytest.mark.parametrize(
    ("password", "variable"),
    [
        (TEST_PASSWORD, "APP_PASSWORD_HASH"),
        (SECOND_PASSWORD, "APP_PASSWORD_HASH_2"),
        (HR_TEST_PASSWORD, "HR_PASSWORD_HASH"),
    ],
)
def test_login_records_which_password_was_used(client, monkeypatch, caplog, password, variable):
    # Both passwords open the same door; the log line and the claim are the
    # only way to tell a reviewer's session from the team's afterwards.
    monkeypatch.setenv("APP_PASSWORD_HASH_2", _second_hash())
    with caplog.at_level(logging.INFO, logger="sourcebook.api.routes.auth"):
        response = client.post("/api/auth/login", json={"password": password})
    assert response.status_code == 200
    claims = decode_claims(response.json()["access_token"])
    assert claims is not None
    assert re.fullmatch(r"[0-9a-f]{32}", claims["sub"])
    assert claims["cred"] == variable
    assert claims["fingerprint"] == auth_routes.credential_fingerprint(os.environ[variable])
    assert len(claims["fingerprint"]) == auth_routes.FINGERPRINT_HEX_LEN
    assert f"Login with {variable}" in caplog.text
    assert password not in caplog.text
    assert os.environ[variable] not in response.text
    assert os.environ[variable] not in caplog.text
    assert os.environ[variable] not in claims["fingerprint"]


def test_rotated_second_hash_rejects_its_tokens(client, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD_HASH_2", _second_hash())
    token = client.post("/api/auth/login", json={"password": SECOND_PASSWORD}).json()[
        "access_token"
    ]
    assert (
        client.get("/api/conversations", headers={"Authorization": f"Bearer {token}"}).status_code
        == 200
    )

    monkeypatch.setenv("APP_PASSWORD_HASH_2", _second_hash())
    assert (
        client.get("/api/conversations", headers={"Authorization": f"Bearer {token}"}).status_code
        == 401
    )


def test_rotating_second_hash_does_not_affect_primary_tokens(client, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD_HASH_2", _second_hash())
    primary = client.post("/api/auth/login", json={"password": TEST_PASSWORD}).json()[
        "access_token"
    ]
    secondary = client.post("/api/auth/login", json={"password": SECOND_PASSWORD}).json()[
        "access_token"
    ]

    monkeypatch.setenv("APP_PASSWORD_HASH_2", _second_hash())
    assert (
        client.get("/api/conversations", headers={"Authorization": f"Bearer {primary}"}).status_code
        == 200
    )
    assert (
        client.get(
            "/api/conversations", headers={"Authorization": f"Bearer {secondary}"}
        ).status_code
        == 401
    )


def test_legacy_token_without_fingerprint_is_rejected(client):
    token = auth_routes.create_access_token(
        {"sub": "user", "cred": "APP_PASSWORD_HASH"},
        timedelta(hours=1),
    )
    assert (
        client.get("/api/conversations", headers={"Authorization": f"Bearer {token}"}).status_code
        == 401
    )


def test_malformed_fingerprint_length_is_rejected(client):
    token = auth_routes.create_access_token(
        {
            "sub": "user",
            "cred": "APP_PASSWORD_HASH",
            "fingerprint": "short",
        },
        timedelta(hours=1),
    )
    assert (
        client.get("/api/conversations", headers={"Authorization": f"Bearer {token}"}).status_code
        == 401
    )


def test_token_cred_outside_allowlist_is_rejected(client, monkeypatch):
    # A forged cred must not become an os.getenv selector for an arbitrary name.
    monkeypatch.setenv("PATH", os.environ.get("PATH", "/usr/bin"))
    token = auth_routes.create_access_token(
        {
            "sub": "user",
            "cred": "PATH",
            "fingerprint": auth_routes.credential_fingerprint(os.environ["PATH"]),
        },
        timedelta(hours=1),
    )
    assert (
        client.get("/api/conversations", headers={"Authorization": f"Bearer {token}"}).status_code
        == 401
    )


def test_unset_second_hash_rejects_its_tokens(client, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD_HASH_2", _second_hash())
    token = client.post("/api/auth/login", json={"password": SECOND_PASSWORD}).json()[
        "access_token"
    ]
    monkeypatch.delenv("APP_PASSWORD_HASH_2", raising=False)
    assert (
        client.get("/api/conversations", headers={"Authorization": f"Bearer {token}"}).status_code
        == 401
    )


# validate_password_hashes is what main.py runs at import, so these pin the
# startup rule without re-importing the app.
def test_startup_rejects_a_malformed_second_hash(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD_HASH_2", "not-a-bcrypt-hash")
    with pytest.raises(auth_routes.PasswordHashError, match="APP_PASSWORD_HASH_2"):
        auth_routes.validate_password_hashes()


def test_startup_requires_the_first_hash_even_with_a_second(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD_HASH", "")
    monkeypatch.setenv("APP_PASSWORD_HASH_2", _second_hash())
    with pytest.raises(auth_routes.PasswordHashError, match="APP_PASSWORD_HASH is not configured"):
        auth_routes.validate_password_hashes()


def test_startup_accepts_one_or_two_well_formed_hashes(monkeypatch):
    monkeypatch.delenv("APP_PASSWORD_HASH_2", raising=False)
    monkeypatch.delenv("HR_PASSWORD_HASH", raising=False)
    assert [name for name, _ in auth_routes.validate_password_hashes()] == ["APP_PASSWORD_HASH"]
    monkeypatch.setenv("APP_PASSWORD_HASH_2", _second_hash())
    assert [name for name, _ in auth_routes.validate_password_hashes()] == [
        "APP_PASSWORD_HASH",
        "APP_PASSWORD_HASH_2",
    ]


# ── The HR password ───────────────────────────────────────────────────────────


def test_hr_password_opens_the_employee_routes_too(client):
    token = client.post("/api/auth/login", json={"password": HR_TEST_PASSWORD}).json()[
        "access_token"
    ]
    assert (
        client.get("/api/conversations", headers={"Authorization": f"Bearer {token}"}).status_code
        == 200
    )


def test_hr_password_is_rejected_when_not_configured(client, monkeypatch):
    monkeypatch.delenv("HR_PASSWORD_HASH", raising=False)
    assert client.post("/api/auth/login", json={"password": HR_TEST_PASSWORD}).status_code == 401
    assert client.post("/api/auth/login", json={"password": TEST_PASSWORD}).status_code == 200


def test_the_shared_password_wins_when_hr_reuses_it(client, monkeypatch):
    """An HR hash of the shared password must not make every employee HR."""
    monkeypatch.setenv("HR_PASSWORD_HASH", _cost4_hash())
    token = client.post("/api/auth/login", json={"password": TEST_PASSWORD}).json()["access_token"]
    assert decode_claims(token)["cred"] == "APP_PASSWORD_HASH"


def test_hr_wins_when_it_shares_the_second_hash(client, monkeypatch):
    """The course deployment gives the reviewer's password HR access this way."""
    second = _second_hash()
    monkeypatch.setenv("APP_PASSWORD_HASH_2", second)
    monkeypatch.setenv("HR_PASSWORD_HASH", second)
    token = client.post("/api/auth/login", json={"password": SECOND_PASSWORD}).json()[
        "access_token"
    ]
    assert decode_claims(token)["cred"] == "HR_PASSWORD_HASH"
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/reports/gaps", headers=headers).status_code == 200


def test_malformed_hr_hash_is_a_server_error(client, monkeypatch, caplog):
    monkeypatch.setenv("HR_PASSWORD_HASH", "not-a-bcrypt-hash")
    with caplog.at_level(logging.ERROR, logger="sourcebook.api.routes.auth"):
        response = client.post("/api/auth/login", json={"password": TEST_PASSWORD})
    assert response.status_code == 500
    assert "HR_PASSWORD_HASH is not a valid bcrypt hash" in caplog.text


def test_hr_hash_alone_does_not_replace_the_first(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD_HASH", "")
    with pytest.raises(auth_routes.PasswordHashError, match="APP_PASSWORD_HASH is not configured"):
        auth_routes.validate_password_hashes()


def test_startup_accepts_all_three_hashes(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD_HASH_2", _second_hash())
    assert [name for name, _ in auth_routes.validate_password_hashes()] == [
        "APP_PASSWORD_HASH",
        "HR_PASSWORD_HASH",
        "APP_PASSWORD_HASH_2",
    ]


def test_rotated_hr_hash_rejects_its_tokens(client, monkeypatch):
    token = client.post("/api/auth/login", json={"password": HR_TEST_PASSWORD}).json()[
        "access_token"
    ]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/escalations", headers=headers).status_code == 200

    monkeypatch.setenv("HR_PASSWORD_HASH", _cost4_hash())
    assert client.get("/api/escalations", headers=headers).status_code == 401
    assert client.get("/api/conversations", headers=headers).status_code == 401


def test_unset_hr_hash_rejects_its_tokens(client, monkeypatch):
    token = client.post("/api/auth/login", json={"password": HR_TEST_PASSWORD}).json()[
        "access_token"
    ]
    monkeypatch.delenv("HR_PASSWORD_HASH", raising=False)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/escalations", headers=headers).status_code == 401
    assert client.get("/api/reports/gaps", headers=headers).status_code == 401


@pytest.mark.parametrize("cred", ["APP_PASSWORD_HASH", "APP_PASSWORD_HASH_2"])
def test_employee_logins_cannot_reach_the_hr_routes(client, monkeypatch, cred):
    monkeypatch.setenv("APP_PASSWORD_HASH_2", _second_hash())
    password = TEST_PASSWORD if cred == "APP_PASSWORD_HASH" else SECOND_PASSWORD
    token = client.post("/api/auth/login", json={"password": password}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/escalations", headers=headers).status_code == 403
    assert client.get("/api/reports/gaps", headers=headers).status_code == 403


def test_unconfigured_password_is_a_server_error(client, monkeypatch, caplog):
    monkeypatch.setenv("APP_PASSWORD_HASH", "")
    with caplog.at_level(logging.ERROR, logger="sourcebook.api.routes.auth"):
        response = client.post("/api/auth/login", json={"password": TEST_PASSWORD})
    assert response.status_code == 500
    assert "APP_PASSWORD_HASH is not configured" in caplog.text


def test_malformed_password_hash_is_a_server_error(client, monkeypatch, caplog):
    monkeypatch.setenv("APP_PASSWORD_HASH", "not-a-bcrypt-hash")
    with caplog.at_level(logging.ERROR, logger="sourcebook.api.routes.auth"):
        response = client.post("/api/auth/login", json={"password": TEST_PASSWORD})
    assert response.status_code == 500
    assert "APP_PASSWORD_HASH is not a valid bcrypt hash" in caplog.text


@pytest.mark.parametrize("damage", ["\n", " "], ids=["trailing-newline", "trailing-space"])
def test_hash_with_trailing_whitespace_does_not_silently_lock_out(
    client, monkeypatch, caplog, damage
):
    # checkpw returns False for these, which would read as a wrong password.
    monkeypatch.setenv("APP_PASSWORD_HASH", _cost4_hash() + damage)
    with caplog.at_level(logging.ERROR, logger="sourcebook.api.routes.auth"):
        response = client.post("/api/auth/login", json={"password": TEST_PASSWORD})
    assert response.status_code == 500
    assert "not a valid bcrypt hash" in caplog.text


def test_truncated_hash_is_a_server_error_not_a_lockout(client, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD_HASH", _cost4_hash()[:-1])
    assert client.post("/api/auth/login", json={"password": TEST_PASSWORD}).status_code == 500


def test_lone_surrogate_password_is_rejected_not_a_server_error(client, caplog):
    # json.loads accepts a lone surrogate; str.encode refuses it with a
    # UnicodeEncodeError, which subclasses ValueError.
    body = json.dumps({"password": "\ud800abc"}).encode("utf-8", "surrogatepass")
    with caplog.at_level(logging.ERROR, logger="sourcebook.api.routes.auth"):
        response = client.post(
            "/api/auth/login", content=body, headers={"content-type": "application/json"}
        )
    assert response.status_code in (401, 422)
    assert "APP_PASSWORD_HASH" not in caplog.text


def test_overlong_password_is_rejected_not_a_server_error(client, monkeypatch):
    """bcrypt 5 raises past 72 bytes where 4 truncated. Pin the 401 on either."""
    real = bcrypt.checkpw

    def strict(password: bytes, hashed: bytes) -> bool:
        if len(password) > auth_routes.BCRYPT_MAX_PASSWORD_BYTES:
            raise ValueError("password cannot be longer than 72 bytes")
        return real(password, hashed)

    monkeypatch.setattr(auth_routes.bcrypt, "checkpw", strict)
    assert client.post("/api/auth/login", json={"password": "a" * 100}).status_code == 401


def test_overlong_correct_password_still_logs_in(client, monkeypatch):
    """Truncation, not rejection: a deployment with a long password keeps working."""
    long_password = "p" * 80
    monkeypatch.setenv(
        "APP_PASSWORD_HASH",
        bcrypt.hashpw(long_password.encode()[:72], bcrypt.gensalt(4)).decode(),
    )
    assert client.post("/api/auth/login", json={"password": long_password}).status_code == 200


@pytest.mark.parametrize("prefix", ["$2a$", "$2b$", "$2y$"])
def test_login_accepts_legacy_bcrypt_prefixes(client, monkeypatch, prefix):
    monkeypatch.setenv("APP_PASSWORD_HASH", prefix + _cost4_hash()[4:])
    assert client.post("/api/auth/login", json={"password": TEST_PASSWORD}).status_code == 200


@pytest.mark.parametrize(
    "value",
    ["", "ci-placeholder", "not-a-bcrypt-hash", "$2b$99$" + "a" * 53, "$2b$04$" + "a" * 52],
)
def test_is_bcrypt_hash_rejects_bad_shapes(value):
    assert not auth_routes.is_bcrypt_hash(value)


def test_protected_routes_reject_missing_and_bad_tokens(client):
    assert client.get("/api/conversations").status_code in (401, 403)
    assert (
        client.get("/api/conversations", headers={"Authorization": "Bearer junk"}).status_code
        == 401
    )


def test_health_and_config_are_public(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    assert "similarity_threshold" in client.get("/api/config").json()


# ── Owner ids (issue #290, item 4) ────────────────────────────────────────────


def test_login_puts_the_browsers_client_id_in_sub(client):
    client_id = "ab" * 16
    response = client.post(
        "/api/auth/login", json={"password": TEST_PASSWORD, "client_id": client_id}
    )
    assert decode_claims(response.json()["access_token"])["sub"] == client_id


def test_login_without_a_client_id_mints_a_fresh_owner(client):
    subs = {
        decode_claims(
            client.post("/api/auth/login", json={"password": TEST_PASSWORD}).json()["access_token"]
        )["sub"]
        for _ in range(2)
    }
    assert len(subs) == 2


@pytest.mark.parametrize("client_id", ["AB" * 16, "ab" * 15, "../etc/passwd", ""])
def test_login_rejects_a_malformed_client_id(client, client_id):
    response = client.post(
        "/api/auth/login", json={"password": TEST_PASSWORD, "client_id": client_id}
    )
    assert response.status_code == 422


def test_a_token_from_before_owners_is_rejected(client):
    """Tokens issued before this change carry sub "user". Their holders sign in again."""
    token = auth_routes.create_access_token(
        {
            "sub": "user",
            "cred": "APP_PASSWORD_HASH",
            "fingerprint": auth_routes.credential_fingerprint(os.environ["APP_PASSWORD_HASH"]),
        },
        timedelta(hours=1),
    )
    response = client.get("/api/conversations", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
