# Innovation Analysis

Independent TechLife child app (same pattern as Product Feasibility SaaS).

Users log into [TechLife Portal](https://techlife-app.streamlit.app), then click **进入** on 创新分析. The portal opens this Streamlit app in a new tab with a signed token.

## Streamlit Cloud

1. [share.streamlit.io](https://share.streamlit.io) → **New app**
2. Repository: `Laurenceku2026/Innovation-Analysis-SaaS`
3. Branch: `main`
4. Main file: `app.py`
5. Paste Secrets from `secrets.example.toml` (JWT + Supabase must match the portal; AI keys live only here)

Public URL: `https://innovation-analysis.streamlit.app`

If Streamlit assigns a different URL, set `INNOVATION_APP_URL` in the portal Cloud secrets.
