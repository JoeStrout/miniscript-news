"""Fetch MiniScript-related articles from dev.to."""

import requests
from datetime import datetime, timedelta

from llm import call_llm

API_BASE = "https://dev.to/api"
RELEVANT_TAGS = {"miniscript", "minimicro"}
RELEVANT_KEYWORDS = ["miniscript", "mini micro"]

SUMMARY_PROMPT = """\
The following is a blog post from dev.to. We are looking for articles about \
MiniScript, a clean scripting language designed for embedding in games and apps, \
or Mini Micro, a retro-style virtual computer that runs MiniScript.

Note: there is a DIFFERENT language also called "MiniScript" related to Bitcoin/blockchain. \
Articles about that are NOT relevant.

If this article is NOT about our MiniScript or Mini Micro, respond with exactly: NOT APPLICABLE

Otherwise, write a one-paragraph summary of the article suitable for inclusion in a \
community newsletter. Include what the article covers and why it would be interesting \
to MiniScript developers.

Article title: {title}
Article author: {author}
Article URL: {url}

Article text:
{body}
"""


def _is_relevant(article):
    """Check if an article is MiniScript-related by tags or content."""
    tags = set((article.get("tag_list") or []))
    if tags & RELEVANT_TAGS:
        return True
    # Check title and description
    text = (article.get("title", "") + " " + article.get("description", "")).lower()
    return any(kw in text for kw in RELEVANT_KEYWORDS)


def _fetch_by_tag(tag, since, per_page=30):
    """Fetch recent articles with a given tag."""
    resp = requests.get(f"{API_BASE}/articles", params={
        "tag": tag,
        "per_page": per_page,
        "top": 7,  # articles from the last 7 days
    })
    if resp.status_code != 200:
        return []
    return [a for a in resp.json() if _parse_date(a) >= since]


def _fetch_by_username(username, since, per_page=30):
    """Fetch recent articles by a specific author."""
    resp = requests.get(f"{API_BASE}/articles", params={
        "username": username,
        "per_page": per_page,
    })
    if resp.status_code != 200:
        print(f"  Warning: dev.to user {username} returned {resp.status_code}")
        return []
    return [a for a in resp.json() if _parse_date(a) >= since]


def _parse_date(article):
    """Parse the published_at timestamp from an article."""
    date_str = article.get("published_at", "")
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, AttributeError):
        return datetime.min


def _fetch_full_article(article_id):
    """Fetch the full article body markdown from dev.to."""
    resp = requests.get(f"{API_BASE}/articles/{article_id}")
    if resp.status_code != 200:
        return ""
    return resp.json().get("body_markdown", "")


def _summarize_article(article, config):
    """Fetch full text and ask the LLM to summarize. Returns summary or None if not applicable."""
    title = article.get("title", "Untitled")
    url = article.get("url", "")
    author = article.get("user", {}).get("name", article.get("user", {}).get("username", "Unknown"))

    body = _fetch_full_article(article["id"])
    if not body:
        return None

    # Cap body length to control costs
    body = body[:5000]

    prompt = SUMMARY_PROMPT.format(title=title, author=author, url=url, body=body)
    response = call_llm(prompt, config)

    if "NOT APPLICABLE" in response.upper():
        return None
    return response.strip()


def _format_article(article, summary):
    """Format an article with its LLM summary for the newsletter source material."""
    title = article.get("title", "Untitled")
    url = article.get("url", "")
    author = article.get("user", {}).get("name", article.get("user", {}).get("username", "Unknown"))
    date = article.get("readable_publish_date", "")
    return f"**[{title}]({url})** by {author} ({date})\n{summary}"


def fetch(config: dict, since: datetime | None = None) -> list[dict]:
    """Return recent MiniScript-related dev.to articles with LLM summaries."""
    if since is None:
        since = datetime.now() - timedelta(days=7)

    seen_ids = set()
    articles = []

    # Fetch by relevant tags
    for tag in RELEVANT_TAGS:
        for article in _fetch_by_tag(tag, since):
            aid = article["id"]
            if aid not in seen_ids:
                seen_ids.add(aid)
                articles.append(article)

    # Fetch by configured authors, filtering for relevance
    for username in config.get("devto_authors", []):
        for article in _fetch_by_username(username, since):
            aid = article["id"]
            if aid not in seen_ids and _is_relevant(article):
                seen_ids.add(aid)
                articles.append(article)

    print(f"  dev.to: {len(articles)} candidate articles")

    if not articles:
        return []

    # Summarize each article via LLM, filtering out non-applicable ones
    entries = []
    for article in articles:
        title = article.get("title", "Untitled")
        print(f"    Summarizing: {title}...")
        summary = _summarize_article(article, config)
        if summary:
            entries.append(_format_article(article, summary))
        else:
            print(f"    Skipped (not applicable)")

    print(f"  dev.to: {len(entries)} articles after filtering")

    if not entries:
        return []

    return [{
        "source": "devto",
        "content": "\n\n".join(entries),
    }]
