"""Load manually-written news blurbs from the manual/ directory."""

import os
from datetime import datetime, timedelta


def fetch(config: dict, since: datetime | None = None) -> list[dict]:
    """Return blurbs from .md files in the manual/ directory.

    Each entry is a dict with keys: source, filename, content.
    """
    if since is None:
        since = datetime.now() - timedelta(days=7)

    manual_dir = config.get("manual_dir", "manual")
    entries = []

    if not os.path.isdir(manual_dir):
        return entries

    for fname in sorted(os.listdir(manual_dir)):
        if not fname.endswith(".md"):
            continue
        path = os.path.join(manual_dir, fname)
        mtime = datetime.fromtimestamp(os.path.getmtime(path))
        if mtime < since:
            continue
        with open(path) as f:
            content = f.read().strip()
        if content:
            entries.append({
                "source": "manual",
                "filename": fname,
                "content": content,
            })

    total_lines = sum(e["content"].count("\n") + 1 for e in entries)
    print(f"  manual: {len(entries)} files, {total_lines} lines")
    return entries
