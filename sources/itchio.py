"""Fetch MiniScript-related projects from itch.io."""

import requests
from datetime import datetime, timedelta


def fetch(config: dict, since: datetime | None = None) -> list[dict]:
    """Return recently published/updated itch.io projects.

    Each entry is a dict with keys: source, title, url, author, description.
    """
    if since is None:
        since = datetime.now() - timedelta(days=7)

    entries = []
    for dev in config.get("itchio_devs", []):
        # itch.io doesn't have a great public API; we may need to scrape
        # or use their RSS feeds.  Placeholder for now.
        # Example feed: https://{dev}.itch.io/feed.xml
        pass

    # TODO: implement itch.io scraping or API calls
    return entries
