"""Infrastructure tables that no domain owns and the DSL does not generate.

Every `{domain}/models.py` in this package is emitted by the DSL generator
(`scripts/generate_code.py` rewrites those files on every run), so a
hand-written table declared there would be silently destroyed by the next
`./bin/generate_code`. Authorization infrastructure is also not a business
entity: it has no schemas, no CRUD router and no MCP tool. Both reasons point
at the same place — `shared/`, next to the auth layer that reads it.

Models declared here must be imported by `migrations/env.py` (below its
`naming_convention` block) so Alembic sees them in `Base.metadata`.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from caramello_api.shared.base import Base


class AllowedEmail(Base):
    """E-mail allowed to use the system at all — the first authorization layer.

    Presence in this table answers "may this identity use Caramello?"; family
    membership (`family_member`) answers "which data may it reach?". See
    "Authentication model" in the root `docs/architecture.md`.

    Unlike every business table, this one carries NO `uuid`: it is never
    exposed through the API (there is no route to list, create or delete an
    entry — administration is `scripts/seed_allowed_email.py` /
    `scripts/remove_allowed_email.py`, run by the operator), so there is no
    public identifier to protect.

    Normalization contract: `email` is always stored `.strip().lower()`, by
    every writer (the startup seed, both operator scripts) and assumed by the
    only reader (`shared.auth.is_email_allowlisted`). Postgres comparison is
    case-sensitive, so a row stored with different casing would never match.
    """

    __tablename__ = "allowed_emails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, nullable=False)
    # 320 = 64 (local part) + 1 (@) + 255 (domain), the RFC 3696 ceiling.
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    # Server-side default: rows are inserted by raw `text()` statements that
    # never go through the ORM flush, so a Python-side default would leave the
    # column empty.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
