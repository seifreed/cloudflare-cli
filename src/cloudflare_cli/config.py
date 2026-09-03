"""Configuration composition for single and multi-account use."""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

from cloudflare_cli.config_environment import account_from_environment, config_path
from cloudflare_cli.config_file import accounts_from_document, read_document
from cloudflare_cli.models import AccountConfig, CloudflareConfig

__all__ = ["AccountConfig", "CloudflareConfig", "load_config"]


def load_config(path: Path | None = None) -> CloudflareConfig:
    """Load TOML configuration, then overlay the single-account environment."""
    document = read_document(path or config_path())
    unknown = set(document) - {"accounts", "default_account"}
    if unknown:
        raise ValueError(f"Unknown top-level settings: {sorted(unknown)}")
    accounts = accounts_from_document(document)
    environment_account = account_from_environment()
    if environment_account is not None:
        existing = accounts.get(environment_account.name)
        accounts[environment_account.name] = (
            _overlay_environment(existing, environment_account)
            if existing is not None
            else environment_account
        )
    if not accounts:
        raise ValueError(
            "No Cloudflare account configured; set CLOUDFLARE or provide a config file"
        )
    configured_default = document.get("default_account", "")
    if not isinstance(configured_default, str):
        raise ValueError("default_account must be a string")
    default = configured_default or next(iter(accounts))
    if "CLOUDFLARE_ACCOUNT" in os.environ:
        default = os.environ["CLOUDFLARE_ACCOUNT"]
    if default not in accounts:
        raise ValueError(f"Default account {default!r} is not configured")
    return CloudflareConfig(
        accounts=MappingProxyType(accounts), default_account=default
    )


def _overlay_environment(
    existing: AccountConfig, environment: AccountConfig
) -> AccountConfig:
    values = {
        field: value
        for field, value in {
            "account_id": environment.account_id,
            "api_token": environment.api_token,
            "api_key": environment.api_key,
            "email": environment.email,
            "s3_access_key_id": environment.s3_access_key_id,
            "s3_secret_access_key": environment.s3_secret_access_key,
            "s3_endpoint": environment.s3_endpoint,
            "s3_session_token": environment.s3_session_token,
        }.items()
        if value is not None
    }
    if os.environ.get("CLOUDFLARE_R2_REGION") or os.environ.get("AWS_REGION"):
        values["s3_region"] = environment.s3_region
    return replace(existing, **values)
