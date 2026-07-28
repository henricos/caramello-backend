"""Remove an e-mail from the allowlist (`allowed_emails`) directly in the database.

Mirror of `seed_allowed_email.py`: there is no HTTP route for allowlist
management, so revoking an access means running this script (or direct SQL).
Removing from the allowlist does NOT delete the `user` row nor any family
membership — the history is preserved; the e-mail simply stops passing
authorization on the next request.

The e-mail is normalized (`.strip().lower()`) before the DELETE — same contract
as `src/caramello_api/shared/models.py` (`AllowedEmail`). The operation is
idempotent: removing an absent e-mail is a no-op.

Usage: uv run python scripts/remove_allowed_email.py \
           --database-url postgresql+asyncpg://... --email pessoa@exemplo.com
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def _remove_allowed_email(database_url: str, email: str) -> None:
    engine = create_async_engine(database_url, future=True)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM allowed_emails WHERE email = :email"),
                {"email": email.strip().lower()},
            )
    finally:
        await engine.dispose()
    print(f"Removed from the allowlist: {email.strip().lower()}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Remove an e-mail from the allowlist (allowed_emails) directly in "
            "the database, normalized to lowercase. Idempotent."
        )
    )
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--email", required=True)
    args = parser.parse_args()

    asyncio.run(_remove_allowed_email(args.database_url, args.email))


if __name__ == "__main__":
    main()
