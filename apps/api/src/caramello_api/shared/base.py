"""Declarative base shared by every model — the single source of `metadata`.

Kept deliberately separate from `shared/database.py`, which owns the engine and
the session factory. The two concerns have different costs and different
lifetimes:

  - This module is pure mapping metadata. Importing it touches no configuration
    and opens no connection, so a model module can be imported (by a test, by
    the DSL generator's output, by Alembic) without `DATABASE_URL` being set.
  - `shared/database.py` builds the async engine at import time, which makes
    `DATABASE_URL` a hard requirement for anything that reaches it.

Alembic's `migrations/env.py` imports `Base` from here to reach
`Base.metadata` — and to install the naming convention on that metadata BEFORE
any model module is imported, which is why the convention lives there and not
in this file.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
