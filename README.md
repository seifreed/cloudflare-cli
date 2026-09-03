<p align="center">
  <img src="https://img.shields.io/badge/cloudflare--multi--cli-Multi--account%20API%20client-blue?style=for-the-badge" alt="cloudflare-multi-cli">
</p>

<h1 align="center">cloudflare-multi-cli</h1>

<p align="center">
  <strong>Modern multi-account Cloudflare API client, CLI, and R2 toolkit</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/cloudflare-multi-cli/"><img src="https://img.shields.io/pypi/v/cloudflare-multi-cli?style=flat-square&logo=pypi&logoColor=white" alt="PyPI Version"></a>
  <a href="https://pypi.org/project/cloudflare-multi-cli/"><img src="https://img.shields.io/pypi/pyversions/cloudflare-multi-cli?style=flat-square&logo=python&logoColor=white" alt="Python Versions"></a>
  <a href="https://github.com/seifreed/cloudflare-cli/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License"></a>
  <a href="https://github.com/seifreed/cloudflare-cli/stargazers"><img src="https://img.shields.io/github/stars/seifreed/cloudflare-cli?style=flat-square" alt="GitHub Stars"></a>
  <a href="https://github.com/seifreed/cloudflare-cli/issues"><img src="https://img.shields.io/github/issues/seifreed/cloudflare-cli?style=flat-square" alt="GitHub Issues"></a>
</p>

---

## Overview

**cloudflare-multi-cli** is a Python 3.14 client and command-line interface for
Cloudflare's OpenAPI REST API. It supports multiple accounts in one
configuration, exposes the complete packaged catalog, and provides generic
requests for operations that are added to the upstream schema later.

### Key Features

| Feature | Description |
|---------|-------------|
| **Complete API catalog** | 3,407 OpenAPI operations packaged as CLI commands and dynamic Python methods |
| **Multi-account** | Select independent Cloudflare accounts with `--account` |
| **TOML and environment config** | Use one config file, `CLOUDFLARE`, or explicit environment variables |
| **Generic requests** | Call any relative Cloudflare API path and HTTP method |
| **R2 support** | Signed S3-compatible bucket and object requests with AWS Signature V4 |
| **JSON and TOON** | Export command results as JSON or TOON |
| **Typed library** | Immutable account and operation models with an injectable transport |
| **Cross-platform** | Windows, Linux, and macOS on x64 or ARM |

### Supported Outputs

```text
Cloudflare API       JSON responses, binary responses
Exports              JSON, TOON
R2 objects           JSON/XML decoding or raw binary output
Automation           Python library and shell-friendly exit codes
```

---

## Installation

### From PyPI (Recommended)

```bash
python -m pip install cloudflare-multi-cli
```

### From Source

```bash
git clone https://github.com/seifreed/cloudflare-cli.git
cd cloudflare-cli
python3.14 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
python -m pip install -e .
```

Development tooling is available with:

```bash
python -m pip install -e '.[dev]'
```

---

## Quick Start

For a single account, set the token and account ID:

```bash
export CLOUDFLARE="your-api-token"
export CLOUDFLARE_ACCOUNT_ID="your-account-id"

cloudflare accounts
cloudflare request GET /accounts/{account_id}/tokens/verify
cloudflare operations --format toon
```

Use `CLOUDFLARE_API_TOKEN` instead of `CLOUDFLARE` when an explicit variable
name is preferred.

---

## Configuration

Create `~/.config/cloudflare/config.toml` on Unix-like systems. On Windows,
the default location uses `APPDATA`; `CLOUDFLARE_CONFIG` can override either
location.

```toml
default_account = "personal"

[accounts.personal]
account_id = "your-account-id"
api_token = "your-api-token"

[accounts.customer]
account_id = "another-account-id"
api_token = "another-api-token"

[accounts.customer.s3]
access_key_id = "r2-access-key"
secret_access_key = "r2-secret-key"
endpoint = "https://another-account-id.r2.cloudflarestorage.com"
region = "auto"
```

Select an account explicitly:

```bash
cloudflare --account customer accounts list-accounts --name example.com
cloudflare --account customer r2 list-buckets
```

API authentication supports `api_token`, or `api_key` together with `email`.
Environment variables override the matching values for the selected account:

```text
CLOUDFLARE_API_TOKEN       API token; CLOUDFLARE is also accepted
CLOUDFLARE_API_KEY         Global API key
CLOUDFLARE_EMAIL            Email used with the global API key
CLOUDFLARE_ACCOUNT_ID       Account ID
CLOUDFLARE_ACCOUNT          Account name
CLOUDFLARE_CONFIG           TOML configuration path
```

R2 also accepts `CLOUDFLARE_R2_ACCESS_KEY_ID`,
`CLOUDFLARE_R2_SECRET_ACCESS_KEY`, `CLOUDFLARE_R2_ENDPOINT`,
`CLOUDFLARE_R2_REGION`, and `CLOUDFLARE_R2_SESSION_TOKEN`, plus the equivalent
`AWS_*` variables.

---

## Usage

### Command Line Interface

```bash
# List all packaged operations
cloudflare operations

# Use a catalog command and its documented parameters
cloudflare --account personal accounts list-accounts --name example.com
cloudflare --account personal images get-image-list --per-page 100

# Call any API path directly
cloudflare request GET /accounts/{account_id}/zones \
  --query per_page=20 --format toon

# Send JSON or raw content
cloudflare request POST /accounts/{account_id}/workers/scripts/demo \
  --raw-file worker.js --content-type application/javascript

# Write binary responses without formatting
cloudflare request GET /accounts/{account_id}/workers/scripts/demo \
  --header Accept=application/javascript --output-file worker.js
```

### Main Commands

| Command | Description |
|---------|-------------|
| `cloudflare accounts` | List configured account names and IDs |
| `cloudflare operations` | List the complete packaged OpenAPI catalog |
| `cloudflare request METHOD PATH` | Send a generic Cloudflare API request |
| `cloudflare <group> <operation>` | Execute a catalog operation with named options |
| `cloudflare r2 ...` | Execute signed S3-compatible R2 requests |

Every catalog operation is grouped by its API path, such as `accounts`,
`access`, `dns-records`, `images`, `radar`, and `workers`. Run `--help` on a
group or operation to inspect its generated options.

### JSON and TOON

```bash
cloudflare operations --format json
cloudflare operations --format toon
cloudflare request GET /zones --format json --output-file zones.json
```

`--output-file` writes binary responses as-is and formatted responses as UTF-8.

### R2

```bash
cloudflare --account customer r2 list-buckets
cloudflare --account customer r2 list-objects my-bucket --query prefix=backups/
cloudflare --account customer r2 get-object my-bucket backups/state.json \
  --output-file state.json
cloudflare --account customer r2 put-object my-bucket backups/state.json \
  --raw-file state.json --content-type application/json

# Generic signed R2 request
cloudflare --account customer r2 request GET /my-bucket?list-type=2
```

The R2 adapter covers bucket/object operations and generic signed requests. It
uses region `auto` by default and supports temporary session tokens.

---

## Python Library

```python
from cloudflare_cli import CloudflareClient, R2Client, load_config

config = load_config()
client = CloudflareClient(config.account("customer"))

# The operationId becomes a Python method name.
accounts = client.accounts_list_accounts(name="example.com", per_page=20)

# Generic operation access is available when names are dynamic.
result = client.call(
    "analytics-engine-sql-query-get",
    operation_parameters={"query": "SELECT * FROM events"},
)

r2 = R2Client.from_account(config.account("customer"))
objects = r2.list_objects("my-bucket", prefix="backups/")
```

`CloudflareClient` accepts injectable `Transport` and `OperationCatalog` ports
for custom HTTP infrastructure or an alternate operation source. Tests in this
repository use local HTTP servers only and do not modify a Cloudflare account.

---

## Refreshing The Catalog

The packaged registry is generated from a Cloudflare OpenAPI document:

```bash
python tools/generate_registry.py openapi.json src/cloudflare_cli/registry.json
```

The generated catalog includes operation IDs, methods, paths, parameters,
array metadata, object query metadata, and request-body requirements.

---

## Requirements

- Python 3.14 only
- Windows, Linux, or macOS on x64 or ARM
- Runtime dependency: `defusedxml`
- See [pyproject.toml](pyproject.toml) for development tooling

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Install the development extra
4. Run `black --check .`, `ruff check .`, `mypy .`, `pytest`, `bandit`, and `pip-audit`
5. Open a pull request

Tests must use local servers and must not perform account-changing requests.

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).

---

<p align="center">
  <sub>Built for multi-account Cloudflare automation and API operations</sub>
</p>
