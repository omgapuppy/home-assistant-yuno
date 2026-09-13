"""Yuno Android 4.3 authentication, shared by Home Assistant and the setup helper.

Bare RSA on Android uses Bouncy Castle NoPadding, not desktop Java's PKCS1
padding. Preserve that wire format for this existing HTTPS API only.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass

BASE_URL = "https://appbillpay.yunoenergy.ie:2015"
ORIGIN_ID = "63"
BASIC_CLIENT = "PPP-SA-BP-Prod:a_}@'u2Bn4):"
SIGNATURE_SALT = "mEwg_85Rt"
RSA_MODULUS = int(
    "b04a885944e16d75e1ecde42b64cb522862bc7ba789a69f3dbb0e8a9e1e3bd0a"
    "d971891d69fa26e8538c22a472b0fa7092fb642f8fdef200ebe7037b2fd200b1",
    16,
)
RSA_EXPONENT = 65537


def encrypt_credential(plaintext: str) -> str:
    """Encode a credential exactly like the Android app, using its public key."""
    encoded = plaintext.encode("utf-8")
    size = (RSA_MODULUS.bit_length() + 7) // 8
    value = int.from_bytes(encoded, "big")
    if len(encoded) > size or value >= RSA_MODULUS:
        raise ValueError("Credential is too long for the Yuno app's login format")
    encrypted = pow(value, RSA_EXPONENT, RSA_MODULUS).to_bytes(size, "big")
    return base64.b64encode(encrypted).decode("ascii")


def signature(payload: str) -> str:
    """Sign the exact POST body or GET path using the app's wire format."""
    inner = hashlib.sha1(payload.encode("utf-8")).hexdigest()
    outer = hashlib.sha1((inner + SIGNATURE_SALT).encode("utf-8")).hexdigest()
    return f"{ORIGIN_ID}:{outer}"


@dataclass(frozen=True, repr=False)
class AuthConfig:
    """Reusable login values. These grant account access and must remain private."""

    encrypted_email: str
    encrypted_password: str
    basic_authorization: str
    origin_id: str
    login_signature: str
    usage_signature: str
    login_body: str | None = None

    @classmethod
    def from_account_credentials(cls, email: str, password: str) -> AuthConfig:
        """Derive app login values without retaining the plaintext password."""
        email = email.strip().lower()
        if not email or not password:
            raise ValueError("Email and password are required")
        return cls.from_encrypted_credentials(
            encrypt_credential(email), encrypt_credential(password)
        )

    @classmethod
    def from_encrypted_credentials(
        cls, encrypted_email: str, encrypted_password: str
    ) -> AuthConfig:
        """Rebuild signed requests from the saved app credentials."""
        # Home Assistant supplies a compact JSON serializer to aiohttp.
        # Match it so these fields also work in the original integration.
        body = json.dumps(
            {
                "email": encrypted_email,
                "password": encrypted_password,
                "isPersistent": True,
            },
            separators=(",", ":"),
        )
        return cls(
            encrypted_email=encrypted_email,
            encrypted_password=encrypted_password,
            basic_authorization="Basic " + base64.b64encode(BASIC_CLIENT.encode()).decode(),
            origin_id=ORIGIN_ID,
            login_signature=signature(body),
            usage_signature=signature("/api/bill/electricityUsage"),
            login_body=body,
        )

    @classmethod
    def from_basic_credentials(
        cls,
        *,
        encrypted_email: str,
        encrypted_password: str,
        basic_username: str,
        basic_password: str,
        origin_id: str,
        login_signature: str,
        usage_signature: str,
    ) -> AuthConfig:
        """Build a legacy auth config from captured Basic credentials."""
        raw = f"{basic_username}:{basic_password}".encode()
        return cls(
            encrypted_email=encrypted_email,
            encrypted_password=encrypted_password,
            basic_authorization=f"Basic {base64.b64encode(raw).decode()}",
            origin_id=origin_id,
            login_signature=login_signature,
            usage_signature=usage_signature,
        )

    def setup_values(self) -> dict[str, str]:
        """Return the six fields accepted by the original integration."""
        return {
            "encrypted_email": self.encrypted_email,
            "encrypted_password": self.encrypted_password,
            "basic_authorization": self.basic_authorization,
            "origin_id": self.origin_id,
            "login_signature": self.login_signature,
            "usage_signature": self.usage_signature,
        }
