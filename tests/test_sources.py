from pathlib import Path

import pytest

from thinktank_digest.sources import (
    SourceRegistryError,
    apply_natural_command,
    load_sources,
    set_priority,
)


def test_source_commands_update_yaml(tmp_path: Path) -> None:
    path = tmp_path / "sources.yaml"

    result = apply_natural_command(
        path,
        "Add source Example Institute",
        website="https://example.org",
        rss="https://example.org/feed",
        priority=4,
        topics=["China", "Defense"],
        tags=["test"],
    )

    assert result == "Added source Example Institute"
    source = load_sources(path)[0]
    assert source.name == "Example Institute"
    assert source.enabled is True
    assert source.priority == 4
    assert source.rss == "https://example.org/feed"

    apply_natural_command(path, "Disable source Example Institute")
    assert load_sources(path)[0].enabled is False

    apply_natural_command(path, "Enable source Example Institute")
    assert load_sources(path)[0].enabled is True

    apply_natural_command(path, "Set priority Example Institute 2")
    assert load_sources(path)[0].priority == 2

    apply_natural_command(path, "Remove source Example Institute")
    assert load_sources(path) == []


def test_invalid_priority_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "sources.yaml"
    apply_natural_command(path, "Add source Example", website="https://example.org")

    with pytest.raises(SourceRegistryError):
        set_priority(path, "Example", 6)
