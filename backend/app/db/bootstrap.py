"""Prepare a production database: create tables and the first administrator.

No sample data is created. Everything else — organizations, communities,
households, users — is entered by the administrator inside the app.
"""

import os

from app.core.security import get_password_hash
from app.db.base import Base
from app.db.migrate import run_migrations
from app.db.session import SessionLocal, engine
from app.models.user import User, UserRole

DEFAULT_ADMIN_EMAIL = "admin@flow.app"
DEFAULT_ADMIN_NAME = "Administrator"


def bootstrap() -> None:
    Base.metadata.create_all(bind=engine)
    run_migrations(engine)
    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            print("Users already exist; nothing to bootstrap.")
            return

        email = os.getenv("ADMIN_EMAIL", DEFAULT_ADMIN_EMAIL).strip().lower()
        password = os.getenv("ADMIN_PASSWORD")
        if not password:
            print(
                "ADMIN_PASSWORD is not set; no administrator created. "
                "Set ADMIN_EMAIL/ADMIN_PASSWORD and restart to create the first login."
            )
            return

        db.add(
            User(
                email=email,
                hashed_password=get_password_hash(password),
                full_name=os.getenv("ADMIN_NAME", DEFAULT_ADMIN_NAME),
                role=UserRole.SUPER_ADMIN,
            )
        )
        db.commit()
        print(f"Created initial administrator: {email}")
    finally:
        db.close()


if __name__ == "__main__":
    bootstrap()
