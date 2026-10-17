"""Rotate an existing tenant's read token without altering tenant, integration, or workflow IDs."""
import argparse
import secrets
import sys
from uuid import UUID

from dotenv import load_dotenv

from app.core.config import Settings
from app.core.database import make_engine, session_factory
from app.core.security import token_hash
from app.models.entities import Tenant


def rotate_tenant_token(database_url: str, tenant_id: UUID, custom_token: str | None = None) -> tuple[str, str]:
    """Rotate read token for an existing tenant. Returns (tenant_name, plain_token)."""
    token = custom_token or secrets.token_urlsafe(32)
    if not (32 <= len(token) <= 512):
        raise ValueError("Token must be between 32 and 512 characters")

    engine = make_engine(database_url)
    try:
        with session_factory(engine)() as db:
            tenant = db.get(Tenant, tenant_id)
            if tenant is None:
                raise LookupError(f"Tenant not found: {tenant_id}")

            tenant.read_token_hash = token_hash(token)
            db.commit()
            return tenant.name, token
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", required=True, help="UUID of the existing tenant")
    parser.add_argument("--database-url", help="Database connection URL override (defaults to Settings.database_url)")
    parser.add_argument("--token", help="Optional explicit token (minimum 32 characters; generated if omitted)")
    args = parser.parse_args()

    try:
        tenant_id = UUID(args.tenant_id)
    except (ValueError, TypeError):
        parser.error(f"Invalid UUID: {args.tenant_id}")

    load_dotenv()
    db_url = args.database_url or Settings().database_url.get_secret_value()

    try:
        tenant_name, new_token = rotate_tenant_token(db_url, tenant_id, args.token)
        print("Token rotation succeeded.")
        print(f"Tenant ID:      {tenant_id}")
        print(f"Tenant Name:    {tenant_name}")
        print(f"New Read Token: {new_token}")
        print("Note: Store this token securely. It will not be shown again and is not stored in plaintext.")
    except Exception as exc:
        print(f"Token rotation failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

