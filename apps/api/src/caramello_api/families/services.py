"""Domain services for families — pure logic, no FastAPI dependency.

The functions take the AsyncSession and the User as plain parameters (never via
Depends), which keeps them reusable from MCP, from tests and from any other
caller with no framework around it.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from caramello_api.families.models import Family, FamilyMember
from caramello_api.users.models import User


async def list_my_families(session: AsyncSession, user: User) -> list[Family]:
    """Return the families the authenticated user belongs to.

    Filters by FamilyMember.user_id == user.id — the caller is responsible for
    the user coming from a trusted source (e.g. get_current_user via the JWT).
    Domain errors are plain Python errors; the caller (operations.py) handles
    them and turns them into the right HTTP response.
    """
    result = await session.execute(
        select(Family)
        .join(FamilyMember, FamilyMember.family_id == Family.id)
        .where(FamilyMember.user_id == user.id)
    )
    return list(result.scalars().all())
