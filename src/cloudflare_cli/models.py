"""Domain configuration models shared by the API adapters."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AccountConfig:
    """Credentials and account metadata for one Cloudflare account."""

    name: str
    account_id: str | None
    api_token: str | None
    api_key: str | None = None
    email: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_endpoint: str | None = None
    s3_region: str = "auto"
    s3_session_token: str | None = None

    def headers(self) -> dict[str, str]:
        if self.api_token:
            return {"Authorization": f"Bearer {self.api_token}"}
        if self.api_key and self.email:
            return {"X-Auth-Key": self.api_key, "X-Auth-Email": self.email}
        raise ValueError(f"Account {self.name!r} has no usable credentials")


@dataclass(frozen=True, slots=True)
class CloudflareConfig:
    """Resolved configuration with a default account."""

    accounts: Mapping[str, AccountConfig]
    default_account: str

    def account(self, name: str | None = None) -> AccountConfig:
        selected = name or self.default_account
        try:
            return self.accounts[selected]
        except KeyError as error:
            available = ", ".join(sorted(self.accounts)) or "none"
            raise ValueError(
                f"Unknown account {selected!r}; available accounts: {available}"
            ) from error
