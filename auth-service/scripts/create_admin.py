"""One-shot script to create the initial admin user.

Usage:
    python -m scripts.create_admin admin@example.com 'Sup3rS3cret!Passw0rd'
"""

from __future__ import annotations

import asyncio
import sys

from app.db.session import SessionFactory
from app.services.auth_service import AuthService


async def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python -m scripts.create_admin <email> <password>")
        return 1
    email, password = sys.argv[1], sys.argv[2]

    async with SessionFactory() as session:
        service = AuthService(session)
        user = await service.register(
            email=email,
            password=password,
            full_name="Administrator",
            is_public_registration=False,
        )
        admin = await service.users.get_role_by_name("admin")
        if admin:
            await service.users.assign_role(user, admin)
            await session.commit()
        print(f"Created admin user: {user.email} ({user.id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
