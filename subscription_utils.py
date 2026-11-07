# subscription_utils.py (用于工具 App)
from typing import Any, Dict, Optional

import streamlit as st
from supabase import create_client

from portal_auth import verify_portal_token


def _get_secret(*keys: str, default=None):
    for key in keys:
        if key in st.secrets:
            return st.secrets[key]
    if default is not None:
        return default
    return None


def _get_supabase_url() -> Optional[str]:
    return _get_secret(
        "SUPABASE_STOCK_URL",
        "SUPABASE_URL",
        "connections.supabase.SUPABASE_URL",
    )


def _get_service_role_key() -> Optional[str]:
    return _get_secret(
        "SUPABASE_STOCK_SECRET_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_KEY",
        "connections.supabase.SUPABASE_SERVICE_ROLE_KEY",
    )


def _get_jwt_secret() -> Optional[str]:
    return _get_secret("JWT_SECRET_KEY", "connections.supabase.JWT_SECRET_KEY")


@st.cache_resource
def get_supabase_admin_client():
    """管理员客户端（service_role key，绕过 RLS）"""
    try:
        url = _get_supabase_url()
        key = _get_service_role_key()
        if not url or not key:
            raise ValueError("Missing Supabase admin credentials")
        return create_client(url, key)
    except Exception as e:
        st.error(f"管理员客户端初始化失败: {e}")
        return None


def get_user_profile(user_id: str) -> Dict[str, Any]:
    """从 profiles 表读取订阅信息（与门户一致）"""
    supabase = get_supabase_admin_client()
    if supabase is None or not user_id:
        return {
            "subscription_tier": "free",
            "free_trials_remaining": 0,
            "email": "",
        }

    try:
        result = (
            supabase.table("profiles")
            .select(
                "email, subscription_tier, free_trials_remaining, subscription_expires_at, "
                "organization_id, org_role"
            )
            .eq("id", user_id)
            .execute()
        )
        if result.data:
            return result.data[0]
    except Exception as e:
        st.error(f"获取用户资料失败: {e}")

    return {
        "subscription_tier": "free",
        "free_trials_remaining": 0,
        "email": "",
    }


def authenticate_from_portal() -> Optional[Dict[str, Any]]:
    """
    从门户跳转参数认证用户。
    优先验证 JWT token；过渡期仍兼容旧 URL 参数，但会回源 profiles 校验。
  返回: {user_id, email, lang, subscription_tier, trials_left}
    """
    query_params = st.query_params
    token = query_params.get("token")
    if token:
        payload = verify_portal_token(token)
        if payload:
            profile = get_user_profile(payload["sub"])
            org_id = profile.get("organization_id") or payload.get("organization_id")
            tier = profile.get("subscription_tier", payload.get("tier", "free"))
            if org_id:
                tier = "enterprise"
            return {
                "user_id": payload["sub"],
                "email": payload.get("email") or profile.get("email", ""),
                "lang": payload.get("lang", query_params.get("lang", "zh")),
                "subscription_tier": tier,
                "trials_left": profile.get("free_trials_remaining", payload.get("trials_left", 0)),
                "organization_id": org_id,
            }
        st.error("登录凭证无效或已过期，请返回门户重新登录。")
        st.stop()

    user_id = query_params.get("user_id")
    email = query_params.get("email")
    if user_id and email:
        profile = get_user_profile(user_id)
        if profile.get("email") and profile.get("email") != email:
            st.error("登录信息不匹配，请返回门户重新登录。")
            st.stop()
        org_id = profile.get("organization_id")
        tier = profile.get("subscription_tier", "free")
        if org_id:
            tier = "enterprise"
        return {
            "user_id": user_id,
            "email": email,
            "lang": query_params.get("lang", "zh"),
            "subscription_tier": tier,
            "trials_left": profile.get("free_trials_remaining", 0),
            "organization_id": org_id,
        }

    return None


def require_portal_user() -> Dict[str, Any]:
    user = authenticate_from_portal()
    if user is None:
        st.error("未检测到门户登录信息，请返回 TechLife 门户重新登录。")
        st.stop()
    return user


def can_use_tool(user: Dict[str, Any]) -> bool:
    """检查用户是否有权限使用工具（以 profiles 表为准）"""
    if user.get("organization_id"):
        return True
    tier = user.get("subscription_tier")
    if tier in ("pro", "enterprise"):
        return True
    if user.get("trials_left", 0) > 0:
        return True
    st.warning("您的免费次数已用完，请返回门户升级订阅。")
    return False


def decrement_trial(user_id: str) -> bool:
    """免费用户使用后扣减 profiles.free_trials_remaining"""
    supabase = get_supabase_admin_client()
    if supabase is None:
        return False

    profile = get_user_profile(user_id)
    if profile.get("organization_id") or profile.get("subscription_tier") in ("pro", "enterprise"):
        return True

    remaining = profile.get("free_trials_remaining", 0)
    if remaining <= 0:
        return False

    try:
        supabase.table("profiles").update(
            {"free_trials_remaining": remaining - 1}
        ).eq("id", user_id).execute()
        return True
    except Exception as e:
        st.error(f"更新使用次数失败: {e}")
        return False


def get_subscription_display(user: Dict[str, Any], lang: str = "zh") -> Dict[str, Any]:
    tier = user.get("subscription_tier")
    is_pro = tier in ("pro", "enterprise")
    remaining = user.get("trials_left", 0)
    if lang == "zh":
        if tier == "enterprise":
            plan_text = "企业版"
        else:
            plan_text = "专业版" if is_pro else "免费版"
        remaining_text = "无限次使用" if is_pro else f"剩余免费次数: {max(0, remaining)}"
    else:
        if tier == "enterprise":
            plan_text = "Enterprise"
        else:
            plan_text = "Pro" if is_pro else "Free"
        remaining_text = "Unlimited" if is_pro else f"Free trial remaining: {max(0, remaining)}"
    return {
        "plan_text": plan_text,
        "remaining_text": remaining_text,
        "is_pro": is_pro,
        "remaining": remaining,
    }
