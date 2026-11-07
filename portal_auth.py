"""Signed portal tokens for child app SSO."""
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import jwt
import streamlit as st

TOKEN_TTL_SECONDS = 8 * 3600


def _jwt_secret_or_none() -> Optional[str]:
    return st.secrets.get("JWT_SECRET_KEY")


def create_portal_token(
    user_id: str,
    email: str,
    lang: str,
    subscription_tier: str,
    trials_remaining: int,
    *,
    organization_id: Optional[str] = None,
    organization_name: Optional[str] = None,
    organization_name_zh: Optional[str] = None,
    organization_name_en: Optional[str] = None,
    organization_name_display_mode: Optional[str] = None,
    org_role: Optional[str] = None,
) -> Optional[str]:
    secret = _jwt_secret_or_none()
    if not secret:
        return None

    now = int(time.time())
    payload: Dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "lang": lang,
        "tier": subscription_tier,
        "trials_left": trials_remaining,
        "iat": now,
        "exp": now + TOKEN_TTL_SECONDS,
    }
    if organization_id:
        payload["organization_id"] = organization_id
        payload["organization_name"] = organization_name or ""
        if organization_name_zh:
            payload["organization_name_zh"] = organization_name_zh
        if organization_name_en:
            payload["organization_name_en"] = organization_name_en
        if organization_name_display_mode:
            payload["organization_name_display_mode"] = organization_name_display_mode
        payload["org_role"] = org_role or "member"
    try:
        return jwt.encode(payload, secret, algorithm="HS256")
    except Exception:
        return None


def verify_portal_token(token: str) -> Optional[Dict[str, Any]]:
    secret = _jwt_secret_or_none()
    if not secret:
        return None
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def build_app_launch_url(
    base_url: str,
    user_id: str,
    email: str,
    lang: str,
    subscription_tier: str,
    trials_remaining: int,
    *,
    organization_id: Optional[str] = None,
    organization_name: Optional[str] = None,
    organization_name_zh: Optional[str] = None,
    organization_name_en: Optional[str] = None,
    organization_name_display_mode: Optional[str] = None,
    org_role: Optional[str] = None,
    include_legacy_params: bool = True,
) -> str:
    """Build child-app URL with signed token (and optional legacy params for rollout)."""
    token = create_portal_token(
        user_id,
        email,
        lang,
        subscription_tier,
        trials_remaining,
        organization_id=organization_id,
        organization_name=organization_name,
        organization_name_zh=organization_name_zh,
        organization_name_en=organization_name_en,
        organization_name_display_mode=organization_name_display_mode,
        org_role=org_role,
    )
    params: Dict[str, str] = {"lang": lang}
    if token:
        params["token"] = token
    if include_legacy_params:
        params.update(
            {
                "user_id": user_id,
                "email": email,
                "trials_left": str(trials_remaining),
            }
        )
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{urlencode(params)}"
