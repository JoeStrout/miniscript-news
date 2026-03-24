"""Fetch DEV_LOG.md entries and recent commits from GitHub repos."""

import re
import requests
from datetime import datetime, timedelta

# Date patterns found in DEV_LOG.md headings, e.g. "## Jan 06, 2026"
DATE_PATTERNS = [
    re.compile(r"^##\s+(\w{3}\s+\d{1,2},?\s+\d{4})"),  # ## Mon DD, YYYY
]


def _parse_heading_date(line):
    """Try to parse a date from a ## heading line. Returns datetime or None."""
    for pat in DATE_PATTERNS:
        m = pat.match(line)
        if m:
            text = m.group(1).replace(",", "")  # normalize missing comma
            try:
                return datetime.strptime(text, "%b %d %Y")
            except ValueError:
                pass
    return None


def _filter_devlog(content, since):
    """Extract only devlog entries dated on or after `since`."""
    sections = []
    current_date = None
    current_lines = []

    for line in content.splitlines():
        heading_date = _parse_heading_date(line)
        if heading_date is not None:
            if current_date and current_date >= since and current_lines:
                sections.append("\n".join(current_lines))
            current_date = heading_date
            current_lines = [line]
        else:
            current_lines.append(line)

    # Don't forget the last section
    if current_date and current_date >= since and current_lines:
        sections.append("\n".join(current_lines))

    return "\n\n".join(sections)


def _make_headers(token):
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def _check_repo_exists(repo, headers):
    """Return True if repo exists, False otherwise."""
    resp = requests.get(f"https://api.github.com/repos/{repo}", headers=headers)
    return resp.status_code == 200


def _find_devlog(repo, headers):
    """Search for DEV_LOG.md in the repo. Returns (path, raw_content) or (None, None)."""
    # Use the search API to find it anywhere in the repo
    resp = requests.get(
        "https://api.github.com/search/code",
        params={"q": f"filename:DEV_LOG.md repo:{repo}"},
        headers=headers,
    )
    if resp.status_code != 200 or resp.json().get("total_count", 0) == 0:
        return None, None

    path = resp.json()["items"][0]["path"]

    # Fetch raw content
    raw_resp = requests.get(
        f"https://api.github.com/repos/{repo}/contents/{path}",
        headers={**headers, "Accept": "application/vnd.github.v3.raw"},
    )
    if raw_resp.status_code != 200:
        return path, None

    return path, raw_resp.text


def _fetch_recent_commits(repo, since, headers):
    """Fetch commit messages since the given date."""
    resp = requests.get(
        f"https://api.github.com/repos/{repo}/commits",
        params={"since": since.isoformat(), "per_page": 100},
        headers=headers,
    )
    if resp.status_code != 200:
        return []

    commits = []
    for c in resp.json():
        sha = c["sha"][:7]
        msg = c["commit"]["message"]
        date = c["commit"]["committer"]["date"][:10]
        commits.append(f"- `{sha}` ({date}) {msg}")
    return commits


def fetch(config: dict, since: datetime | None = None) -> list[dict]:
    """Return recent dev-log entries and commits from configured GitHub repos.

    Aborts (raises) if a repo is not found.
    """
    if since is None:
        since = datetime.now() - timedelta(days=7)

    token = config.get("github_token")
    headers = _make_headers(token)
    entries = []

    for repo_entry in config.get("github_repos", []):
        # Support both string and dict config formats
        if isinstance(repo_entry, dict):
            repo = repo_entry["repo"]
        else:
            repo = repo_entry

        # Check repo exists
        if not _check_repo_exists(repo, headers):
            raise RuntimeError(f"GitHub repo not found: {repo}")

        parts = []

        # Look for DEV_LOG.md
        devlog_path, devlog_content = _find_devlog(repo, headers)
        if devlog_content:
            filtered = _filter_devlog(devlog_content, since)
            if filtered:
                parts.append(f"**Dev Log** ({devlog_path}):\n\n{filtered}")

        # Fetch recent commits
        commits = _fetch_recent_commits(repo, since, headers)

        # Print summary
        devlog_status = f"devlog: {len(filtered.splitlines())} lines" if (devlog_content and filtered) else "no recent devlog"
        print(f"  {repo}: {devlog_status}, {len(commits)} commits")

        if commits:
            parts.append(f"**Recent commits:**\n\n" + "\n".join(commits))

        if parts:
            entries.append({
                "source": "github",
                "repo": repo,
                "content": "\n\n".join(parts),
            })

    return entries
