"""Environment configuration source."""

from __future__ import annotations

import os
from pathlib import Path

from cloudflare_cli.models import AccountConfig


def config_path() -> Path | None:
    value = os.environ.get("CLOUDFLARE_CONFIG")
    if value:
        return Path(value).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME") or os.environ.get("APPDATA")
    if base is None:
        base = str(Path.home() / ".config")
    candidate = Path(base) / "cloudflare" / "config.toml"
    return candidate if candidate.is_file() else None


def account_from_environment() -> AccountConfig | None:
    token = os.environ.get("CLOUDFLARE_API_TOKEN") or os.environ.get("CLOUDFLARE")
    key = os.environ.get("CLOUDFLARE_API_KEY")
    email = os.environ.get("CLOUDFLARE_EMAIL")
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    s3_access_key_id = os.environ.get("CLOUDFLARE_R2_ACCESS_KEY_ID") or os.environ.get(
        "AWS_ACCESS_KEY_ID"
    )
    s3_secret_access_key = os.environ.get(
        "CLOUDFLARE_R2_SECRET_ACCESS_KEY"
    ) or os.environ.get("AWS_SECRET_ACCESS_KEY")
    s3_endpoint = os.environ.get("CLOUDFLARE_R2_ENDPOINT") or os.environ.get(
        "AWS_ENDPOINT_URL"
    )
    s3_region = os.environ.get("CLOUDFLARE_R2_REGION") or os.environ.get(
        "AWS_REGION", "auto"
    )
    s3_session_token = os.environ.get("CLOUDFLARE_R2_SESSION_TOKEN") or os.environ.get(
        "AWS_SESSION_TOKEN"
    )
    if not any(
        (
            token,
            key,
            email,
            account_id,
            s3_access_key_id,
            s3_secret_access_key,
            s3_endpoint,
        )
    ):
        return None
    return AccountConfig(
        name=os.environ.get("CLOUDFLARE_ACCOUNT", "default"),
        account_id=account_id,
        api_token=token,
        api_key=key,
        email=email,
        s3_access_key_id=s3_access_key_id,
        s3_secret_access_key=s3_secret_access_key,
        s3_endpoint=s3_endpoint,
        s3_region=s3_region,
        s3_session_token=s3_session_token,
    )
