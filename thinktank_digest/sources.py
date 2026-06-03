from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .models import Source


class SourceRegistryError(ValueError):
    pass


def _normalise_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip()).casefold()


def _validate_priority(priority: int) -> int:
    if priority < 1 or priority > 5:
        raise SourceRegistryError("priority must be between 1 and 5")
    return priority


def load_sources(path: Path) -> list[Source]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    records = data.get("sources", [])
    if not isinstance(records, list):
        raise SourceRegistryError("sources.yaml must contain a top-level 'sources' list")

    sources: list[Source] = []
    for record in records:
        if not isinstance(record, dict):
            raise SourceRegistryError("each source must be a mapping")
        for field in ("name", "website", "enabled", "priority", "topics", "tags"):
            if field not in record:
                raise SourceRegistryError(f"source is missing required field: {field}")
        sources.append(
            Source(
                name=str(record["name"]),
                website=str(record["website"]),
                rss=str(record["rss"]) if record.get("rss") else None,
                enabled=bool(record["enabled"]),
                priority=_validate_priority(int(record["priority"])),
                topics=list(record.get("topics") or []),
                tags=list(record.get("tags") or []),
            )
        )
    return sources


def save_sources(path: Path, sources: list[Source]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "sources": [
            {
                "name": source.name,
                "website": source.website,
                "rss": source.rss or "",
                "enabled": source.enabled,
                "priority": source.priority,
                "topics": source.topics,
                "tags": source.tags,
            }
            for source in sorted(sources, key=lambda src: src.name.casefold())
        ]
    }
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def find_source(sources: list[Source], institution: str) -> int | None:
    needle = _normalise_name(institution)
    for index, source in enumerate(sources):
        if _normalise_name(source.name) == needle:
            return index
    return None


def add_source(
    path: Path,
    institution: str,
    *,
    website: str = "",
    rss: str = "",
    priority: int = 3,
    topics: list[str] | None = None,
    tags: list[str] | None = None,
    enabled: bool = True,
) -> Source:
    sources = load_sources(path)
    if find_source(sources, institution) is not None:
        raise SourceRegistryError(f"source already exists: {institution}")
    source = Source(
        name=institution.strip(),
        website=website.strip(),
        rss=rss.strip() or None,
        enabled=enabled,
        priority=_validate_priority(priority),
        topics=topics or [],
        tags=tags or [],
    )
    sources.append(source)
    save_sources(path, sources)
    return source


def remove_source(path: Path, institution: str) -> Source:
    sources = load_sources(path)
    index = find_source(sources, institution)
    if index is None:
        raise SourceRegistryError(f"source not found: {institution}")
    removed = sources.pop(index)
    save_sources(path, sources)
    return removed


def set_enabled(path: Path, institution: str, enabled: bool) -> Source:
    sources = load_sources(path)
    index = find_source(sources, institution)
    if index is None:
        raise SourceRegistryError(f"source not found: {institution}")
    current = sources[index]
    updated = Source(
        name=current.name,
        website=current.website,
        rss=current.rss,
        enabled=enabled,
        priority=current.priority,
        topics=current.topics,
        tags=current.tags,
    )
    sources[index] = updated
    save_sources(path, sources)
    return updated


def set_priority(path: Path, institution: str, priority: int) -> Source:
    sources = load_sources(path)
    index = find_source(sources, institution)
    if index is None:
        raise SourceRegistryError(f"source not found: {institution}")
    current = sources[index]
    updated = Source(
        name=current.name,
        website=current.website,
        rss=current.rss,
        enabled=current.enabled,
        priority=_validate_priority(priority),
        topics=current.topics,
        tags=current.tags,
    )
    sources[index] = updated
    save_sources(path, sources)
    return updated


def apply_natural_command(
    path: Path,
    command: str,
    *,
    website: str = "",
    rss: str = "",
    priority: int = 3,
    topics: list[str] | None = None,
    tags: list[str] | None = None,
) -> str:
    command = command.strip()
    patterns = [
        (r"^Add source\s+(.+)$", "add"),
        (r"^Remove source\s+(.+)$", "remove"),
        (r"^Enable source\s+(.+)$", "enable"),
        (r"^Disable source\s+(.+)$", "disable"),
        (r"^Set priority\s+(.+?)\s+([1-5])$", "priority"),
    ]
    for pattern, action in patterns:
        match = re.match(pattern, command, flags=re.IGNORECASE)
        if not match:
            continue
        if action == "add":
            source = add_source(
                path,
                match.group(1),
                website=website,
                rss=rss,
                priority=priority,
                topics=topics,
                tags=tags,
            )
            return f"Added source {source.name}"
        if action == "remove":
            source = remove_source(path, match.group(1))
            return f"Removed source {source.name}"
        if action == "enable":
            source = set_enabled(path, match.group(1), True)
            return f"Enabled source {source.name}"
        if action == "disable":
            source = set_enabled(path, match.group(1), False)
            return f"Disabled source {source.name}"
        source = set_priority(path, match.group(1), int(match.group(2)))
        return f"Set source {source.name} priority to {source.priority}"
    raise SourceRegistryError(
        "unsupported command. Use Add/Remove/Enable/Disable source <institution> "
        "or Set priority <institution> <1-5>"
    )
