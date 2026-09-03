"""TOML configuration source and validation."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from cloudflare_cli.models import AccountConfig


def read_document(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    with path.open("rb") as handle:
        return tomllib.load(handle)


def accounts_from_document(document: dict[str, Any]) -> dict[str, AccountConfig]:
    raw_accounts = document.get("accounts", {})
    if not isinstance(raw_accounts, dict):
        raise ValueError("The [accounts] configuration must be a TOML table")
    accounts: dict[str, AccountConfig] = {}
    for name, raw in raw_accounts.items():
        if not isinstance(raw, dict):
            raise ValueError(f"Account {name!r} must be a TOML table")
        accounts[str(name)] = _account_from_values(str(name), raw)
    return accounts


def _account_from_values(name: str, values: dict[str, Any]) -> AccountConfig:
    allowed = {"account_id", "api_token", "api_key", "email", "s3"}
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"Unknown settings for account {name!r}: {sorted(unknown)}")
    s3 = values.get("s3", {})
    if not isinstance(s3, dict):
        raise ValueError(f"Account {name!r} s3 settings must be a TOML table")
    s3_values = _s3_values(name, s3)
    return AccountConfig(
        name=name,
        account_id=_optional_string(values.get("account_id")),
        api_token=_optional_string(values.get("api_token")),
        api_key=_optional_string(values.get("api_key")),
        email=_optional_string(values.get("email")),
        s3_access_key_id=s3_values["s3_access_key_id"],
        s3_secret_access_key=s3_values["s3_secret_access_key"],
        s3_endpoint=s3_values["s3_endpoint"],
        s3_region=s3_values["s3_region"] or "auto",
        s3_session_token=s3_values["s3_session_token"],
    )


def _s3_values(name: str, values: dict[str, Any]) -> dict[str, str | None]:
    allowed = {
        "access_key_id",
        "secret_access_key",
        "endpoint",
        "region",
        "session_token",
    }
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"Unknown s3 settings for account {name!r}: {sorted(unknown)}")
    return {
        "s3_access_key_id": _optional_string(values.get("access_key_id")),
        "s3_secret_access_key": _optional_string(values.get("secret_access_key")),
        "s3_endpoint": _optional_string(values.get("endpoint")),
        "s3_region": _optional_string(values.get("region")) or "auto",
        "s3_session_token": _optional_string(values.get("session_token")),
    }


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Cloudflare configuration values must be strings")
    return value
