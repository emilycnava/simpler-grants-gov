from datetime import datetime, timedelta, timezone

import jwt
import pytest

import src.auth.login_gov_jwt_auth as login_gov_jwt_auth
from src.auth.login_gov_jwt_auth import JwtValidationError, LoginGovConfig, validate_token

DEFAULT_CLIENT_ID = "urn:gov:unit-test"
DEFAULT_ISSUER = "http://localhost:3000"


@pytest.fixture
def login_gov_config(public_rsa_key):
    # Note this isn't session scoped so it gets remade
    # for every test in the event of changes to it
    return LoginGovConfig(
        LOGIN_GOV_PUBLIC_KEYS=[public_rsa_key],
        LOGIN_GOV_JWK_ENDPOINT="not_used",
        LOGIN_GOV_ENDPOINT=DEFAULT_ISSUER,
        LOGIN_GOV_CLIENT_ID=DEFAULT_CLIENT_ID,
    )


def create_jwt(
    user_id: str,
    email: str,
    expires_at: datetime,
    issued_at: datetime,
    not_before: datetime,
    private_key: str | bytes,
    issuer: str = DEFAULT_ISSUER,
    audience: str = DEFAULT_CLIENT_ID,
    acr: str = "urn:acr.login.gov:auth-only",
):
    payload = {
        "sub": user_id,
        "iss": issuer,
        "acr": acr,
        "aud": audience,
        "email": email,
        # The jwt encode function automatically turns these datetime
        # objects into a UTC timestamp integer
        "exp": expires_at,
        "iat": issued_at,
        "nbf": not_before,
        # These values aren't checked by anything at the moment
        # but are a part of the token from login.gov
        "jti": "abc123",
        "nonce": "abc123",
        "at_hash": "abc123",
        "c_hash": "abc123",
    }

    return jwt.encode(payload, private_key, algorithm="RS256")


def test_validate_token_happy_path(login_gov_config, private_rsa_key):
    user_id = "12345678-abc"
    email = "fake@mail.com"

    token = create_jwt(
        user_id=user_id,
        email=email,
        private_key=private_rsa_key,
        expires_at=datetime.now(tz=timezone.utc) + timedelta(days=30),
        issued_at=datetime.now(tz=timezone.utc) - timedelta(days=1),
        not_before=datetime.now(tz=timezone.utc) - timedelta(days=1),
    )

    login_gov_user = validate_token(token, login_gov_config)

    assert login_gov_user.user_id == user_id
    assert login_gov_user.email == email


def test_validate_token_expired(login_gov_config, private_rsa_key):
    token = create_jwt(
        user_id="abc123",
        email="mail@fake.com",
        private_key=private_rsa_key,
        expires_at=datetime.now(tz=timezone.utc) - timedelta(days=1),
        issued_at=datetime.now(tz=timezone.utc) - timedelta(days=30),
        not_before=datetime.now(tz=timezone.utc) - timedelta(days=30),
    )

    with pytest.raises(JwtValidationError, match="Expired Token"):
        validate_token(token, login_gov_config)


def test_validate_token_issued_at_future(login_gov_config, private_rsa_key):
    token = create_jwt(
        user_id="abc123",
        email="mail@fake.com",
        private_key=private_rsa_key,
        expires_at=datetime.now(tz=timezone.utc) + timedelta(days=1),
        issued_at=datetime.now(tz=timezone.utc) + timedelta(days=1),
        not_before=datetime.now(tz=timezone.utc) - timedelta(days=30),
    )

    with pytest.raises(JwtValidationError, match="Token not yet valid"):
        validate_token(token, login_gov_config)


def test_validate_token_not_before_future(login_gov_config, private_rsa_key):
    token = create_jwt(
        user_id="abc123",
        email="mail@fake.com",
        private_key=private_rsa_key,
        expires_at=datetime.now(tz=timezone.utc) + timedelta(days=30),
        issued_at=datetime.now(tz=timezone.utc) - timedelta(days=1),
        not_before=datetime.now(tz=timezone.utc) + timedelta(days=1),
    )

    with pytest.raises(JwtValidationError, match="Token not yet valid"):
        validate_token(token, login_gov_config)


def test_validate_token_unknown_issuer(login_gov_config, private_rsa_key):
    token = create_jwt(
        user_id="abc123",
        email="mail@fake.com",
        issuer="fred",
        private_key=private_rsa_key,
        expires_at=datetime.now(tz=timezone.utc) + timedelta(days=30),
        issued_at=datetime.now(tz=timezone.utc) - timedelta(days=1),
        not_before=datetime.now(tz=timezone.utc) - timedelta(days=1),
    )

    with pytest.raises(JwtValidationError, match="Unknown Issuer"):
        validate_token(token, login_gov_config)


def test_validate_token_unknown_audience(login_gov_config, private_rsa_key):
    token = create_jwt(
        user_id="abc123",
        email="mail@fake.com",
        audience="fred",
        private_key=private_rsa_key,
        expires_at=datetime.now(tz=timezone.utc) + timedelta(days=30),
        issued_at=datetime.now(tz=timezone.utc) - timedelta(days=1),
        not_before=datetime.now(tz=timezone.utc) - timedelta(days=1),
    )

    with pytest.raises(JwtValidationError, match="Unknown Audience"):
        validate_token(token, login_gov_config)


def test_validate_token_invalid_signature(login_gov_config, other_rsa_key_pair, monkeypatch):
    token = create_jwt(
        user_id="abc123",
        email="mail@fake.com",
        private_key=other_rsa_key_pair[0],  # Create it with a different key
        expires_at=datetime.now(tz=timezone.utc) + timedelta(days=30),
        issued_at=datetime.now(tz=timezone.utc) - timedelta(days=1),
        not_before=datetime.now(tz=timezone.utc) - timedelta(days=1),
    )

    # Need to override the refresh logic so it doesn't try to reach out to anything
    # We don't need to set the keys to anything else here.
    def override_method(config):
        pass

    monkeypatch.setattr(login_gov_jwt_auth, "_refresh_keys", override_method)

    with pytest.raises(
        JwtValidationError,
        match="Token could not be validated against any public keys from login.gov",
    ):
        validate_token(token, login_gov_config)


def test_something_with_the_refresh(login_gov_config, other_rsa_key_pair, monkeypatch):
    token = create_jwt(
        user_id="abc123",
        email="mail@fake.com",
        private_key=other_rsa_key_pair[0],  # Create it with a different key
        expires_at=datetime.now(tz=timezone.utc) + timedelta(days=30),
        issued_at=datetime.now(tz=timezone.utc) - timedelta(days=1),
        not_before=datetime.now(tz=timezone.utc) - timedelta(days=1),
    )

    def override_method(config):
        config.public_keys = [other_rsa_key_pair[1]]

    monkeypatch.setattr(login_gov_jwt_auth, "_refresh_keys", override_method)

    validate_token(token, login_gov_config)
