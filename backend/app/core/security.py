import hashlib
import hmac
import os
import re
from uuid import UUID

from dotenv import dotenv_values
from fastapi import HTTPException
from sqlalchemy import select

from app.models.entities import Integration, Tenant


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def resolve_secret(reference: str) -> str:
    # Resolve only server-controlled environment references, never request data.
    secret = os.environ.get(reference)
    if secret is None:
        secret = dotenv_values(".env").get(reference) or ""
    if len(secret) < 32:
        raise HTTPException(503, "Integration secret unavailable")
    return secret


def authenticate_webhook(db, integration_id: str | None, signature: str | None, raw: bytes):
    try:
        parsed_id = UUID(integration_id or "")
    except ValueError:
        raise HTTPException(401, "Invalid integration credentials") from None
    integration = db.scalar(select(Integration).where(Integration.id == parsed_id, Integration.enabled.is_(True)))
    if integration is None or not re.fullmatch(r"sha256=[0-9a-f]{64}", signature or ""):
        raise HTTPException(401, "Invalid integration credentials")
    secret = resolve_secret(integration.secret_ref)
    expected = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(401, "Invalid integration credentials")
    return integration, secret


def authenticate_reader(db, authorization: str | None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Invalid tenant credentials")
    token = authorization[7:]
    if len(token) < 32 or len(token) > 512:
        raise HTTPException(401, "Invalid tenant credentials")
    tenant = db.scalar(select(Tenant).where(Tenant.read_token_hash == token_hash(token)))
    if tenant is None:
        raise HTTPException(401, "Invalid tenant credentials")
    return tenant
