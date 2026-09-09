from __future__ import annotations

import re
from pathlib import Path

ZH_NOTE = "自动发现的结构性变化线索；事件类型和机会结论仍需 Tier-1 一手证据链确认。"
EN_NOTE = "Automatically discovered structural-change lead; event type and opportunity conclusions still require Tier-1 first-party evidence."

WHAT_RE = re.compile(
    r'(<div class="what"><b>.*?</b>)<span>.*?</span>(</div>)',
    flags=re.S,
)


def patch(path: Path = Path("docs/index.html")) -> int:
    html = path.read_text(encoding="utf-8")
    replacement = (
        r'\1<span><span class="lang-zh">'
        + ZH_NOTE
        + r'</span><span class="lang-en">'
        + EN_NOTE
        + r'</span></span>\2'
    )
    html, count = WHAT_RE.subn(replacement, html)
    path.write_text(html, encoding="utf-8")
    return count


if __name__ == "__main__":
    count = patch()
    print(f"Dashboard content guard: patched {count} Global Feed description(s).")
