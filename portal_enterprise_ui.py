"""Enterprise branding helpers for TechLife child apps."""
from __future__ import annotations

import html
from typing import Any, Callable, Dict, Optional
from urllib.parse import quote

import jwt
import requests
import streamlit as st


def qp_first(query_params: Any, key: str) -> str:
    val = query_params.get(key)
    if isinstance(val, list):
        return val[0] if val else ""
    return val or ""


def _normalize_name_display_mode(value: Any) -> str:
    mode = str(value or "auto").strip().lower()
    return mode if mode in ("zh", "en") else "auto"


def _resolve_organization_display_name(lang: str = "zh") -> str:
    name_zh = (st.session_state.get("organization_name_zh") or "").strip()
    name_en = (st.session_state.get("organization_name_en") or "").strip()
    legacy = (st.session_state.get("organization_name") or "").strip()
    mode = _normalize_name_display_mode(st.session_state.get("organization_name_display_mode"))
    if mode == "zh":
        return name_zh or legacy or name_en
    if mode == "en":
        return name_en or legacy or name_zh
    if lang == "en":
        return name_en or legacy or name_zh
    return name_zh or legacy or name_en


def ensure_enterprise_session_defaults() -> None:
    defaults = {
        "organization_id": None,
        "organization_name": "",
        "organization_name_zh": "",
        "organization_name_en": "",
        "organization_name_display_mode": "auto",
        "organization_logo_url": "",
        "_enterprise_branding_loaded": False,
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default


def apply_portal_token(
    query_params: Any,
    *,
    set_app_language: Optional[Callable[[str], None]] = None,
) -> None:
    token = qp_first(query_params, "token")
    secret = st.secrets.get("JWT_SECRET_KEY")
    if not token or not secret:
        return
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return

    if payload.get("sub"):
        st.session_state.user_id = payload["sub"]
    if payload.get("email"):
        st.session_state.user_email = payload["email"]
        if "@" in payload["email"]:
            st.session_state.username = payload["email"].split("@")[0]
    if payload.get("organization_id"):
        st.session_state.organization_id = payload["organization_id"]
        st.session_state._enterprise_branding_loaded = False
    if payload.get("organization_name_zh"):
        st.session_state.organization_name_zh = payload["organization_name_zh"]
    if payload.get("organization_name_en"):
        st.session_state.organization_name_en = payload["organization_name_en"]
    if payload.get("organization_name"):
        st.session_state.organization_name = payload["organization_name"]
    if payload.get("organization_name_display_mode"):
        st.session_state.organization_name_display_mode = payload["organization_name_display_mode"]
    if payload.get("org_role"):
        st.session_state.org_role = payload["org_role"]
    if payload.get("trials_left") is not None and "trials_left" not in st.session_state:
        try:
            st.session_state.trials_left = int(payload["trials_left"])
        except (TypeError, ValueError):
            pass
    if set_app_language and "lang" not in st.session_state and payload.get("lang") in ("zh", "en"):
        set_app_language(payload["lang"])


def is_enterprise_user() -> bool:
    return bool(st.session_state.get("organization_id"))


def load_enterprise_branding(supabase_url: str, headers: Dict[str, str]) -> None:
    if not is_enterprise_user() or st.session_state.get("_enterprise_branding_loaded"):
        return

    org_id = st.session_state.get("organization_id")
    logo_url = ""
    try:
        query = (
            f"id=eq.{quote(str(org_id), safe='')}"
            "&select=name,name_zh,name_en,name_display_mode,logo_url"
        )
        response = requests.get(
            f"{supabase_url}/rest/v1/organizations?{query}",
            headers=headers,
            timeout=12,
        )
        if response.status_code == 200 and response.json():
            row = response.json()[0]
            name_zh = (row.get("name_zh") or "").strip()
            name_en = (row.get("name_en") or "").strip()
            legacy = (row.get("name") or "").strip()
            if name_zh:
                st.session_state.organization_name_zh = name_zh
            if name_en:
                st.session_state.organization_name_en = name_en
            if legacy:
                st.session_state.organization_name = legacy
            st.session_state.organization_name_display_mode = _normalize_name_display_mode(
                row.get("name_display_mode")
            )
            logo_url = (row.get("logo_url") or "").strip()
    except Exception:
        logo_url = ""

    st.session_state.organization_logo_url = logo_url
    st.session_state._enterprise_branding_loaded = True


def enterprise_display_name() -> str:
    lang = st.session_state.get("lang", "zh")
    return _resolve_organization_display_name(lang)


def enterprise_logo_url() -> str:
    return (st.session_state.get("organization_logo_url") or "").strip()


def enterprise_brand_markup(org_name: str, logo_url: str | None, *, variant: str = "main") -> str:
    """Logo left of org name, scaled slightly above text cap-height, with 2ch spacing."""
    safe_name = html.escape(org_name or "")
    if variant == "sidebar":
        wrapper_style = (
            "display:flex; align-items:center; "
            "font-size:calc(2.25rem * 0.85); font-weight:700; line-height:1.2; margin:0 0 0.5rem 0;"
        )
    elif variant == "main_compact":
        wrapper_style = (
            "display:flex; align-items:center; "
            "font-size:1.75rem; font-weight:700; line-height:1.2; margin:0 0 0.75rem 0;"
        )
    else:
        wrapper_style = (
            "display:flex; align-items:center; "
            "font-size:2.25rem; font-weight:700; line-height:1.2; margin:0 0 1rem 0;"
        )

    if logo_url:
        safe_logo = html.escape(logo_url, quote=True)
        return (
            f'<div style="{wrapper_style}">'
            f'<img src="{safe_logo}" alt="" '
            f'style="height:1.1em; width:auto; object-fit:contain; flex-shrink:0;" />'
            f'<span style="margin-left:2ch; white-space:nowrap;">{safe_name}</span>'
            f"</div>"
        )
    return f'<div style="{wrapper_style}">{safe_name}</div>'


def render_enterprise_sidebar_brand() -> None:
    if not is_enterprise_user():
        return
    org_name = enterprise_display_name()
    logo_url = enterprise_logo_url()
    if not org_name and not logo_url:
        return
    st.markdown(
        enterprise_brand_markup(org_name, logo_url or None, variant="sidebar"),
        unsafe_allow_html=True,
    )


def render_enterprise_main_brand() -> None:
    if not is_enterprise_user():
        return
    org_name = enterprise_display_name()
    logo_url = enterprise_logo_url()
    if not org_name and not logo_url:
        return
    st.markdown(
        enterprise_brand_markup(org_name, logo_url or None, variant="main_compact"),
        unsafe_allow_html=True,
    )
