from __future__ import annotations

import re
from pathlib import Path

LEGACY = re.compile(
    r'<script>\(function\(\)\{var r=document\.documentElement,l=document\.getElementById\("langToggle"\),t=document\.getElementById\("themeToggle"\);.*?</script>',
    re.S,
)


def strip(path: Path = Path('docs/index.html')) -> None:
    html = path.read_text(encoding='utf-8')
    cleaned, count = LEGACY.subn('', html)
    if count:
        path.write_text(cleaned, encoding='utf-8')
    print(f'Removed {count} legacy dashboard controller(s).')


if __name__ == '__main__':
    strip()
