"""Innovation Analysis — standalone Streamlit Cloud app (TechLife child app).

Deploy: GitHub Laurenceku2026/Innovation-Analysis-SaaS, main file app.py.
Secrets (JWT, Supabase, AI) belong on this Cloud app, not the portal.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Tuple

import requests
import streamlit as st

from voc_web_search import (
    extract_json_object,
    format_channel_guide,
    format_search_block,
    format_tech_block,
    search_all_markets,
    search_patents_and_competitors,
)

ICON_COLOR = "#8EC8E8"
PORTAL_HOME_URL = "https://techlife-app.streamlit.app"

CHANNEL_ALIASES = {
    "amazon": "Amazon",
    "amz": "Amazon",
    "小红书": "Xiaohongshu",
    "xiaohongshu": "Xiaohongshu",
    "xhs": "Xiaohongshu",
    "red": "Xiaohongshu",
    "京东": "JD",
    "jd": "JD",
    "淘宝": "Taobao",
    "taobao": "Taobao",
    "天猫": "Tmall",
    "tmall": "Tmall",
    "reddit": "Reddit",
    "app store": "App Store",
    "appstore": "App Store",
    "google play": "Google Play",
    "访谈": "Interview",
    "interview": "Interview",
    "工单": "Support ticket",
    "售后": "Support ticket",
    "ticket": "Support ticket",
    "nps": "NPS/survey",
    "问卷": "NPS/survey",
    "survey": "NPS/survey",
    "youtube": "YouTube",
    "tiktok": "TikTok",
    "抖音": "Douyin",
    "微博": "Weibo",
    "facebook": "Facebook",
    "instagram": "Instagram",
}


def _secret(*keys: str, default: str = "") -> str:
    for key in keys:
        try:
            value = st.secrets.get(key)
        except Exception:
            value = None
        if value:
            return str(value)
        value = os.getenv(key)
        if value:
            return str(value)
    return default


def _supabase_config() -> Tuple[str, Dict[str, str]]:
    url = _secret("SUPABASE_STOCK_URL", "SUPABASE_URL").rstrip("/")
    key = _secret("SUPABASE_STOCK_SECRET_KEY", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_KEY")
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    return url, headers


def _ai_config() -> Tuple[str, str, str]:
    api_key = _secret("AI_API_KEY", "DEEPSEEK_API_KEY")
    base_url = _secret("AI_BASE_URL", "DEEPSEEK_BASE_URL", default="https://api.deepseek.com")
    model = _secret("AI_MODEL_NAME", "DEEPSEEK_MODEL", default="deepseek-chat")
    return api_key, base_url, model


def consume_trial(user_id: str, app_name: str = "innovation") -> Tuple[bool, int, str]:
    if st.session_state.get("organization_id"):
        return True, -1, ""
    url, headers = _supabase_config()
    if not url or not headers.get("apikey"):
        return True, st.session_state.get("trials_left", 30), ""
    try:
        resp = requests.get(f"{url}/rest/v1/profiles?id=eq.{user_id}", headers=headers, timeout=20)
        if resp.status_code != 200 or not resp.json():
            return False, 0, "用户不存在"
        row = resp.json()[0]
        if row.get("organization_id"):
            return True, -1, ""
        current = row.get("free_trials_remaining", 30)
        tier = row.get("subscription_tier", "free")
        if tier == "pro":
            return True, -1, ""
        if current <= 0:
            return False, 0, "免费次数已用完，请升级后继续使用"
        patch = requests.patch(
            f"{url}/rest/v1/profiles?id=eq.{user_id}",
            headers=headers,
            json={"free_trials_remaining": current - 1},
            timeout=20,
        )
        if patch.status_code not in (200, 204):
            return False, 0, f"更新失败: {patch.text}"
        requests.post(
            f"{url}/rest/v1/usage_logs",
            headers=headers,
            json={
                "user_id": user_id,
                "app_name": app_name,
                "analysis_count": 1,
                "used_at": datetime.now().isoformat(),
            },
            timeout=20,
        )
        return True, current - 1, ""
    except Exception as exc:
        return False, 0, f"计数失败: {exc}"


def split_user_items(raw: str) -> List[str]:
    items: List[str] = []
    for line in (raw or "").splitlines():
        text = re.sub(r"^[\s·•\-\d\.、）)\]]+", "", line).strip()
        if text:
            items.append(text)
    return items


def format_numbered_items(items: List[str], empty_label: str) -> str:
    if not items:
        return empty_label
    return "\n".join(f"{i}. {item}" for i, item in enumerate(items, start=1))


def parse_voc_paste(raw: str) -> Dict[str, Any]:
    items: List[Dict[str, str]] = []
    by_channel: Dict[str, int] = {}
    for line in (raw or "").splitlines():
        text = line.strip()
        if not text:
            continue
        channel = "Unspecified"
        body = text
        tagged = re.match(r"^\[([^\]]+)\]\s*(.*)$", text)
        colon = re.match(r"^([^:：]{1,24})[:：]\s*(.+)$", text)
        token = ""
        if tagged:
            token, body = tagged.group(1).strip(), tagged.group(2).strip() or text
        elif colon:
            token, body = colon.group(1).strip(), colon.group(2).strip()
        if token:
            key = token.lower()
            channel = CHANNEL_ALIASES.get(key, token)
        by_channel[channel] = by_channel.get(channel, 0) + 1
        items.append({"channel": channel, "text": body})
    return {
        "n": len(items),
        "by_channel": by_channel,
        "items": items,
    }


def voc_block_for_prompt(parsed: Dict[str, Any], lang: str) -> str:
    if parsed["n"] <= 0:
        if lang == "zh":
            return (
                "【VOC 原文】未提供。所有痛点必须标记证据等级 L4（模型假设），"
                "提及频率写“未知”，证据条数 n=0，样本量 N=0，不得编造评论条数或 URL。"
            )
        return (
            "[VOC corpus] Not provided. Mark every pain point as evidence grade L4 (model hypothesis). "
            "Frequency = Unknown, n=0, N=0. Do not invent review counts or URLs."
        )
    lines = [
        f"VOC_PASTED_COUNT={parsed['n']}",
        f"VOC_CHANNEL_COUNTS={json.dumps(parsed['by_channel'], ensure_ascii=False)}",
        "VOC_ITEMS_START",
    ]
    for i, item in enumerate(parsed["items"][:400], start=1):
        lines.append(f"{i}. [{item['channel']}] {item['text']}")
    lines.append("VOC_ITEMS_END")
    if lang == "zh":
        lines.append(
            "计数规则：n 只能来自以上条目；N 等于 VOC_PASTED_COUNT（或该渠道计数）。"
            "禁止把训练集记忆当成证据。未出现在列表中的痛点一律 L4。"
        )
    else:
        lines.append(
            "Counting rule: n may only come from the items above; N = VOC_PASTED_COUNT "
            "(or that channel's count). Never treat model memory as evidence. "
            "Pain points not in the list are L4."
        )
    return "\n".join(lines)


def markdown_to_docx(md_text: str, lang: str):
    from docx import Document
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, RGBColor

    def set_cell_border(cell):
        tc = cell._tc
        tc_pr = tc.get_or_add_tcPr()
        for edge in ("top", "left", "bottom", "right"):
            border = OxmlElement(f"w:{edge}")
            border.set(qn("w:val"), "single")
            border.set(qn("w:sz"), "4")
            border.set(qn("w:space"), "0")
            border.set(qn("w:color"), "CCCCCC")
            tc_pr.append(border)

    doc = Document()
    font_name = "Arial" if lang == "en" else "宋体"
    lines = md_text.split("\n")
    i = 0

    def parse_row(row: str) -> List[str]:
        cells = [cell.strip() for cell in row.split("|")]
        if cells and cells[0] == "":
            cells = cells[1:]
        if cells and cells[-1] == "":
            cells = cells[:-1]
        return cells

    while i < len(lines):
        line = lines[i]
        if line.startswith("# "):
            doc.add_heading(line[2:], level=1)
        elif line.startswith("## "):
            doc.add_heading(line[3:], level=2)
        elif line.startswith("### "):
            doc.add_heading(line[4:], level=3)
        elif line.startswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].startswith("|"):
                table_lines.append(lines[i].strip())
                i += 1
            if len(table_lines) >= 2:
                headers = parse_row(table_lines[0])
                data_lines = table_lines[2:] if len(table_lines) > 1 and "---" in table_lines[1] else table_lines[1:]
                num_cols = len(headers)
                if num_cols > 0:
                    table = doc.add_table(rows=1 + len(data_lines), cols=num_cols)
                    table.style = "Table Grid"
                    table.autofit = True
                    table.width = Inches(6.5)
                    for row in table.rows:
                        for cell in row.cells:
                            set_cell_border(cell)
                    for col_idx, cell_text in enumerate(headers):
                        cell = table.cell(0, col_idx)
                        cell.text = cell_text
                        for paragraph in cell.paragraphs:
                            for run in paragraph.runs:
                                run.font.bold = True
                                run.font.name = font_name
                    for row_idx, data_line in enumerate(data_lines):
                        cells = parse_row(data_line)
                        for col_idx, cell_text in enumerate(cells):
                            if col_idx < num_cols:
                                cell = table.cell(row_idx + 1, col_idx)
                                cell.text = cell_text
                                for paragraph in cell.paragraphs:
                                    for run in paragraph.runs:
                                        run.font.name = font_name
                    doc.add_paragraph()
            continue
        elif line.strip():
            p = doc.add_paragraph(line)
            for run in p.runs:
                run.font.name = font_name
        else:
            doc.add_paragraph()
        i += 1
    return doc


REPORT_PROMPT_ZH = """
你是 DFSS / 创新顾问。界面语言中文：全文用中文。用户输入可中可英。检索已覆盖：各市场中英文 VOC、用户描述主张核对、专利、竞品。
本报告必须按 Innovation 三支柱组织：**Desirability（想不想要）/ Viability（值不值得）/ Feasibility（能不能做成）**。
Desirability=痛点与 VOC；Viability=创新的商业价值；Feasibility=技术+专利空白+竞品（格式借鉴产品可行性报告的竞品与技术可行性章节）。

硬性规则：
1. 禁止编造 URL、专利号、竞品型号、条数。只能引用 VOC_BLOCK / SEARCH_BLOCK / TECH_BLOCK 中的条目。
2. 用户在输入框填写的「痛点」和「技术创新」必须全部出现在报告中并打分，一条都不能丢。痛点走 Desirability（P）；技术创新走 Feasibility（专利/竞品/T分）。产品简要描述作为补充背景。
3. 痛点优先级 P=0.3F+0.3S+0.2U+0.2W。创新机会表：Top {top_n} + 所有 P≥{pain_threshold}。
4. Viability 分 V：在有证据时用 0.4×付费意愿W + 0.3×可触达/渠道匹配 + 0.3×单位经济（溢价或替代成本）；缺证据写未知。
5. Feasibility 分 T：0.4×技术就绪（对照用户技术经验与预算）+ 0.3×IP空白（专利未覆盖或可规避）+ 0.3×与竞品差异可实现性。
6. 竞品分析按每个目标市场至少 3 个，表格列品牌、型号/系列、优势、劣势、定价区间；再做功能对比与市场空白（可行性报告 2.1–2.3 格式）。
7. 表格不得空；假设标明待验证。不要输出标题和基本信息表，从「三支柱总览」开始。

## 三支柱总览
用表格：支柱、1-10分、一句话结论、主要证据、最大缺口。三行分别为 Desirability / Viability / Feasibility。

---

# 支柱一　Desirability（用户想要吗 · 痛点）

## D1 用户输入痛点打分（必须覆盖全部用户痛点）
用户填写的痛点如下，必须逐条成表，不得合并丢掉：
{user_pains}
列：用户原话、VOC是否印证、F、S、U、W、P、是否≥阈值 {pain_threshold}、证据等级、n、引用。无 VOC 则 P 可为不可计算，但仍保留该行。

## D1b 产品描述补充主张
产品简要描述：{product_description}
仅补充用户痛点框未覆盖的主张。

## D2 证据盘点与分市场 VOC
每市场：信息渠道、中文检索、英文检索、YouTuber/测评/评论、该市场痛点。最后跨市场汇总。粘贴 {voc_n} 条，网页 VOC {search_n} 条。

## D3 信息获取渠道（尽量列全）
每市场一张表。必须覆盖 CHANNEL_GUIDE。
<<<CHANNEL_GUIDE>>>

## D4 JTBD 场景（按市场）

## D5 痛点清单与 P 分
用户输入痛点必须全部进入此表并打分，然后再补充检索发现的其他痛点。来源列标明「用户输入」或「检索发现」。

## D6 创新机会表（Desirability 输出）
Top {top_n} + P≥{pain_threshold}。列：排名、机会、痛点、P、是否过阈值、创新方向、CTQ线索、市场。

---

# 支柱二　Viability（创新有没有价值）

评价的是「解决该痛点能换回多少可持续价值」，不是再列一遍痛点。

## V1 价值主张
每个高 P 痛点/机会：谁付钱、为何现在付钱、替代方案成本、可要溢价、购买频次、渠道能否变现。W 在此展开。

## V2 市场与渠道价值（按市场，借鉴可行性报告）
每市场简表：需求规模量级（标假设）、渠道结构、客户现有渠道（{channel_status} / {channel_detail}）、品牌（{brand_status}）、变现适合度。

## V3 Viability 评分表
列：机会ID、对应痛点、可触达用户、愿付溢价、年价值潜力（可粗算并标假设）、渠道匹配、V分、证据。对照销售目标 {sales_target} 与预算 {estimated_budget}。

## V4 价值风险
伪需求、只叫好不付钱、价格战、渠道进不去、回本过长。

---

# 支柱三　Feasibility（技术能不能做成 · 专利与竞品）

## F1 用户输入技术创新打分（必须覆盖全部）
用户填写的技术创新如下，必须逐条成表：
{user_tech_innovations}
列：用户原话、专利检索结果（仅 TECH_BLOCK URL）、与本方案关系（阻挡/可规避/空白）、竞品是否已做、技术就绪、IP空白、可差异化、T分、风险。
未检索到写「本次未找到公开专利，空白待专业 FTO」，禁止编公开号。产品描述里多出来的技术点可作补充行。

## F2 关键技术要求（借鉴可行性 4.1）
列：技术项、对应痛点、量化指标、客户能力（{tech_experience}）、预算匹配（{estimated_budget}）、风险。

## F3 竞品分析（借鉴可行性 2.1–2.3）
### F3.1 每市场至少 3 个竞品（品牌、型号、优劣、定价）
### F3.2 关键功能对比（功能 vs 竞品A/B/C vs 本方案 vs 空白）
### F3.3 技术/市场空白点（哪些痛点竞品没做、哪些专利已占）
竞品型号仅当 SEARCH/TECH 中出现或明确标「行业常识假设」。

## F4 开发周期与技术风险（可行性 4.2–4.3 格式）
阶段-时间-任务；风险-可能性-影响-对策。开发阶段输入：{dev_stage}。

## F5 Feasibility 评分
T 分及理由：技术就绪、IP 空白、与竞品差异、资源匹配。

---

# 综合建议（三支柱合成）
### C1 对照表：Desirability / Viability / Feasibility 分数与能否进入开发
### C2 差异化定位 2–3 个选项
### C3 下一步 5 条：必须含 VOC 验证、专利 FTO/查新、竞品拆机或购买、渠道/定价实验

输入其他：{additional_info}

<<<VOC_BLOCK>>>
<<<SEARCH_BLOCK>>>
<<<TECH_BLOCK>>>

直接输出中文 Markdown。
"""

REPORT_PROMPT_EN = """
You are a DFSS / innovation advisor. UI language is English. Inputs may be Chinese or English.
Searches already cover: per-market Chinese+English VOC, verification of claims in the product description, patents, and competitors.
Organize the report around the three pillars of innovation: **Desirability / Viability / Feasibility**.
Desirability = pain points and VOC. Viability = commercial value of the innovation. Feasibility = technology + patent white space + competitors (borrow Product Feasibility report format for competitor and technical sections).

Hard rules:
1. Never invent URLs, patent numbers, competitor SKUs, or counts. Cite only VOC_BLOCK / SEARCH_BLOCK / TECH_BLOCK.
2. Every user-entered pain point and technical innovation MUST appear in the report and be scored. Pains → Desirability (P). Tech innovations → Feasibility (patents/competitors/T). Description is background only.
3. Pain priority P=0.3F+0.3S+0.2U+0.2W. Opportunity table: Top {top_n} plus all P>={pain_threshold}.
4. Viability score V = 0.4*WTP + 0.3*reach/channel fit + 0.3*unit economics when evidence exists.
5. Feasibility score T = 0.4*tech readiness (vs user experience and budget) + 0.3*IP white space + 0.3*differentiability vs competitors.
6. At least 3 competitors per target market (brand, model, pros/cons, price band), plus feature comparison and white space — same layout as Product Feasibility 2.1–2.3.
7. No empty cells. Start from "Three-pillar overview". Do not output title/basics table.

## Three-pillar overview
Table: pillar, score 1-10, one-line finding, main evidence, biggest gap. Rows: Desirability, Viability, Feasibility.

# Pillar 1 Desirability (do users want it)
## D1 Score every user-entered pain point
User pains (include every line, do not drop):
{user_pains}
Columns: user wording, VOC support?, F, S, U, W, P, ≥threshold {pain_threshold}?, evidence grade, n, citation.
## D1b Extra claims from the short description only if not already in the pain box.
Product description: {product_description}
## D2 Evidence and VOC by market (Chinese search, English search, YouTubers/reviews). Pasted {voc_n}, web VOC {search_n}. Then cross-market summary.
## D3 Information channels — cover CHANNEL_GUIDE
<<<CHANNEL_GUIDE>>>
## D4 JTBD by market
## D5 Pain register with P (all user-entered pains first, source=user vs search)
## D6 Opportunity table: Top {top_n} + P>={pain_threshold}

# Pillar 2 Viability (is the innovation worth it)
This is value, not a repeat of pains.
## V1 Value proposition per high-P pain: who pays, why now, substitute cost, price premium, frequency, channel capture. Expand W here.
## V2 Market and channel value by market (borrow Feasibility 1.1 / 3.x). Use {channel_status}, {channel_detail}, {brand_status}.
## V3 Viability score table vs {sales_target} and {estimated_budget}
## V4 Value risks (false demand, no WTP, channel lock-out, long payback)

# Pillar 3 Feasibility (can we build it — patents and competitors)
## F1 Score every user-entered technical innovation
User innovations (include every line):
{user_tech_innovations}
Columns: user wording, patent hits (TECH_BLOCK URLs only), relation (blocking / design-around / white space), already in competitors?, tech readiness, IP white space, differentiability, T score, risk.
If none found: "no public patent this run; FTO still required". Extra description-only tech can be extra rows.
## F2 Key technical requirements (Feasibility 4.1 style) vs {tech_experience} and {estimated_budget}
## F3 Competitor analysis (Feasibility 2.1–2.3)
F3.1 >=3 competitors per market; F3.2 feature comparison; F3.3 white space vs patents and competitor features.
## F4 Schedule and tech risks (4.2–4.3). Stage={dev_stage}
## F5 Feasibility score T

# Synthesis
C1 Go / no-go using the three scores
C2 2–3 positioning options
C3 Five next steps including VOC validation, patent FTO, competitor teardown, pricing/channel test

Other: {additional_info}

<<<VOC_BLOCK>>>
<<<SEARCH_BLOCK>>>
<<<TECH_BLOCK>>>

Output English Markdown only.
"""


TEXTS = {
    "zh": {
        "title": "创新分析",
        "back": "← 返回应用导航",
        "return_portal": "返回 TechLife 门户",
        "sidebar_analyst": "分析师信息",
        "sidebar_title": "分析说明",
        "sidebar_basis": "本模块用于：",
        "basis_items": [
            "Desirability：痛点是否真实、有多痛",
            "Viability：创新有没有商业价值（谁付钱）",
            "Feasibility：技术、专利空白与竞品",
            "用户描述中的技术创新会做专利/竞品核对",
        ],
        "analyst_name_label": "分析人姓名",
        "analyst_name_ph": "请输入分析师姓名",
        "analyst_title_label": "分析人头衔（可选）",
        "analyst_title_ph": "例如：产品经理、创新顾问",
        "api_status": "AI API 状态",
        "api_configured": "✅ 已配置",
        "api_not_configured": "❌ 未配置，请在 Secrets 中设置 AI_API_KEY 或 DEEPSEEK_API_KEY",
        "input_title": "📝 产品信息",
        "input_lang_hint": "中英文均可输入。界面语言只决定报告语言；检索会同时做中文检索和英文检索。",
        "basic_info": "基本信息",
        "product_name": "产品名称",
        "product_name_ph": "例如：宠物智能饮水机 / Smart pet fountain",
        "product_desc": "产品简要描述",
        "product_desc_ph": "产品是什么、给谁用、主功能。中英文均可。",
        "user_pains": "用户痛点（一行一条）",
        "user_pains_ph": "清洗困难，内壁发霉\n夜间噪音大，影响睡眠\n漏水泡坏地板",
        "user_pains_caption": "你认为的核心痛点。报告会逐条检索 VOC 并打 P 分（Desirability）。",
        "user_tech": "技术创新（一行一条）",
        "user_tech_ph": "可拆洗紫外杀菌模块\n流量传感误差<5%\n食品级水路无死角",
        "user_tech_caption": "你认为的技术创新。报告会逐条检索类似专利/竞品并打 Feasibility 分。",
        "target_markets": "目标市场",
        "market_options": ["中国大陆", "美国", "欧洲", "东南亚", "日本", "其他"],
        "custom_market": "其他市场（逗号分隔）",
        "target_users": "目标用户群体",
        "target_users_ph": "例如：25-40岁城市中产、养猫人群",
        "market_channel": "市场与销售渠道",
        "channel_status": "现有销售渠道情况",
        "channel_options": ["有成熟渠道", "有部分渠道", "渠道较弱", "无渠道/从零开始"],
        "channel_detail": "销售渠道详情",
        "channel_detail_ph": "例如：天猫旗舰店、京东自营、部分线下宠物店",
        "brand_status": "品牌认知度",
        "brand_options": ["高（知名）", "中（行业内有认知）", "低（需从零建设）"],
        "tech_capability": "技术能力",
        "tech_experience_label": "相关技术经验",
        "tech_experience_ph": "例如：智能硬件/IoT、App、结构、供应链",
        "dev_stage": "开发阶段",
        "stage_options": ["概念/想法", "调研中", "已立项", "开发中", "已有样机"],
        "business_goals": "商业目标",
        "estimated_budget_label": "预估研发预算",
        "estimated_budget_ph": "例如：50-100万，或具体金额",
        "sales_target": "首年销售目标",
        "sales_target_ph": "例如：1000万人民币",
        "other_info": "其他信息",
        "other_ph": "已有调研、竞品、特殊约束等",
        "voc_title": "VOC 证据（可选粘贴，中英文均可）",
        "voc_caption": "一行一条，中英文都行。格式：[渠道] 原文。系统还会按每个目标市场做中文+英文网页检索（YouTube、测评、评论）。",
        "voc_ph": "[Amazon] 清洗太麻烦，内壁发霉，已退货\n[小红书] 噪音太大晚上不敢开\n[访谈] 每周清洁要半小时，拆不干净\n[工单] 漏水泡坏地板要求赔偿",
        "voc_preview": "已识别粘贴 {n} 条，渠道分布：{channels}",
        "web_search_label": "按目标市场做中文+英文网页检索（YouTuber / 测评 / 评论）",
        "pain_threshold_label": "痛点纳入阈值 P（1–10）",
        "pain_threshold_help": "P=0.3×频次+0.3×严重度+0.2×未满足+0.2×付费意愿。第7部分先出 Top N；凡 P≥阈值的机会全部列入，所以可以多于 N 条。建议默认 6.0。",
        "top_n_label": "至少输出机会数（Top N）",
        "submit_btn": "🚀 开始创新分析",
        "product_name_missing": "请填写产品名称",
        "api_key_missing": "AI API Key 未配置",
        "generating": "正在分析证据与痛点量化…",
        "progress_preparing": "整理中英文检索词与 VOC 计数…",
        "progress_search": "按市场检索 VOC，并核对描述主张、专利与竞品…",
        "progress_analyzing": "按 Desirability / Viability / Feasibility 撰写中文报告…",
        "progress_finishing": "整理创新分析报告…",
        "error_prefix": "分析失败：",
        "report_title": "📄 创新分析报告",
        "download_section": "📥 下载",
        "download_btn": "下载 Word 文档",
        "download_excel": "下载 Excel（VOC 数据库）",
        "method_title": "痛点优先级 P 与阈值如何计算",
        "clear_btn": "清除报告并重新填写",
        "footer": "创新分析模块 · 证据优先于推断",
    },
    "en": {
        "title": "Innovation Analysis",
        "back": "← Back to app navigation",
        "return_portal": "Back to TechLife Portal",
        "sidebar_analyst": "Analyst",
        "sidebar_title": "About this module",
        "sidebar_basis": "This module is for:",
        "basis_items": [
            "Desirability: are pains real and how acute",
            "Viability: is the innovation worth money",
            "Feasibility: technology, patent white space, competitors",
            "Technical claims in the description are checked against patents",
        ],
        "analyst_name_label": "Analyst name",
        "analyst_name_ph": "Your name",
        "analyst_title_label": "Title (optional)",
        "analyst_title_ph": "e.g., Product Manager",
        "api_status": "AI API status",
        "api_configured": "✅ Configured",
        "api_not_configured": "❌ Missing AI_API_KEY or DEEPSEEK_API_KEY in Secrets",
        "input_title": "📝 Product information",
        "input_lang_hint": "Chinese or English input is fine. UI language only controls the report language. Search always runs in both Chinese and English.",
        "basic_info": "Basics",
        "product_name": "Product name",
        "product_name_ph": "e.g., Smart pet fountain / 宠物智能饮水机",
        "product_desc": "Short description",
        "product_desc_ph": "What it is, who it is for, main functions. Chinese or English.",
        "user_pains": "Pain points (one per line)",
        "user_pains_ph": "Hard to clean, mold inside\nToo noisy at night\nLeaks damage the floor",
        "user_pains_caption": "The pains you believe matter. Each will be VOC-checked and scored with P (Desirability).",
        "user_tech": "Technical innovations (one per line)",
        "user_tech_ph": "Detachable UV sterilization module\nFlow-sensor error <5%\nDead-corner-free food-grade water path",
        "user_tech_caption": "The innovations you claim. Each will be searched against patents/competitors and scored for Feasibility.",
        "target_markets": "Target markets",
        "market_options": ["Mainland China", "United States", "Europe", "Southeast Asia", "Japan", "Others"],
        "custom_market": "Other markets (comma separated)",
        "target_users": "Target users",
        "target_users_ph": "e.g., urban cat owners aged 25–40",
        "market_channel": "Market & sales channels",
        "channel_status": "Current sales-channel status",
        "channel_options": ["Mature channels", "Partial channels", "Weak channels", "No channels / start from scratch"],
        "channel_detail": "Sales-channel details",
        "channel_detail_ph": "e.g., Tmall flagship, JD, some pet stores",
        "brand_status": "Brand awareness",
        "brand_options": ["High (well-known)", "Medium (industry-known)", "Low (need to build)"],
        "tech_capability": "Technical capability",
        "tech_experience_label": "Relevant tech experience",
        "tech_experience_ph": "e.g., IoT, App, mechanical, supply chain",
        "dev_stage": "Development stage",
        "stage_options": ["Idea/Concept", "Researching", "Project approved", "Developing", "Prototype ready"],
        "business_goals": "Business goals",
        "estimated_budget_label": "Estimated R&D budget",
        "estimated_budget_ph": "e.g., 0.5–1M, or a specific amount",
        "sales_target": "First-year sales target",
        "sales_target_ph": "e.g., 10M RMB / 2M USD",
        "other_info": "Other information",
        "other_ph": "Existing research, competitors, constraints",
        "voc_title": "VOC evidence (optional paste; Chinese or English)",
        "voc_caption": "One item per line, Chinese or English. Format: [channel] quote. The app also runs Chinese+English web search per selected market (YouTube, reviews, comments).",
        "voc_ph": "[Amazon] Too hard to clean, mold inside, returned\n[Xiaohongshu] Too noisy at night\n[Interview] Weekly cleaning takes 30 minutes\n[Ticket] Leak damaged the floor",
        "voc_preview": "Recognized {n} pasted items, by channel: {channels}",
        "web_search_label": "Run Chinese+English web search per market (YouTubers / reviews / comments)",
        "pain_threshold_label": "Pain inclusion threshold P (1–10)",
        "pain_threshold_help": "P=0.3×frequency+0.3×severity+0.2×unmet+0.2×WTP. Part 7 always lists Top N, then adds every opportunity with P≥threshold (so it can exceed N). Default 6.0.",
        "top_n_label": "Minimum opportunities (Top N)",
        "submit_btn": "🚀 Start innovation analysis",
        "product_name_missing": "Please enter the product name",
        "api_key_missing": "AI API Key not configured",
        "generating": "Analyzing evidence and pain quantification…",
        "progress_preparing": "Preparing bilingual search terms and VOC counts…",
        "progress_search": "Searching VOC by market, plus patents and competitors for your claims…",
        "progress_analyzing": "Writing the English report across Desirability / Viability / Feasibility…",
        "progress_finishing": "Assembling the report…",
        "error_prefix": "Analysis failed: ",
        "report_title": "📄 Innovation Analysis Report",
        "download_section": "📥 Download",
        "download_btn": "Download Word",
        "download_excel": "Download Excel (VOC database)",
        "method_title": "How pain priority P and the threshold are calculated",
        "clear_btn": "Clear report and edit inputs",
        "footer": "Innovation Analysis · evidence before inference",
    },
}


def _call_llm(prompt: str, api_key: str, base_url: str, model: str, *, max_tokens: int = 8000, temperature: float = 0.3) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


def expand_bilingual_terms(
    product_name: str, product_description: str, api_key: str, base_url: str, model: str
) -> Tuple[str, str, List[Dict[str, str]]]:
    prompt = (
        "User text may be Chinese, English, or mixed. Return JSON only:\n"
        "{\"product_zh\":\"...\",\"product_en\":\"...\","
        "\"claims\":[{\"text\":\"...\",\"kind\":\"tech_innovation|user_benefit|feature\","
        "\"terms_zh\":\"...\",\"terms_en\":\"...\"}]}\n"
        "Extract EVERY concrete claim in the product description, especially technical innovations, "
        "mechanisms, materials, algorithms, structures. kind=tech_innovation for those. "
        "terms_zh/en are search phrases for patents and reviews. No markdown.\n\n"
        f"name: {product_name}\n"
        f"description: {product_description or ''}"
    )
    try:
        raw = _call_llm(prompt, api_key, base_url, model, max_tokens=900, temperature=0.1)
        data = extract_json_object(raw)
        zh = str(data.get("product_zh") or "").strip()
        en = str(data.get("product_en") or "").strip()
        claims = []
        for item in data.get("claims") or []:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            claims.append(
                {
                    "text": text,
                    "kind": str(item.get("kind") or "feature").strip(),
                    "terms_zh": str(item.get("terms_zh") or text).strip(),
                    "terms_en": str(item.get("terms_en") or text).strip(),
                }
            )
        return zh or product_name, en or product_name, claims
    except Exception:
        pass
    return product_name, product_name, []


def scoring_method_markdown(lang: str, threshold: float, top_n: int) -> str:
    if lang == "zh":
        return f"""## 痛点优先级与阈值计算方法

本次第 7 部分入选规则使用痛点优先级 **P（1–10 分）**：

**P = 0.3×F + 0.3×S + 0.2×U + 0.2×W**

| 符号 | 含义 | 怎么打分（1–10） |
|------|------|------------------|
| F 频次 | 有多少人遇到、提及有多密 | 有 VOC 时用提及率/条数；无证据则「未知」 |
| S 严重度 | 后果有多糟（安全、退货、工时、金钱） | 差评/退货/安全相关更高 |
| U 未满足 | 现有产品把这件事解决得有多差 | 竞品差评、反复吐槽更高 |
| W 付费意愿 | 用户是否愿意为解决它多付钱 | 访谈/溢价线索；无证据则「未知」 |

任一维度为「未知」时，**P 记为「不可计算」**，不得用假数字凑权重。

**入选第 7 部分创新机会表：**

1. 先按 P 从高到低列出至少 **Top {top_n}**（P 不可计算的排在后面，并标注假设）。
2. 凡 **P ≥ {threshold:g}** 的机会全部列入，因此行数可以多于 {top_n}。
3. P 不可计算的项目**不因阈值扩列**，除非已经进入 Top {top_n}。

默认阈值 6.0 表示「中等偏上、值得认真做」；调高更严、调低覆盖更多中等痛点。

## 创新三支柱如何评分

Innovation 报告分三块，避免只看痛点：

| 支柱 | 评价什么 | 分数 |
|------|----------|------|
| Desirability 想要吗 | 痛点是否真实、有多痛 | 主要看 P（及 VOC 证据等级） |
| Viability 值得吗 | 创新能否变成钱 | **V = 0.4×W + 0.3×可触达/渠道 + 0.3×单位经济** |
| Feasibility 做得到吗 | 技术、专利空白、竞品是否已占 | **T = 0.4×技术就绪 + 0.3×IP空白 + 0.3×与竞品可差异化** |

三支柱都高才建议投入开发；Desirability 高但 Viability 低 = 伪需求/不付钱；Desirability 高但 Feasibility 低 = 专利墙或做不出来。
"""
    return f"""## How pain priority P and the threshold are calculated

Part 7 uses pain priority **P (1–10)**:

**P = 0.3×F + 0.3×S + 0.2×U + 0.2×W**

| Symbol | Meaning | Scoring (1–10) |
|------|------|------------------|
| F frequency | How many people hit it / how often it is mentioned | Use mention rate when VOC exists; else Unknown |
| S severity | How bad the consequence is (safety, returns, time, money) | Higher if returns/safety |
| U unmet need | How poorly current products solve it | Higher if repeated competitor complaints |
| W willingness-to-pay | Whether users would pay more to fix it | Interview/price-premium clues; else Unknown |

If any factor is Unknown, **P = not computable**. Do not invent weights.

**Inclusion in the Part 7 opportunity table:**

1. List at least **Top {top_n}** by P (non-computable P last, marked hypothesis).
2. Include **every** opportunity with **P ≥ {threshold:g}**, so the table may exceed {top_n} rows.
3. Non-computable P is **not** added by the threshold unless it already made Top {top_n}.

Default 6.0 means "above-medium, worth doing seriously". Raise it to be stricter; lower it to include more mid pains.

## How the three innovation pillars are scored

| Pillar | What it asks | Score |
|------|------|------|
| Desirability | Do users want it? Are pains real? | Mainly P plus VOC evidence grade |
| Viability | Is the innovation worth money? | **V = 0.4×W + 0.3×reach/channel + 0.3×unit economics** |
| Feasibility | Can we build it? Patents and competitors | **T = 0.4×tech readiness + 0.3×IP white space + 0.3×differentiability** |

Enter development only if all three are strong. High Desirability + low Viability = nobody pays. High Desirability + low Feasibility = patent wall or cannot build.
"""


def report_header_markdown(
    *,
    lang: str,
    product_name: str,
    product_description: str,
    target_markets: str,
    target_users: str,
    tech_experience: str,
    estimated_budget: str,
    report_url: str,
    current_date: str,
    analyst_info: str,
    product_zh: str,
    product_en: str,
    user_pains: str,
    user_tech: str,
    voc_n: int,
    search_n: int,
    pain_threshold: float,
    top_n: int,
) -> str:
    if lang == "zh":
        return f"""# 《创新分析报告》
## {product_name}

**报告在线访问地址：{report_url}**

## 报告基本信息

| 项目 | 内容 |
|------|------|
| 产品名称 | {product_name} |
| 产品描述 | {product_description} |
| 用户输入痛点 | {user_pains} |
| 用户输入技术创新 | {user_tech} |
| 目标市场 | {target_markets} |
| 目标用户 | {target_users} |
| 相关技术经验 | {tech_experience} |
| 预估研发预算 | {estimated_budget} |
| 中文检索词 | {product_zh} |
| 英文检索词 | {product_en} |
| VOC 粘贴条数 | {voc_n} |
| 网页检索条数 | {search_n} |
| 分析框架 | Desirability / Viability / Feasibility |
| 痛点纳入阈值 P | {pain_threshold:g} |
| 至少输出机会数 | Top {top_n} |
| 报告日期 | {current_date} |
| 分析人 | {analyst_info} |

---
"""
    return f"""# Innovation Analysis Report
## {product_name}

**Online report URL: {report_url}**

## Report basics

| Item | Content |
|------|------|
| Product name | {product_name} |
| Description | {product_description} |
| User-stated pain points | {user_pains} |
| User-stated technical innovations | {user_tech} |
| Target markets | {target_markets} |
| Target users | {target_users} |
| Relevant tech experience | {tech_experience} |
| Estimated R&D budget | {estimated_budget} |
| Chinese search terms | {product_zh} |
| English search terms | {product_en} |
| Pasted VOC items | {voc_n} |
| Web VOC items | {search_n} |
| Framework | Desirability / Viability / Feasibility |
| Pain inclusion threshold P | {pain_threshold:g} |
| Minimum opportunities | Top {top_n} |
| Report date | {current_date} |
| Analyst | {analyst_info} |

---
"""


def build_voc_excel_bytes(
    *,
    lang: str,
    pasted: Dict[str, Any],
    search_payload: Dict[str, Any],
    tech_payload: Dict[str, Any] | None = None,
    claims: List[Dict[str, str]] | None = None,
    user_pains: List[str] | None = None,
    user_tech: List[str] | None = None,
    markets: List[str],
    meta: Dict[str, Any],
) -> bytes:
    import pandas as pd

    voc_cols = ["id", "source", "market", "query_lang", "channel", "content_type", "title", "text", "url", "query"]
    paste_rows = []
    for i, item in enumerate(pasted.get("items") or [], start=1):
        paste_rows.append(
            {
                "id": i,
                "source": "paste",
                "market": "",
                "query_lang": "",
                "channel": item.get("channel") or "",
                "content_type": "user_paste",
                "title": "",
                "text": item.get("text") or "",
                "url": "",
                "query": "",
            }
        )
    web_rows = []
    for i, hit in enumerate(search_payload.get("hits") or [], start=1):
        web_rows.append(
            {
                "id": i,
                "source": "web_search",
                "market": hit.get("market") or "",
                "query_lang": hit.get("query_lang") or "",
                "channel": hit.get("platform") or "",
                "content_type": hit.get("content_type") or "",
                "title": hit.get("title") or "",
                "text": hit.get("snippet") or "",
                "url": hit.get("url") or "",
                "query": hit.get("query") or "",
            }
        )
    tech_rows = []
    for i, hit in enumerate((tech_payload or {}).get("hits") or [], start=1):
        tech_rows.append(
            {
                "id": i,
                "source": hit.get("purpose") or "tech_search",
                "market": hit.get("market") or "",
                "query_lang": hit.get("query_lang") or "",
                "channel": hit.get("platform") or "",
                "content_type": hit.get("content_type") or "",
                "title": hit.get("title") or "",
                "text": hit.get("snippet") or "",
                "url": hit.get("url") or "",
                "query": hit.get("query") or "",
            }
        )
    claim_rows = []
    for i, claim in enumerate(claims or [], start=1):
        claim_rows.append(
            {
                "id": i,
                "kind": claim.get("kind") or "",
                "text": claim.get("text") or "",
                "terms_zh": claim.get("terms_zh") or "",
                "terms_en": claim.get("terms_en") or "",
            }
        )
    all_rows = paste_rows + [
        {**row, "id": len(paste_rows) + i} for i, row in enumerate(web_rows, start=1)
    ] + [
        {**row, "id": len(paste_rows) + len(web_rows) + i} for i, row in enumerate(tech_rows, start=1)
    ]
    channel_rows = []
    for market in markets:
        from voc_web_search import MARKET_PROFILES, normalize_market_key

        profile = MARKET_PROFILES[normalize_market_key(market)]
        key = "info_channels_zh" if lang == "zh" else "info_channels_en"
        for ch in profile.get(key) or []:
            channel_rows.append({"market": market, "information_channel": ch})

    method = {
        "item": [
            "P formula",
            "F",
            "S",
            "U",
            "W",
            "threshold",
            "top_n",
            "inclusion_rule",
            "Desirability",
            "Viability V",
            "Feasibility T",
        ],
        "value": [
            "P=0.3F+0.3S+0.2U+0.2W",
            "Frequency 1-10",
            "Severity 1-10",
            "Unmet need 1-10",
            "Willingness to pay 1-10",
            meta.get("pain_threshold"),
            meta.get("top_n"),
            "Top N plus all P>=threshold",
            "Pain priority P and VOC evidence",
            "V=0.4W+0.3reach/channel+0.3 unit economics",
            "T=0.4 tech readiness+0.3 IP white space+0.3 vs competitors",
        ],
    }
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        pd.DataFrame(all_rows, columns=voc_cols).to_excel(writer, index=False, sheet_name="VOC_database")
        pd.DataFrame(paste_rows, columns=voc_cols).to_excel(writer, index=False, sheet_name="VOC_pasted")
        pd.DataFrame(web_rows, columns=voc_cols).to_excel(writer, index=False, sheet_name="VOC_web_search")
        pd.DataFrame(tech_rows, columns=voc_cols).to_excel(writer, index=False, sheet_name="Patents_competitors")
        pd.DataFrame(claim_rows or [{"id": "", "kind": "", "text": "", "terms_zh": "", "terms_en": ""}]).to_excel(
            writer, index=False, sheet_name="User_claims"
        )
        pd.DataFrame(
            [{"id": i, "user_stated_pain": p} for i, p in enumerate(user_pains or [], start=1)]
            or [{"id": "", "user_stated_pain": ""}]
        ).to_excel(writer, index=False, sheet_name="User_stated_pains")
        pd.DataFrame(
            [{"id": i, "user_stated_tech": t} for i, t in enumerate(user_tech or [], start=1)]
            or [{"id": "", "user_stated_tech": ""}]
        ).to_excel(writer, index=False, sheet_name="User_stated_tech")
        pd.DataFrame(channel_rows or [{"market": "", "information_channel": ""}]).to_excel(
            writer, index=False, sheet_name="Info_channels"
        )
        pd.DataFrame(method).to_excel(writer, index=False, sheet_name="Scoring_method")
    buf.seek(0)
    return buf.getvalue()


def _title_html(label: str) -> str:
    return (
        f'<div style="display:flex;align-items:center;gap:12px;margin:0 0 0.4rem 0;">'
        f'<span style="display:inline-block;width:28px;height:28px;border-radius:8px;'
        f'background:{ICON_COLOR};flex-shrink:0;"></span>'
        f'<h1 style="margin:0;font-size:1.75rem;">{label}</h1></div>'
    )


def render_innovation_app(*, embedded: bool = False) -> None:
    lang = st.session_state.get("lang", "zh")
    if lang not in TEXTS:
        lang = "zh"
    t = TEXTS[lang]
    api_key, base_url, model = _ai_config()

    with st.sidebar:
        picked_lang = st.radio(
            "Language",
            options=["zh", "en"],
            format_func=lambda code: "中文" if code == "zh" else "English",
            index=0 if lang == "zh" else 1,
            key="inn_ui_lang",
            horizontal=True,
            label_visibility="collapsed",
        )
        if picked_lang != lang:
            st.session_state.lang = picked_lang
            st.rerun()
        st.markdown(f"### {t['sidebar_analyst']}")
        analyst_name = st.text_input(t["analyst_name_label"], placeholder=t["analyst_name_ph"], key="inn_analyst_name")
        analyst_title = st.text_input(t["analyst_title_label"], placeholder=t["analyst_title_ph"], key="inn_analyst_title")
        st.markdown(f"**{t['api_status']}**")
        if api_key:
            st.success(t["api_configured"])
        else:
            st.error(t["api_not_configured"])
        st.divider()
        st.markdown(f"### {t['sidebar_title']}")
        st.caption(t["sidebar_basis"])
        for item in t["basis_items"]:
            st.caption(f"• {item}")
        st.divider()
        portal_url = _secret("APP_BASE_URL", default=PORTAL_HOME_URL)
        st.link_button(t["return_portal"], portal_url, use_container_width=True)

    st.markdown(_title_html(t["title"]), unsafe_allow_html=True)
    st.caption(t["input_lang_hint"])

    st.markdown(f"### {t['input_title']}")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"#### {t['basic_info']}")
        product_name = st.text_input(t["product_name"], placeholder=t["product_name_ph"], key="inn_product_name")
        product_description = st.text_area(t["product_desc"], placeholder=t["product_desc_ph"], height=80, key="inn_product_desc")
        st.markdown(f"**{t['target_markets']}**")
        selected_markets = st.multiselect(
            t["target_markets"],
            options=t["market_options"],
            default=[t["market_options"][0]],
            label_visibility="collapsed",
            key="inn_markets",
        )
        custom_market = st.text_input(t["custom_market"], key="inn_custom_market")
        target_users = st.text_input(t["target_users"], placeholder=t["target_users_ph"], key="inn_target_users")
    with col2:
        st.markdown(f"#### {t['market_channel']}")
        channel_status = st.selectbox(t["channel_status"], options=t["channel_options"], key="inn_channel_status")
        channel_detail = st.text_area(t["channel_detail"], placeholder=t["channel_detail_ph"], height=80, key="inn_channel_detail")
        brand_status = st.selectbox(t["brand_status"], options=t["brand_options"], key="inn_brand_status")

    col_pain, col_tech_in = st.columns(2)
    with col_pain:
        st.markdown(f"#### {t['user_pains']}")
        st.caption(t["user_pains_caption"])
        user_pains_raw = st.text_area("", placeholder=t["user_pains_ph"], height=120, key="inn_user_pains")
    with col_tech_in:
        st.markdown(f"#### {t['user_tech']}")
        st.caption(t["user_tech_caption"])
        user_tech_raw = st.text_area("", placeholder=t["user_tech_ph"], height=120, key="inn_user_tech")

    st.markdown(f"#### {t['tech_capability']}")
    col3, col4 = st.columns(2)
    with col3:
        tech_experience = st.text_area(t["tech_experience_label"], placeholder=t["tech_experience_ph"], height=80, key="inn_tech")
    with col4:
        dev_stage = st.selectbox(t["dev_stage"], options=t["stage_options"], key="inn_stage")

    st.markdown(f"#### {t['business_goals']}")
    col5, col6 = st.columns(2)
    with col5:
        estimated_budget = st.text_input(t["estimated_budget_label"], placeholder=t["estimated_budget_ph"], key="inn_budget")
    with col6:
        sales_target = st.text_input(t["sales_target"], placeholder=t["sales_target_ph"], key="inn_sales")

    st.markdown(f"#### {t['other_info']}")
    additional_info = st.text_area("", placeholder=t["other_ph"], height=80, key="inn_other")

    st.markdown(f"#### {t['pain_threshold_label']}")
    st.caption(t["pain_threshold_help"])
    col_th, col_n, col_web = st.columns([2, 2, 3])
    with col_th:
        pain_threshold = st.slider(
            t["pain_threshold_label"],
            min_value=1.0,
            max_value=10.0,
            value=6.0,
            step=0.5,
            key="inn_pain_threshold",
            label_visibility="collapsed",
        )
    with col_n:
        top_n = st.number_input(t["top_n_label"], min_value=5, max_value=30, value=10, step=1, key="inn_top_n")
    with col_web:
        do_web_search = st.checkbox(t["web_search_label"], value=True, key="inn_web_search")

    st.markdown(f"#### {t['voc_title']}")
    st.caption(t["voc_caption"])
    voc_raw = st.text_area("", placeholder=t["voc_ph"], height=160, key="inn_voc")
    parsed_voc = parse_voc_paste(voc_raw)
    if parsed_voc["n"]:
        st.info(t["voc_preview"].format(n=parsed_voc["n"], channels=json.dumps(parsed_voc["by_channel"], ensure_ascii=False)))

    st.markdown("---")
    submitted = st.button(t["submit_btn"], type="primary", use_container_width=True, key="inn_submit")
    progress_slot = st.empty()

    if submitted:
        if not product_name:
            st.error(t["product_name_missing"])
        elif not api_key:
            st.error(t["api_key_missing"])
        else:
            user_id = st.session_state.get("user_id") or ""
            allowed, _remaining, error_msg = consume_trial(str(user_id)) if user_id else (True, 0, "")
            if not allowed:
                st.error(error_msg)
            else:
                progress = progress_slot.progress(0, text=t["progress_preparing"])
                try:
                    markets = list(selected_markets)
                    if custom_market.strip():
                        markets.extend([m.strip() for m in custom_market.split(",") if m.strip()])
                    if analyst_name:
                        analyst_info = f"{analyst_name} ({analyst_title})" if analyst_title else analyst_name
                    else:
                        analyst_info = "创新分析师" if lang == "zh" else "Innovation analyst"

                    user_pain_items = split_user_items(user_pains_raw)
                    user_tech_items = split_user_items(user_tech_raw)
                    desc_for_expand = "\n".join(
                        [
                            product_description or "",
                            "PAINS:\n" + "\n".join(user_pain_items),
                            "TECH:\n" + "\n".join(user_tech_items),
                        ]
                    )
                    product_zh, product_en, claims = expand_bilingual_terms(
                        product_name, desc_for_expand, api_key, base_url, model
                    )
                    existing = {(c.get("text") or "").strip().lower() for c in claims}
                    for item in user_tech_items:
                        if item.lower() not in existing:
                            claims.append(
                                {
                                    "text": item,
                                    "kind": "tech_innovation",
                                    "terms_zh": item,
                                    "terms_en": item,
                                }
                            )
                            existing.add(item.lower())
                    search_payload = {"n": 0, "hits": [], "by_market": {}, "errors": []}
                    tech_payload = {"n": 0, "hits": [], "errors": []}
                    if do_web_search:
                        progress.progress(20, text=t["progress_search"])
                        search_payload = search_all_markets(
                            markets, product_zh, product_en, extra_terms=user_pain_items
                        )
                        progress.progress(40, text=t["progress_search"])
                        tech_payload = search_patents_and_competitors(product_zh, product_en, claims)
                    voc_block = voc_block_for_prompt(parsed_voc, lang)
                    search_block = format_search_block(search_payload, lang)
                    tech_block = format_tech_block(tech_payload, claims, lang)
                    channel_guide = format_channel_guide(markets, lang)
                    template = REPORT_PROMPT_ZH if lang == "zh" else REPORT_PROMPT_EN
                    missing = "未提供" if lang == "zh" else "Not provided"
                    pains_text = format_numbered_items(user_pain_items, missing)
                    tech_text = format_numbered_items(user_tech_items, missing)
                    prompt = (
                        template.format(
                            product_name=product_name,
                            product_zh=product_zh,
                            product_en=product_en,
                            product_description=product_description or missing,
                            user_pains=pains_text,
                            user_tech_innovations=tech_text,
                            target_markets=", ".join(markets) or missing,
                            target_users=target_users or missing,
                            channel_status=channel_status,
                            channel_detail=channel_detail or missing,
                            brand_status=brand_status,
                            tech_experience=tech_experience or missing,
                            estimated_budget=estimated_budget or missing,
                            dev_stage=dev_stage,
                            sales_target=sales_target or missing,
                            additional_info=additional_info or missing,
                            voc_n=parsed_voc["n"],
                            search_n=search_payload.get("n", 0),
                            voc_channel_counts=json.dumps(parsed_voc["by_channel"], ensure_ascii=False),
                            pain_threshold=pain_threshold,
                            top_n=int(top_n),
                        )
                        .replace("<<<VOC_BLOCK>>>", voc_block)
                        .replace("<<<SEARCH_BLOCK>>>", search_block)
                        .replace("<<<TECH_BLOCK>>>", tech_block)
                        .replace("<<<CHANNEL_GUIDE>>>", channel_guide)
                    )
                    progress.progress(55, text=t["progress_analyzing"])
                    body = _call_llm(prompt, api_key, base_url, model)
                    progress.progress(85, text=t["progress_finishing"])
                    if lang == "zh":
                        current_date = datetime.now().strftime("%Y年%m月%d日")
                    else:
                        current_date = datetime.now().strftime("%B %d, %Y")
                    body = body.replace("{{CURRENT_DATE}}", current_date)
                    body = body.replace("{{{{CURRENT_DATE}}}}", current_date)
                    body = body.replace("{{ANALYST_INFO}}", analyst_info)
                    body = body.replace("{{{{ANALYST_INFO}}}}", analyst_info)
                    body = re.sub(r"\*+", "", body)
                    report_url = _secret("APP_BASE_URL", default="https://techlife-app.streamlit.app")
                    header = report_header_markdown(
                        lang=lang,
                        product_name=product_name,
                        product_description=product_description or missing,
                        user_pains="；".join(user_pain_items) if user_pain_items else missing,
                        user_tech="；".join(user_tech_items) if user_tech_items else missing,
                        target_markets=", ".join(markets) or missing,
                        target_users=target_users or missing,
                        tech_experience=tech_experience or missing,
                        estimated_budget=estimated_budget or missing,
                        report_url=report_url,
                        current_date=current_date,
                        analyst_info=analyst_info,
                        product_zh=product_zh,
                        product_en=product_en,
                        voc_n=parsed_voc["n"],
                        search_n=int(search_payload.get("n") or 0),
                        pain_threshold=float(pain_threshold),
                        top_n=int(top_n),
                    )
                    method = scoring_method_markdown(lang, float(pain_threshold), int(top_n))
                    report = header + "\n" + method + "\n---\n\n" + body.lstrip()
                    st.session_state.innovation_report = report
                    st.session_state.innovation_report_lang = lang
                    st.session_state.innovation_product_name = product_name
                    st.session_state.innovation_search_n = search_payload.get("n", 0)
                    st.session_state.innovation_method = method
                    st.session_state.innovation_voc_excel = build_voc_excel_bytes(
                        lang=lang,
                        pasted=parsed_voc,
                        search_payload=search_payload,
                        tech_payload=tech_payload,
                        claims=claims,
                        user_pains=user_pain_items,
                        user_tech=user_tech_items,
                        markets=markets,
                        meta={"pain_threshold": float(pain_threshold), "top_n": int(top_n)},
                    )
                    progress.progress(100, text=t["generating"])
                    progress_slot.empty()
                except Exception as exc:
                    progress_slot.empty()
                    st.error(f"{t['error_prefix']}{exc}")

    report = st.session_state.get("innovation_report")
    if report:
        report_lang = st.session_state.get("innovation_report_lang")
        if report_lang and report_lang != lang:
            st.warning(
                "当前报告按生成时的界面语言撰写。切换中/英文后请重新分析以得到对应语言报告。"
                if lang == "zh"
                else "This report was written in the UI language at generation time. Re-run analysis after switching Chinese/English."
            )
        search_n = st.session_state.get("innovation_search_n")
        if search_n is not None:
            st.caption(
                f"网页检索命中 {search_n} 条（中文+英文，按市场）" if lang == "zh" else f"Web VOC hits: {search_n} (Chinese + English, by market)"
            )
        st.markdown("---")
        st.markdown(report)
        method = st.session_state.get("innovation_method") or ""
        if method:
            with st.expander(t["method_title"], expanded=True):
                st.markdown(method)
        st.markdown("---")
        st.markdown(f"### {t['download_section']}")
        fname = st.session_state.get("innovation_product_name") or "innovation"
        safe_name = re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", fname)
        dl1, dl2 = st.columns(2)
        with dl1:
            try:
                doc = markdown_to_docx(report, lang)
                buf = BytesIO()
                doc.save(buf)
                buf.seek(0)
                st.download_button(
                    t["download_btn"],
                    data=buf,
                    file_name=f"{safe_name}_Innovation_Analysis.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="inn_dl_docx",
                    use_container_width=True,
                )
            except Exception:
                st.caption("Word 导出需要 python-docx" if lang == "zh" else "Word export requires python-docx")
        with dl2:
            excel_bytes = st.session_state.get("innovation_voc_excel")
            if excel_bytes:
                st.download_button(
                    t["download_excel"],
                    data=excel_bytes,
                    file_name=f"{safe_name}_VOC_database.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="inn_dl_xlsx",
                    use_container_width=True,
                )
        if st.button(t["clear_btn"], key="inn_clear"):
            st.session_state.innovation_report = None
            st.session_state.innovation_voc_excel = None
            st.session_state.innovation_method = None
            st.rerun()
    else:
        st.caption(t["footer"])


def run_standalone() -> None:
    """Streamlit entry for a dedicated Cloud app, or portal ?app=innovation."""
    try:
        st.set_page_config(page_title="Innovation Analysis", page_icon="🔹", layout="wide")
    except Exception:
        pass
    from subscription_utils import require_portal_user

    user = require_portal_user()
    st.session_state.user_id = user["user_id"]
    st.session_state.user_email = user.get("email")
    st.session_state.lang = user.get("lang") or st.session_state.get("lang", "zh")
    if user.get("organization_id"):
        st.session_state.organization_id = user["organization_id"]
    st.session_state.trials_left = user.get("trials_left", 0)
    render_innovation_app(embedded=False)


if __name__ == "__main__":
    run_standalone()
