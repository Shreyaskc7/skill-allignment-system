"""Command-line administration.

    cd backend
    python -m app.cli create-admin --email admin@example.edu --name "Admin Name"

The password is prompted for (hidden) or read from stdin with --password-stdin.
It is never accepted as a command-line argument.
"""

import argparse
import getpass
import sys

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app import models
from app.db import SessionLocal
from app.models import UserRole
from app.schemas import _strong_password
from app.security import hash_password
from app.services.audit import audit
from app.services.auth import find_user_by_email


_EMAIL = TypeAdapter(EmailStr)


def create_admin(db: Session, email: str, full_name: str, password: str) -> models.User:
    # Same validation as the login form, so the account can actually sign in.
    try:
        email = _EMAIL.validate_python(email.strip()).lower()
    except ValidationError as e:
        raise ValueError(f"Invalid email address: {e.errors()[0]['msg']}") from None
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    _strong_password(password)
    if find_user_by_email(db, email):
        raise ValueError(f"A user with email {email} already exists")
    user = models.User(
        email=email,
        full_name=" ".join(full_name.split()),
        role=UserRole.admin,
        password_hash=hash_password(password),
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.flush()
    audit(db, "cli.admin_created", user_id=user.id, entity_type="user", entity_id=user.id)
    db.commit()
    return user


def _read_password(from_stdin: bool) -> str:
    if from_stdin:
        return sys.stdin.readline().rstrip("\r\n")
    first = getpass.getpass("Password (min 8 chars, letters and numbers): ")
    if first != getpass.getpass("Confirm password: "):
        raise ValueError("Passwords do not match")
    return first


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    ca = sub.add_parser("create-admin", help="Create an administrator account")
    ca.add_argument("--email", required=True)
    ca.add_argument("--name", required=True, help="Full name")
    ca.add_argument("--password-stdin", action="store_true", help="Read the password from standard input")
    args = parser.parse_args(argv)

    try:
        password = _read_password(args.password_stdin)
        with SessionLocal() as db:
            user = create_admin(db, args.email, args.name, password)
            summary = f"Administrator created: {user.email} (id {user.id})"
    except (ValueError, ValidationError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
