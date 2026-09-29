"""Bootstrap the first admin from INITIAL_ADMIN_EMAIL / INITIAL_ADMIN_PASSWORD on an empty database.

Run after migrations, before first use in production:
    python -m app.cli.create_admin

Refuses to run if any user already exists, or if the env vars are missing/too short — production
never gets predictable demo credentials (spec §4, ARCHITECTURE.md §10).
"""

from __future__ import annotations

import sys

from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.scope import get_default_academy_id
from app.db.session import SessionLocal
from app.models.identity import AdminProfile, User, UserRole


def main() -> int:
    with SessionLocal() as db:
        if db.scalar(select(User).limit(1)):
            print("A user already exists — refusing to create another bootstrap admin.")
            return 1

        email = settings.initial_admin_email.strip().lower()
        password = settings.initial_admin_password
        if not email or len(password) < 12:
            print(
                "Set INITIAL_ADMIN_EMAIL and a 12+ character INITIAL_ADMIN_PASSWORD before "
                "running this on an empty database."
            )
            return 1

        academy_id = get_default_academy_id(db)
        admin = User(
            academy_id=academy_id,
            role=UserRole.admin,
            full_name="Talent Admin",
            email=email,
            password_hash=hash_password(password),
            must_change_password=True,
        )
        db.add(admin)
        db.flush()
        db.add(AdminProfile(user_id=admin.id, is_primary=True))
        db.commit()
        print(f"Created admin: {email}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
