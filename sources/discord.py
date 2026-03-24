"""Fetch recent messages from Discord channels."""

import requests
from datetime import datetime, timedelta

API_BASE = "https://discord.com/api/v10"


def _headers(token):
    return {"Authorization": f"Bot {token}"}


def _snowflake_from_datetime(dt):
    """Convert a datetime to a Discord snowflake ID for use in 'after' queries."""
    # Discord epoch: 2015-01-01T00:00:00Z
    discord_epoch_ms = 1420070400000
    unix_ms = int(dt.timestamp() * 1000)
    return (unix_ms - discord_epoch_ms) << 22


def _fetch_messages(channel_id, since, headers):
    """Fetch messages from a channel posted after `since`."""
    after = _snowflake_from_datetime(since)
    messages = []
    while True:
        resp = requests.get(
            f"{API_BASE}/channels/{channel_id}/messages",
            params={"after": after, "limit": 100},
            headers=headers,
        )
        if resp.status_code != 200:
            print(f"  Warning: channel {channel_id} returned {resp.status_code}")
            break
        batch = resp.json()
        if isinstance(batch, dict):
            break
        if not batch:
            break
        messages.extend(batch)
        after = batch[0]["id"]
        if len(batch) < 100:
            break

    messages.reverse()
    return messages


def _format_message(msg):
    """Format a single Discord message as a readable line."""
    author = msg["author"].get("global_name") or msg["author"]["username"]
    timestamp = msg["timestamp"][:10]
    content = msg["content"]
    if not content:
        # Skip empty messages (e.g. image-only, embeds)
        return None
    return f"**{author}** ({timestamp}): {content}"


def fetch(config: dict, since: datetime | None = None) -> list[dict]:
    """Return recent Discord messages from configured channels."""
    if since is None:
        since = datetime.now() - timedelta(days=7)

    token = config.get("discord_bot_token") or config.get("discord_token")
    if not token:
        return []

    channels = config.get("discord_channels", [])
    if not channels:
        return []

    hdrs = _headers(token)
    entries = []

    for ch in channels:
        channel_id = ch["channel_id"]
        name = ch.get("name", channel_id)

        messages = _fetch_messages(channel_id, since, hdrs)
        formatted = [_format_message(m) for m in messages]
        formatted = [f for f in formatted if f]  # remove None

        print(f"  #{name}: {len(formatted)} messages")

        if formatted:
            entries.append({
                "source": "discord",
                "channel": name,
                "content": "\n".join(formatted),
            })

    return entries
