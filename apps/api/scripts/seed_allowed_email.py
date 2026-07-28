"""Insert an e-mail into the allowlist (`allowed_emails`) directly in the database.

There is no HTTP route for allowlist management: this script is the operator's
tool (authorizing an e-mail in production, via `docker exec` — see
`docs/release.md`) and the E2E scripts' tool (seeding the test user before an
automated login against the mock OIDC provider).

The e-mail is always normalized (`.strip().lower()`) before the INSERT —
contract documented in `src/caramello_api/shared/models.py` (`AllowedEmail`),
which the read path (`shared.auth.is_email_allowlisted`) follows the same way.

Usage: uv run python scripts/seed_allowed_email.py \
           --database-url postgresql+asyncpg://... --email pessoa@exemplo.com
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def _add_allowed_email(database_url: str, email: str) -> None:
    engine = create_async_engine(database_url, future=True)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO allowed_emails (email) VALUES (:email) "
                    "ON CONFLICT (email) DO NOTHING"
                ),
                {"email": email.strip().lower()},
            )
    finally:
        await engine.dispose()
    print(f"Allowlisted: {email.strip().lower()}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Insert an e-mail into the allowlist (allowed_emails) directly in "
            "the database, normalized to lowercase. Idempotent."
        )
    )
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--email", required=True)
    args = parser.parse_args()

    asyncio.run(_add_allowed_email(args.database_url, args.email))


if __name__ == "__main__":
    main()
