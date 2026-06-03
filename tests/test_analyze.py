from datetime import datetime, timezone

from thinktank_digest.analyze import analyze_article, fallback_analysis, heuristic_relevance
from thinktank_digest.models import RawArticle


def test_heuristic_relevance_prioritizes_security_topics() -> None:
    article = RawArticle(
        title="China and Taiwan security in the Indo-Pacific",
        url="https://example.org/a",
        publish_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
        source="Example",
        source_priority=5,
        text="This report discusses defense, AI, semiconductors, and national security.",
    )

    assert heuristic_relevance(article) is True


def test_analyze_uses_fallback_without_openai_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    article = RawArticle(
        title="China AI semiconductor defense report",
        url="https://example.org/a",
        publish_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
        source="Example",
        source_priority=5,
        text="China AI semiconductor defense trade security analysis.",
    )

    analysis = analyze_article(article)

    assert analysis.relevant is True
    assert analysis.importance >= 4
    assert "China" in analysis.topic_tags


def test_fallback_analysis_marks_irrelevant_when_no_topics() -> None:
    article = RawArticle(
        title="Museum exhibition opening hours",
        url="https://example.org/a",
        publish_date=None,
        source="Example",
        source_priority=1,
        text="Culture and local events.",
    )

    assert fallback_analysis(article).relevant is False


def test_openai_json_response_is_normalized(monkeypatch) -> None:
    class FakeMessage:
        content = """{
          "relevant": true,
          "一句话结论": "中国与印太安全议题值得优先关注。",
          "核心观点": ["观点一", "观点二", "观点三"],
          "对中国的影响": "影响中国安全与科技政策。",
          "对印太的影响": "影响印太威慑和联盟协调。",
          "对国际安全的影响": "提高危机管理重要性。",
          "对全球经济的影响": "影响供应链和贸易风险。",
          "重要性评分": 5,
          "主题标签": ["China", "Indo-Pacific", "Defense"]
        }"""

    class FakeChoice:
        message = FakeMessage()

    class FakeResponse:
        choices = [FakeChoice()]

    class FakeCompletions:
        def create(self, **_kwargs):
            return FakeResponse()

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, api_key):
            assert api_key == "test-key"
            self.chat = FakeChat()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("thinktank_digest.analyze.OpenAI", FakeOpenAI)
    article = RawArticle(
        title="China Indo-Pacific defense strategy",
        url="https://example.org/a",
        publish_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
        source="Example",
        source_priority=5,
        text="China and Indo-Pacific defense strategy with security implications.",
    )

    analysis = analyze_article(article)

    assert analysis.conclusion == "中国与印太安全议题值得优先关注。"
    assert analysis.importance == 5
    assert analysis.topic_tags == ["China", "Indo-Pacific", "Defense"]
