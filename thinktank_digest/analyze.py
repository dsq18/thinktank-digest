from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from .models import PRIORITY_TOPICS, TOPICS, Analysis, DigestArticle, RawArticle

LOGGER = logging.getLogger(__name__)


def heuristic_relevance(article: RawArticle) -> bool:
    text = f"{article.title}\n{article.text[:4000]}".casefold()
    priority_hits = [
        "china",
        "chinese",
        "taiwan",
        "indo-pacific",
        "indopacific",
        "great power",
        "national security",
        "defense",
        "defence",
        "military",
        "technology",
        "artificial intelligence",
        "semiconductor",
        "geoeconomic",
        "trade",
        "supply chain",
        "russia",
        "middle east",
    ]
    return any(hit in text for hit in priority_hits) or re.search(r"\bai\b", text) is not None


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError("model did not return JSON")
    return json.loads(match.group(0))


def _normalise_analysis(payload: dict) -> Analysis:
    tags = [str(tag) for tag in payload.get("主题标签", []) if str(tag) in TOPICS]
    importance = int(payload.get("重要性评分", 1))
    importance = min(max(importance, 1), 5)
    points = [str(point).strip() for point in payload.get("核心观点", []) if str(point).strip()]
    return Analysis(
        relevant=bool(payload.get("relevant", True)),
        conclusion=str(payload.get("一句话结论", "")).strip(),
        key_points=points[:5],
        china_impact=str(payload.get("对中国的影响", "")).strip(),
        indo_pacific_impact=str(payload.get("对印太的影响", "")).strip(),
        international_security_impact=str(payload.get("对国际安全的影响", "")).strip(),
        global_economy_impact=str(payload.get("对全球经济的影响", "")).strip(),
        importance=importance,
        topic_tags=tags,
    )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=20))
def analyze_article(article: RawArticle, model: str | None = None) -> Analysis:
    if not heuristic_relevance(article):
        return Analysis.irrelevant()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        LOGGER.warning("OPENAI_API_KEY is missing; using deterministic fallback analysis")
        return fallback_analysis(article)

    client = OpenAI(api_key=api_key)
    selected_model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    content = article.text[:12000] if article.text else article.title
    prompt = f"""
你是用户的个人地缘政治研究助理，不是新闻聚合器。请只保留有战略意义、政策相关性或安全/经济影响的国际智库研究。

请用简体中文分析下列文章，并只输出 JSON，不要 Markdown。

可选主题标签必须来自这个列表：{", ".join(TOPICS)}
优先关注：{", ".join(sorted(PRIORITY_TOPICS))}

JSON 字段：
{{
  "relevant": true/false,
  "一句话结论": "...",
  "核心观点": ["...", "...", "..."],
  "对中国的影响": "...",
  "对印太的影响": "...",
  "对国际安全的影响": "...",
  "对全球经济的影响": "...",
  "重要性评分": 1-5,
  "主题标签": ["China"]
}}

来源：{article.source}
标题：{article.title}
发布日期：{article.publish_date.isoformat() if article.publish_date else "未知"}
URL：{article.url}
正文：
{content}
"""
    response = client.chat.completions.create(
        model=selected_model,
        temperature=0.2,
        messages=[
            {"role": "system", "content": "你是一名严谨的中文地缘政治研究助理。"},
            {"role": "user", "content": prompt},
        ],
    )
    payload = _extract_json(response.choices[0].message.content or "{}")
    analysis = _normalise_analysis(payload)
    if not analysis.relevant:
        return Analysis.irrelevant(analysis.conclusion or "模型判定相关性不足")
    return analysis


def fallback_analysis(article: RawArticle) -> Analysis:
    text = f"{article.title}\n{article.text}".casefold()
    tags: list[str] = []
    mapping = {
        "China": ["china", "chinese", "beijing", "prc"],
        "Taiwan": ["taiwan", "taipei"],
        "Indo-Pacific": ["indo-pacific", "indopacific", "south china sea", "asean"],
        "US-China Relations": ["u.s.-china", "us-china", "united states and china"],
        "Technology": ["technology", "tech", "digital"],
        "AI": ["artificial intelligence", "machine learning"],
        "Semiconductors": ["semiconductor", "chip"],
        "Defense": ["defense", "defence", "security"],
        "Military": ["military", "armed forces"],
        "Economics": ["economy", "economic", "finance"],
        "Trade": ["trade", "tariff", "supply chain"],
        "Energy": ["energy", "oil", "gas"],
        "Europe": ["europe", "eu", "nato"],
        "Russia": ["russia", "moscow"],
        "Middle East": ["middle east", "iran", "israel", "gulf"],
    }
    for tag, needles in mapping.items():
        if any(needle in text for needle in needles) or (tag == "AI" and re.search(r"\bai\b", text)):
            tags.append(tag)
    strategic = any(tag in tags for tag in ["China", "Taiwan", "Indo-Pacific", "Defense", "AI"])
    importance = min(5, max(2, article.source_priority + (1 if strategic else 0) - 1))
    return Analysis(
        relevant=bool(tags),
        conclusion=f"该研究涉及{article.source}对{article.title}的政策分析，需结合原文研判其战略含义。",
        key_points=[
            "系统未检测到 OpenAI API key，因此使用规则方法生成保守摘要。",
            "建议部署时配置 OPENAI_API_KEY，以获得完整中文分析和跨源综合判断。",
            "该条目因命中优先主题而被纳入每日简报候选。",
        ],
        china_impact="可能影响中国相关政策判断，需阅读原文确认具体方向。",
        indo_pacific_impact="若涉及区域安全、供应链或大国竞争，可能影响印太政策议程。",
        international_security_impact="可能涉及安全态势、联盟政策或风险评估。",
        global_economy_impact="可能涉及贸易、产业链、能源或宏观经济外溢效应。",
        importance=importance,
        topic_tags=tags[:6],
    )


def rank_articles(articles: list[DigestArticle]) -> list[DigestArticle]:
    now = datetime.now(timezone.utc)

    def score(item: DigestArticle) -> tuple[float, int, int, float]:
        publish_date = item.publish_date or item.discovered_at
        age_days = max((now - publish_date.astimezone(timezone.utc)).days, 0)
        recency_score = max(0.0, 7.0 - age_days)
        tags = {tag.casefold() for tag in item.analysis.topic_tags}
        strategic_bonus = 1.0 if tags & PRIORITY_TOPICS else 0.0
        policy_relevance = item.analysis.importance + strategic_bonus
        return (
            policy_relevance,
            item.analysis.importance,
            item.source_priority,
            recency_score,
        )

    return sorted(articles, key=score, reverse=True)


def synthesize_observations(articles: list[DigestArticle], model: str | None = None) -> str:
    if not articles:
        return "今日未发现足够重要的新研究。"
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        top = "；".join(item.analysis.conclusion for item in articles[:3] if item.analysis.conclusion)
        return f"今日重点集中在：{top}" if top else "今日新增研究数量有限，建议关注排名靠前条目。"

    client = OpenAI(api_key=api_key)
    selected_model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    brief = "\n".join(
        f"- {item.source}: {item.title} | {item.analysis.conclusion} | 标签: {', '.join(item.analysis.topic_tags)}"
        for item in articles[:12]
    )
    response = client.chat.completions.create(
        model=selected_model,
        temperature=0.2,
        messages=[
            {"role": "system", "content": "你是一名简洁、严谨的中文地缘政治研究助理。"},
            {
                "role": "user",
                "content": "请基于以下智库研究，用120-180字写出今日重点观察，强调跨源共同信号和战略含义。\n"
                + brief,
            },
        ],
    )
    return (response.choices[0].message.content or "").strip()
