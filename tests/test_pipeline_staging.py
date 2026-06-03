from pathlib import Path

from thinktank_digest.staging import run_staging_workflow


def test_staging_workflow_generates_report_and_blocks_duplicate(tmp_path: Path) -> None:
    sources_path = tmp_path / "sources.yaml"
    sources_path.write_text(
        """
sources:
  - name: Staging Source
    website: https://staging.thinktank-digest.local
    rss: https://staging.thinktank-digest.local/feed
    enabled: true
    priority: 5
    topics: [China, Taiwan, Indo-Pacific]
    tags: [staging]
""",
        encoding="utf-8",
    )

    result = run_staging_workflow(
        sources_path=sources_path,
        db_path=tmp_path / "staging.sqlite",
        out_dir=tmp_path / "reports",
    )

    assert result["first_run_articles"] == 1
    assert result["second_run_articles"] == 0
    assert result["emails_captured"] == 2
    assert result["duplicate_prevention_ok"] is True
    assert Path(result["html_report"]).exists()
