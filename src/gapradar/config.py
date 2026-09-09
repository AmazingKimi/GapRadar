from __future__ import annotations

from pathlib import Path

import yaml

from .detector import OfficialSource


def load_sources(path: Path) -> list[OfficialSource]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sources: list[OfficialSource] = []
    for item in raw.get("sources", []):
        sources.append(
            OfficialSource(
                name=item["name"],
                vendor=item["vendor"],
                url=item["url"],
                allowed_domains=tuple(item["allowed_domains"]),
            )
        )
    return sources
