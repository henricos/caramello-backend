"""Application settings sourced from environment variables via pydantic-settings.

`Settings` never reads a dotenv file itself (`env_file` is deliberately NOT
set below) — it only ever reads the real process environment (`os.environ`)
and fails loudly, via pydantic's own required-field validation, when a
required variable is missing. Populating the process environment before this
service starts is the responsibility of whatever launches it (a shell, a
script, a container), never something this module resolves on its own. In
development that means sourcing the versioned `.env.development`:

    set -a && source .env.development && set +a
    uv run python -m caramello_api --reload

Because a shell resolves the file, `${VAR:-fallback}` indirection works
there. The rationale for rejecting the more common `.env.example` +
copy-to-`.env` pattern is recorded in the repository's `docs/architecture.md`
("Configuration comes from the process environment") and in `AGENTS.md`.

Service-specific knobs (host, port, log level) use the `CARAMELLO_API_`
prefix. Variables shared with `apps/web` or with the deploy as a whole
(`DATABASE_URL`, `APP_ENV`, `AUTH_OIDC_*`, `APP_BASE_PATH`, `DATA_DIR`) are
read WITHOUT the prefix via `validation_alias`, so an operator running both
modules sees a single consistent name for the same concept.

`app_base_path` mirrors `apps/web`'s `APP_BASE_PATH`. The mechanism differs:
Next.js bakes `basePath` into static assets at *build* time, while FastAPI's
`root_path` is a pure *runtime* concern (it only affects OpenAPI generation
and how the app reasons about its mount point behind a reverse proxy), so it
is optional here.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_app_base_path(value: str) -> str:
    """Normalize `APP_BASE_PATH`, mirroring `apps/web`'s base-path helper.

    Empty string means "no base path". `"/"` is treated as equivalent to
    empty (a root mount needs no prefix).
    """
    if value == "":
        return value

    if value != value.strip():
        raise ValueError("Invalid APP_BASE_PATH: no leading or trailing whitespace allowed.")

    if not value.startswith("/"):
        raise ValueError(
            'Invalid APP_BASE_PATH: the value must start with "/". Example: "/caramello".'
        )

    if "//" in value:
        raise ValueError("Invalid APP_BASE_PATH: no duplicated slashes allowed.")

    if value == "/":
        return ""

    return value[:-1] if value.endswith("/") else value


class Settings(BaseSettings):
    """Runtime-configurable settings for the caramello-api service."""

    model_config = SettingsConfigDict(env_prefix="CARAMELLO_API_", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"

    # Async SQLAlchemy DSN (postgresql+asyncpg://...). No default — a
    # Postgres DSN genuinely diverges between environments (embedded pgembed
    # locally, a real instance in production), so there is no sensible
    # fallback; the service fails loudly at startup instead of silently
    # running against the wrong database.
    database_url: str = Field(validation_alias="DATABASE_URL")

    # Closed set of values: a typo in a deploy ("Production", "prod") would
    # silently fall into the permissive branch that re-exposes /docs; a
    # Literal makes it fail loudly at startup instead.
    app_env: Literal["development", "test", "production"] = Field(
        default="development", validation_alias="APP_ENV"
    )

    # Base URL (issuer) of the OIDC provider used for login — the FULL realm
    # URL, e.g. https://keycloak.exemplo.com/realms/caramello (Keycloak in
    # production, a local mock provider in dev/E2E). No default: fails loudly
    # if absent. Everything provider-specific is discovered from here
    # (`/.well-known/openid-configuration`, JWKS), never hardcoded.
    auth_oidc_issuer: str = Field(validation_alias="AUTH_OIDC_ISSUER")

    # Audience this service expects in the `aud` claim of incoming access
    # tokens — the api's own identity at the provider (`caramello-api`, added
    # to each consumer's tokens via an audience mapper). The api is a pure
    # resource server: it never starts an OAuth flow, so it needs no client
    # secret, only the provider's public JWKS and this expected audience.
    auth_oidc_audience: str = Field(validation_alias="AUTH_OIDC_AUDIENCE")

    app_base_path: str = Field(default="", validation_alias="APP_BASE_PATH")

    # Public base URL of this service as consumers reach it (scheme + host +
    # base path, no trailing slash), e.g. https://exemplo.com/caramello-api.
    # Used ONLY to build the absolute URLs served by the OAuth discovery
    # endpoints that MCP clients consume, plus the `resource_metadata` pointer
    # in the `WWW-Authenticate` header — never for routing. Defaults to local
    # dev; in production it MUST be set explicitly (enforced below), otherwise
    # the discovery metadata would silently advertise localhost.
    public_url: str = Field(default="", validation_alias="PUBLIC_URL")

    # Shared data folder. The process always assumes `/data` (a fixed path
    # inside the container; mapping it to a host folder is the deploy's
    # responsibility). In local dev without a container `/data` usually is
    # not writable without root — override via `DATA_DIR`.
    data_dir: str = Field(default="/data", validation_alias="DATA_DIR")

    @field_validator("app_base_path")
    @classmethod
    def _validate_app_base_path(cls, value: str) -> str:
        return normalize_app_base_path(value)

    @field_validator("auth_oidc_issuer")
    @classmethod
    def _normalize_auth_oidc_issuer(cls, value: str) -> str:
        # A trailing slash would keep discovery working while every token
        # fails `iss` validation (the claim never carries the slash) — a
        # silent, hard-to-diagnose failure. Normalize once at the source so
        # discovery and claims validation always agree.
        return value.rstrip("/")

    @model_validator(mode="after")
    def _resolve_public_url(self) -> "Settings":
        if not self.public_url:
            if self.app_env == "production":
                raise ValueError(
                    "PUBLIC_URL is required when APP_ENV=production: without it the"
                    " OAuth discovery metadata would advertise localhost URLs."
                )
            self.public_url = "http://localhost:8000"
        self.public_url = self.public_url.rstrip("/")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    # Every field is actually resolved from environment variables by
    # pydantic-settings at runtime; type checkers only see the
    # dataclass-style constructor and flag the required fields as missing —
    # a well-known BaseSettings typing gap, not a real bug.
    return Settings()  # type: ignore[call-arg]
