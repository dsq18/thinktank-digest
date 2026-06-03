from __future__ import annotations

from datetime import datetime

from jinja2 import BaseLoader, Environment, select_autoescape

from .models import DigestArticle, DigestReport


CATEGORY_MAP = {
    "China": ["China", "US-China Relations"],
    "Taiwan": ["Taiwan"],
    "Indo-Pacific": ["Indo-Pacific"],
    "Technology": ["Technology", "Semiconductors"],
    "AI": ["AI"],
    "Defense": ["Defense", "Military"],
    "Economy": ["Economics", "Trade", "Energy"],
}

HTML_TEMPLATE = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #17202a; line-height: 1.6; margin: 0; padding: 0; background: #f6f8fa; }
    .container { max-width: 860px; margin: 0 auto; background: #ffffff; padding: 28px; }
    h1 { font-size: 26px; margin: 0 0 18px; }
    h2 { font-size: 20px; margin: 28px 0 12px; border-bottom: 1px solid #d8dee4; padding-bottom: 6px; }
    h3 { font-size: 16px; margin: 18px 0 6px; }
    .meta { color: #5f6b7a; font-size: 13px; }
    .item { border: 1px solid #d8dee4; border-radius: 8px; padding: 16px; margin: 12px 0; background: #fbfcfd; }
    .score { font-weight: 700; color: #8a3ffc; }
    a { color: #0969da; text-decoration: none; }
    ul { padding-left: 20px; }
    .tag { display: inline-block; font-size: 12px; color: #344054; border: 1px solid #d0d5dd; border-radius: 999px; padding: 1px 8px; margin: 2px 4px 2px 0; }
  </style>
</head>
<body>
  <div class="container">
    <h1>今日最重要研究</h1>
    <div class="meta">生成时间：{{ generated_at }}</div>
    {% for item in top_items %}
      <div class="item">
        <h3>{{ loop.index }}. <a href="{{ item.url }}">{{ item.title }}</a></h3>
        <div class="meta">{{ item.source }}{% if item.publish_date %} · {{ item.publish_date }}{% endif %} · 重要性评分 <span class="score">{{ item.analysis.importance }}/5</span></div>
        <p><strong>一句话结论：</strong>{{ item.analysis.conclusion }}</p>
        <ul>
          {% for point in item.analysis.key_points %}
          <li>{{ point }}</li>
          {% endfor %}
        </ul>
        <p><strong>对中国的影响：</strong>{{ item.analysis.china_impact }}</p>
        <p><strong>对印太的影响：</strong>{{ item.analysis.indo_pacific_impact }}</p>
        <p><strong>对国际安全的影响：</strong>{{ item.analysis.international_security_impact }}</p>
        <p><strong>对全球经济的影响：</strong>{{ item.analysis.global_economy_impact }}</p>
        <p>{% for tag in item.analysis.topic_tags %}<span class="tag">{{ tag }}</span>{% endfor %}</p>
      </div>
    {% else %}
      <p>今日未发现足够重要的新研究。</p>
    {% endfor %}

    <h2>今日重点观察</h2>
    <p>{{ synthesis }}</p>

    <h2>按主题分类</h2>
    {% for category, items in categories.items() %}
      <h3>{{ category }}</h3>
      {% if items %}
        <ul>
        {% for item in items %}
          <li><a href="{{ item.url }}">{{ item.title }}</a>（{{ item.source }}，{{ item.analysis.importance }}/5）</li>
        {% endfor %}
        </ul>
      {% else %}
        <p class="meta">无新增重点研究。</p>
      {% endif %}
    {% endfor %}

    <h2>全部新增研究</h2>
    <ul>
    {% for item in remaining_items %}
      <li>{{ item.source }}：<a href="{{ item.url }}">{{ item.title }}</a>{% if item.publish_date %}（{{ item.publish_date }}）{% endif %}</li>
    {% else %}
      <li>无其他新增研究。</li>
    {% endfor %}
    </ul>
  </div>
</body>
</html>
"""


def _format_date(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.strftime("%Y-%m-%d")


def group_by_category(items: list[DigestArticle]) -> dict[str, list[DigestArticle]]:
    grouped: dict[str, list[DigestArticle]] = {}
    for category, tags in CATEGORY_MAP.items():
        wanted = set(tags)
        grouped[category] = [
            item for item in items if wanted.intersection(set(item.analysis.topic_tags))
        ]
    grouped["Other"] = [
        item
        for item in items
        if not any(set(tags).intersection(set(item.analysis.topic_tags)) for tags in CATEGORY_MAP.values())
    ]
    return dict(grouped)


def render_html(report: DigestReport) -> str:
    env = Environment(loader=BaseLoader(), autoescape=select_autoescape(["html", "xml"]))
    template = env.from_string(HTML_TEMPLATE)
    top_urls = {item.url for item in report.top_items}
    return template.render(
        generated_at=report.generated_at.strftime("%Y-%m-%d %H:%M UTC"),
        top_items=[_display_item(item) for item in report.top_items],
        synthesis=report.synthesis,
        categories={
            key: [_display_item(item) for item in value]
            for key, value in group_by_category(report.all_items).items()
        },
        remaining_items=[_display_item(item) for item in report.all_items if item.url not in top_urls],
    )


def render_plain_text(report: DigestReport) -> str:
    lines = ["今日最重要研究", ""]
    for index, item in enumerate(report.top_items, start=1):
        lines.extend(
            [
                f"{index}. {item.title}",
                f"来源：{item.source} | 重要性评分：{item.analysis.importance}/5",
                f"一句话结论：{item.analysis.conclusion}",
                f"URL：{item.url}",
                "",
            ]
        )
    lines.extend(["今日重点观察", report.synthesis, "", "全部新增研究"])
    for item in report.all_items:
        lines.append(f"- {item.source}: {item.title} {item.url}")
    return "\n".join(lines)


def _display_item(item: DigestArticle) -> dict:
    return {
        "title": item.title,
        "url": item.url,
        "publish_date": _format_date(item.publish_date),
        "source": item.source,
        "source_priority": item.source_priority,
        "analysis": item.analysis,
        "discovered_at": item.discovered_at,
    }
