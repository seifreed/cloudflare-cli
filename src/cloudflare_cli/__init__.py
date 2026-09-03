"""Multi-account Cloudflare API client."""

from cloudflare_cli.catalog import PackagedOperationCatalog, operation, operations
from cloudflare_cli.client import CloudflareClient, CloudflareError
from cloudflare_cli.config import load_config
from cloudflare_cli.models import AccountConfig, CloudflareConfig
from cloudflare_cli.ports import (
    OperationCatalog,
    Transport,
    TransportError,
    TransportResponse,
)
from cloudflare_cli.r2 import R2Client, R2Error
from cloudflare_cli.registry import Operation, Parameter

__all__ = [
    "AccountConfig",
    "CloudflareClient",
    "CloudflareConfig",
    "CloudflareError",
    "Operation",
    "OperationCatalog",
    "Parameter",
    "PackagedOperationCatalog",
    "R2Client",
    "R2Error",
    "Transport",
    "TransportError",
    "TransportResponse",
    "load_config",
    "operation",
    "operations",
]

__version__ = "0.1.0"
