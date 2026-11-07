"""Per-market bilingual VOC web search (Chinese + English + local platforms)."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse


MARKET_PROFILES: Dict[str, Dict[str, Any]] = {
    "china": {
        "label_zh": "中国大陆",
        "label_en": "Mainland China",
        "region_zh": "cn-zh",
        "region_en": "wt-wt",
        "platforms": ["Douyin", "Bilibili", "JD", "Tmall", "Xiaohongshu", "Zhihu", "Hardware store", "Trade show"],
        "info_channels_zh": [
            "抖音（短视频种草/避雷）",
            "B站（长测评/拆机）",
            "京东/天猫评价与问大家",
            "小红书笔记",
            "知乎问答",
            "五金店/经销商老板推荐",
            "行业展会（广交会、五金展、照明展等）",
            "微信行业群与师傅社群口碑",
            "售后工单/安装师傅反馈",
        ],
        "info_channels_en": [
            "Douyin",
            "Bilibili reviews",
            "JD/Tmall reviews",
            "Xiaohongshu",
            "Zhihu",
            "Hardware-store owner recommendation",
            "Trade shows (Canton Fair, hardware/lighting shows)",
            "WeChat trade groups / installer word-of-mouth",
            "After-sales tickets",
        ],
        "site_hints_zh": [
            "{p} 测评",
            "{p} site:bilibili.com 测评",
            "{p} site:jd.com 评价",
            "{p} 抖音 缺点",
            "{p} 五金店 推荐",
            "{p} 展会 评价",
        ],
        "site_hints_en": [
            "{p} review China",
            "{p} site:youtube.com review",
            "{p} JD Tmall review",
        ],
    },
    "usa": {
        "label_zh": "美国",
        "label_en": "United States",
        "region_zh": "wt-wt",
        "region_en": "us-en",
        "platforms": ["YouTube", "Home Depot", "Lowe's", "ContractorTalk", "Amazon", "Reddit"],
        "info_channels_zh": [
            "Home Depot / Lowe's 门店导购与货架评价",
            "YouTube 测评与安装视频",
            "专业论坛 ContractorTalk / Reddit",
            "Amazon / 品牌站评论",
            "承包商/工匠口碑推荐",
            "行业展会（IBS、LightFair 等）",
            "专业杂志与买家指南（Wirecutter 等）",
        ],
        "info_channels_en": [
            "Home Depot / Lowe's store staff and shelf reviews",
            "YouTube reviews and install videos",
            "Pro forums (ContractorTalk, Reddit)",
            "Amazon / brand-site reviews",
            "Contractor / tradesperson word-of-mouth",
            "Trade shows (IBS, LightFair)",
            "Pro magazines and buying guides (Wirecutter)",
        ],
        "site_hints_zh": [
            "{p} 美国 测评",
            "{p} site:youtube.com 评测",
        ],
        "site_hints_en": [
            "{p} site:youtube.com review",
            "{p} site:homedepot.com review",
            "{p} site:lowes.com review",
            "{p} site:contractortalk.com",
            "{p} site:amazon.com review",
            "{p} site:reddit.com problem",
        ],
    },
    "europe": {
        "label_zh": "欧洲",
        "label_en": "Europe",
        "region_zh": "wt-wt",
        "region_en": "uk-en",
        "platforms": ["Distributor", "EISENWARENMESSE", "Pro magazine", "YouTube", "Trustpilot", "Craftsman community"],
        "info_channels_zh": [
            "专业经销商/电气五金批发商推荐",
            "行业展会（科隆五金展 EISENWARENMESSE、Light+Building 等）",
            "专业杂志与行业协会刊物",
            "工匠/安装工社群口碑",
            "YouTube 德语/英语测评",
            "Amazon.de / Trustpilot 评论",
            "门店与 visagiste/installateur 口碑",
        ],
        "info_channels_en": [
            "Specialist distributors / electrical-hardware wholesalers",
            "Trade shows (EISENWARENMESSE Cologne, Light+Building)",
            "Professional magazines and association journals",
            "Craftsman / installer community word-of-mouth",
            "YouTube DE/EN reviews",
            "Amazon.de / Trustpilot reviews",
            "Trade-counter recommendations",
        ],
        "site_hints_zh": [
            "{p} 欧洲 测评",
            "{p} site:youtube.com 评测",
        ],
        "site_hints_en": [
            "{p} EISENWARENMESSE",
            "{p} site:youtube.com review",
            "{p} site:trustpilot.com review",
            "{p} site:amazon.de review",
            "{p} electrician review Europe",
        ],
    },
    "sea": {
        "label_zh": "东南亚",
        "label_en": "Southeast Asia",
        "region_zh": "wt-wt",
        "region_en": "sg-en",
        "platforms": ["Shopee", "Lazada", "YouTube", "TikTok", "Trade counter"],
        "info_channels_zh": [
            "Shopee / Lazada 评价",
            "YouTube / TikTok 测评",
            "五金店与经销商柜台推荐",
            "行业展会（泰国、越南、印尼建材展）",
            "WhatsApp/Facebook 工匠群口碑",
        ],
        "info_channels_en": [
            "Shopee / Lazada reviews",
            "YouTube / TikTok reviews",
            "Hardware-store / distributor counter advice",
            "Regional building-material trade shows",
            "WhatsApp/Facebook trades groups",
        ],
        "site_hints_zh": [
            "{p} 东南亚 测评",
            "{p} site:youtube.com 评测",
        ],
        "site_hints_en": [
            "{p} Shopee review",
            "{p} Lazada review",
            "{p} site:youtube.com review",
        ],
    },
    "japan": {
        "label_zh": "日本",
        "label_en": "Japan",
        "region_zh": "wt-wt",
        "region_en": "jp-jp",
        "platforms": ["YouTube", "Amazon.jp", "Kakaku", "Hardware store", "Trade show"],
        "info_channels_zh": [
            "YouTube / ニコニコ 测评",
            "Amazon.co.jp / 乐天评论",
            "价格网 Kakaku.com",
            "家电量贩店/五金店店员推荐",
            "行业展会（Tokyo Gift Show、照明展）",
            "2ch/5ch 与工匠社群",
        ],
        "info_channels_en": [
            "YouTube reviews",
            "Amazon.co.jp / Rakuten reviews",
            "Kakaku.com",
            "Electronics/hardware store staff",
            "Trade shows",
            "Forums and trades communities",
        ],
        "site_hints_zh": [
            "{p} 日本 测评",
            "{p} site:youtube.com 开箱",
        ],
        "site_hints_en": [
            "{p} site:youtube.com review",
            "{p} site:amazon.co.jp review",
            "{p} site:kakaku.com",
        ],
    },
    "other": {
        "label_zh": "其他市场",
        "label_en": "Other markets",
        "region_zh": "wt-wt",
        "region_en": "wt-wt",
        "platforms": ["YouTube", "Amazon", "Trade show", "Distributor"],
        "info_channels_zh": [
            "YouTube 测评",
            "电商评论",
            "专业经销商",
            "行业展会",
            "工匠/用户社群口碑",
        ],
        "info_channels_en": [
            "YouTube reviews",
            "E-commerce reviews",
            "Specialist distributors",
            "Trade shows",
            "Trades / user community word-of-mouth",
        ],
        "site_hints_zh": ["{p} 测评", "{p} site:youtube.com 评测"],
        "site_hints_en": ["{p} review", "{p} site:youtube.com review"],
    },
}

_ALIAS = {
    "中国大陆": "china",
    "中国": "china",
    "mainland china": "china",
    "china": "china",
    "prc": "china",
    "美国": "usa",
    "united states": "usa",
    "usa": "usa",
    "us": "usa",
    "欧洲": "europe",
    "europe": "europe",
    "eu": "europe",
    "uk": "europe",
    "东南亚": "sea",
    "southeast asia": "sea",
    "sea": "sea",
    "asean": "sea",
    "日本": "japan",
    "japan": "japan",
    "jp": "japan",
    "其他": "other",
    "others": "other",
    "other": "other",
}


def normalize_market_key(name: str) -> str:
    raw = (name or "").strip()
    key = _ALIAS.get(raw, _ALIAS.get(raw.lower(), "other"))
    return key


def market_label(name: str, lang: str) -> str:
    profile = MARKET_PROFILES[normalize_market_key(name)]
    return profile["label_zh"] if lang == "zh" else profile["label_en"]


def _platform_from_url(url: str) -> str:
    host = (urlparse(url).netloc or "").lower()
    mapping = (
        ("youtube.com", "YouTube"),
        ("youtu.be", "YouTube"),
        ("bilibili.com", "Bilibili"),
        ("xiaohongshu.com", "Xiaohongshu"),
        ("xhslink.com", "Xiaohongshu"),
        ("zhihu.com", "Zhihu"),
        ("jd.com", "JD"),
        ("tmall.com", "Tmall"),
        ("taobao.com", "Taobao"),
        ("amazon.", "Amazon"),
        ("reddit.com", "Reddit"),
        ("tiktok.com", "TikTok"),
        ("douyin.com", "Douyin"),
        ("trustpilot.com", "Trustpilot"),
        ("shopee.", "Shopee"),
        ("lazada.", "Lazada"),
        ("kakaku.com", "Kakaku"),
        ("wirecutter.com", "Wirecutter"),
        ("homedepot.com", "Home Depot"),
        ("lowes.com", "Lowe's"),
        ("contractortalk.com", "ContractorTalk"),
        ("eisenwarenmesse.com", "EISENWARENMESSE"),
        ("koelnmesse.com", "EISENWARENMESSE"),
        ("patents.google.com", "Google Patents"),
        ("uspto.gov", "USPTO"),
        ("epo.org", "EPO"),
        ("espacenet.com", "Espacenet"),
        ("cnipa.gov.cn", "CNIPA"),
        ("soopat.com", "SooPAT"),
        ("patsnap.com", "PatSnap"),
        ("lens.org", "Lens.org"),
    )
    for needle, label in mapping:
        if needle in host:
            return label
    return host or "Web"


def _content_type(platform: str, title: str, snippet: str) -> str:
    blob = f"{title} {snippet}".lower()
    if "patent" in platform.lower() or any(w in blob for w in ("patent", "专利", "uspto", "epo", "cnipa")):
        return "Patent"
    if platform == "YouTube" or "youtuber" in blob or "vlog" in blob:
        return "YouTuber/video"
    if any(w in blob for w in ("竞品", "competitor", "alternative", " vs ")):
        return "Competitor"
    if any(w in blob for w in ("测评", "评测", "开箱", "review", "unboxing", "hands-on")):
        return "User/editor review"
    if any(w in blob for w in ("reddit", "complaint", "缺点", "差评", "problem", "issue")):
        return "User complaint"
    return "Web mention"


def _ddg_search(query: str, region: str, max_results: int) -> List[Dict[str, str]]:
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS  # type: ignore
    except ImportError as exc:
        raise RuntimeError("missing_ddgs") from exc

    rows: List[Dict[str, str]] = []
    with DDGS() as client:
        for item in client.text(query, region=region, max_results=max_results, safesearch="moderate"):
            rows.append(
                {
                    "title": (item.get("title") or "").strip(),
                    "snippet": (item.get("body") or item.get("description") or "").strip(),
                    "url": (item.get("href") or item.get("url") or "").strip(),
                }
            )
    return rows


def search_market_voc(
    market_name: str,
    product_zh: str,
    product_en: str,
    *,
    max_per_query: int = 5,
    max_queries_per_lang: int = 5,
) -> Tuple[List[Dict[str, str]], List[str]]:
    """Return (hits, errors). Always attempts Chinese + English queries."""
    profile = MARKET_PROFILES[normalize_market_key(market_name)]
    hits: List[Dict[str, str]] = []
    errors: List[str] = []
    seen = set()

    jobs = [
        ("zh", product_zh or product_en, profile["site_hints_zh"], profile["region_zh"]),
        ("en", product_en or product_zh, profile["site_hints_en"], profile["region_en"]),
    ]
    for query_lang, product, hints, region in jobs:
        product = (product or "").strip()
        if not product:
            continue
        for hint in hints[:max_queries_per_lang]:
            query = hint.format(p=product)
            try:
                results = _ddg_search(query, region, max_per_query)
            except Exception as exc:
                errors.append(f"{market_name}/{query_lang}: {exc}")
                continue
            for item in results:
                url = item.get("url") or ""
                key = url or f"{item.get('title')}|{item.get('snippet')}"
                if not key or key in seen:
                    continue
                seen.add(key)
                platform = _platform_from_url(url)
                hits.append(
                    {
                        "market": market_name,
                        "query_lang": query_lang,
                        "query": query,
                        "platform": platform,
                        "content_type": _content_type(platform, item.get("title") or "", item.get("snippet") or ""),
                        "title": item.get("title") or "",
                        "snippet": item.get("snippet") or "",
                        "url": url,
                    }
                )
    return hits, errors


def search_all_markets(
    markets: List[str],
    product_zh: str,
    product_en: str,
    extra_terms: List[str] | None = None,
) -> Dict[str, Any]:
    all_hits: List[Dict[str, str]] = []
    all_errors: List[str] = []
    by_market: Dict[str, List[Dict[str, str]]] = {}
    extras = [t.strip() for t in (extra_terms or []) if t and t.strip()][:4]
    for market in markets:
        hits, errors = search_market_voc(market, product_zh, product_en)
        for term in extras:
            more, more_err = search_market_voc(
                market, term, term, max_per_query=3, max_queries_per_lang=2
            )
            hits.extend(more)
            errors.extend(more_err)
        by_market[market] = hits
        all_hits.extend(hits)
        all_errors.extend(errors)
    return {
        "n": len(all_hits),
        "hits": all_hits,
        "by_market": by_market,
        "errors": all_errors,
    }


def search_patents_and_competitors(
    product_zh: str,
    product_en: str,
    claims: List[Dict[str, str]],
) -> Dict[str, Any]:
    """Search patents and competitor landscape for user-described innovations."""
    hits: List[Dict[str, str]] = []
    errors: List[str] = []
    seen = set()
    queries: List[Tuple[str, str, str, str]] = []  # query, region, lang, purpose

    p_zh = (product_zh or product_en or "").strip()
    p_en = (product_en or product_zh or "").strip()
    if p_zh:
        queries.extend(
            [
                (f"{p_zh} 专利", "cn-zh", "zh", "patent"),
                (f"site:patents.google.com {p_zh}", "wt-wt", "zh", "patent"),
                (f"{p_zh} 竞品", "cn-zh", "zh", "competitor"),
            ]
        )
    if p_en:
        queries.extend(
            [
                (f"site:patents.google.com {p_en}", "wt-wt", "en", "patent"),
                (f"{p_en} patent USPTO", "us-en", "en", "patent"),
                (f"{p_en} vs competitor", "us-en", "en", "competitor"),
                (f"{p_en} alternative review", "us-en", "en", "competitor"),
            ]
        )
    for claim in (claims or [])[:6]:
        kind = (claim.get("kind") or "").lower()
        zh_t = (claim.get("terms_zh") or claim.get("text") or "").strip()
        en_t = (claim.get("terms_en") or claim.get("text") or "").strip()
        if kind in ("tech_innovation", "tech", "patent", "feature") or True:
            if zh_t:
                queries.append((f"{zh_t} 专利", "cn-zh", "zh", "claim_patent"))
                queries.append((f"{zh_t} 测评 是否属实", "cn-zh", "zh", "claim_confirm"))
            if en_t:
                queries.append((f"site:patents.google.com {en_t}", "wt-wt", "en", "claim_patent"))
                queries.append((f"{en_t} patent prior art", "us-en", "en", "claim_patent"))
                queries.append((f"{en_t} review", "us-en", "en", "claim_confirm"))

    # de-dup queries, keep order
    uniq = []
    qseen = set()
    for item in queries:
        if item[0] in qseen:
            continue
        qseen.add(item[0])
        uniq.append(item)

    for query, region, query_lang, purpose in uniq[:18]:
        try:
            results = _ddg_search(query, region, 4)
        except Exception as exc:
            errors.append(f"{purpose}/{query_lang}: {exc}")
            continue
        for item in results:
            url = item.get("url") or ""
            key = url or f"{item.get('title')}|{item.get('snippet')}"
            if not key or key in seen:
                continue
            seen.add(key)
            platform = _platform_from_url(url)
            hits.append(
                {
                    "market": "tech_landscape",
                    "query_lang": query_lang,
                    "query": query,
                    "platform": platform,
                    "content_type": purpose if purpose.startswith("claim") else _content_type(
                        platform, item.get("title") or "", item.get("snippet") or ""
                    ),
                    "purpose": purpose,
                    "title": item.get("title") or "",
                    "snippet": item.get("snippet") or "",
                    "url": url,
                }
            )
    return {"n": len(hits), "hits": hits, "errors": errors}


def format_search_block(payload: Dict[str, Any], lang: str) -> str:
    if not payload.get("n"):
        extra = "; ".join(payload.get("errors") or [])
        if lang == "zh":
            return (
                "【网页检索 VOC】本次检索条数=0。"
                + (f" 失败原因：{extra}" if extra else " 未拿到可核对链接。")
                + " 检索失败的内容不得编造 URL 或条数，一律按 L4 假设。"
            )
        return (
            "[Web VOC] Retrieved 0 items."
            + (f" Errors: {extra}" if extra else " No verifiable URLs.")
            + " Do not invent URLs or counts; treat missing web VOC as L4."
        )

    lines = [f"WEB_VOC_COUNT={payload['n']}", "WEB_VOC_ITEMS_START"]
    for i, hit in enumerate(payload["hits"][:180], start=1):
        lines.append(
            f"{i}. market={hit['market']} lang={hit['query_lang']} "
            f"platform={hit['platform']} type={hit['content_type']} "
            f"title={hit['title']} snippet={hit['snippet'][:220]} url={hit['url']}"
        )
    lines.append("WEB_VOC_ITEMS_END")
    if payload.get("errors"):
        lines.append("WEB_VOC_ERRORS=" + " | ".join(payload["errors"][:12]))
    if lang == "zh":
        lines.append("网页检索条目可作 L2（有 URL）。禁止把未出现的标题/链接写进报告。")
    else:
        lines.append("Web hits may be graded L2 (have URLs). Do not add titles/links that are not listed.")
    return "\n".join(lines)


def format_tech_block(payload: Dict[str, Any], claims: List[Dict[str, str]], lang: str) -> str:
    claim_lines = []
    for i, claim in enumerate(claims or [], start=1):
        claim_lines.append(
            f"{i}. kind={claim.get('kind')} text={claim.get('text')} "
            f"zh={claim.get('terms_zh')} en={claim.get('terms_en')}"
        )
    if lang == "zh":
        head = "【用户产品描述中的主张——必须逐条检索核对，尤其是技术创新/机理】\n"
    else:
        head = "[User claims from the product description — verify each, especially technical innovations]\n"
    claim_text = head + ("\n".join(claim_lines) if claim_lines else ("（无拆出的主张，仍需对产品名做专利/竞品检索）" if lang == "zh" else "(no extracted claims; still search patents/competitors for the product name)"))
    if not payload.get("n"):
        extra = "; ".join(payload.get("errors") or [])
        empty = (
            "【专利/竞品检索】0 条。" + (f" 原因：{extra}" if extra else "")
            if lang == "zh"
            else f"[Patent/competitor search] 0 hits." + (f" Errors: {extra}" if extra else "")
        )
        return claim_text + "\n" + empty + (
            " 不得编造专利号或竞品型号。" if lang == "zh" else " Do not invent patent numbers or competitor SKUs."
        )
    lines = [f"TECH_SEARCH_COUNT={payload['n']}", "TECH_SEARCH_START"]
    for i, hit in enumerate(payload["hits"][:120], start=1):
        lines.append(
            f"{i}. purpose={hit.get('purpose')} lang={hit.get('query_lang')} "
            f"platform={hit.get('platform')} type={hit.get('content_type')} "
            f"title={hit.get('title')} snippet={hit.get('snippet')[:220]} url={hit.get('url')} query={hit.get('query')}"
        )
    lines.append("TECH_SEARCH_END")
    lines.append("只引用以上 URL。专利空白点必须基于未命中或权利要求差异，不能虚构专利号。" if lang == "zh" else "Cite only URLs above. White space must be based on misses or claim gaps; never invent patent numbers.")
    return claim_text + "\n" + "\n".join(lines)


def extract_json_object(text: str) -> Dict[str, Any]:
    raw = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.S)
    blob = fenced.group(1) if fenced else raw
    start, end = blob.find("{"), blob.rfind("}")
    if start < 0 or end <= start:
        return {}
    import json

    try:
        data = json.loads(blob[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def format_channel_guide(markets: List[str], lang: str) -> str:
    lines = []
    if lang == "zh":
        lines.append("【信息获取渠道清单——必须按市场尽量列全，下列为最低覆盖，可再补充同类渠道】")
    else:
        lines.append("[Information-channel checklist — cover at least these per market, then add similar local channels]")
    for market in markets:
        profile = MARKET_PROFILES[normalize_market_key(market)]
        label = profile["label_zh"] if lang == "zh" else profile["label_en"]
        channels = profile.get("info_channels_zh" if lang == "zh" else "info_channels_en") or []
        lines.append(f"- {label} ({market}): " + "；".join(channels) if lang == "zh" else f"- {label} ({market}): " + "; ".join(channels))
    return "\n".join(lines)
