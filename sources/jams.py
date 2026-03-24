"""Scrape upcoming itch.io game jams and evaluate their fit for Mini Micro."""

import csv
import os
import re
import requests
from datetime import datetime
from html.parser import HTMLParser

LISTING_URL = "https://itch.io/jams/upcoming/sort-date"
CACHE_FILE = "jams_cache.csv"
TOP_N = 6
SCORE_THRESHOLD = 5

EVAL_PROMPT = """\
Mini Micro is a retro-style virtual computer powered by the MiniScript language. \
It has a 960x640 pixel display, built-in sprite, tile, and text display layers, \
mouse/keyboard/gamepad input, and sound support. Games are typically 2D: pixel art, \
tile-based, or text-based. It has a scaleable pixel display and so can emulate \
low-res or high-res graphics. It has no 3D support, no networking, and no VR/AR.

Given this game jam description, rate how good a fit it would be for someone \
making a game in Mini Micro. Return ONLY a JSON object like:
{{"score": 7, "blurb": "One sentence blurb about the jam."}}

Score 1-10 where:
- 1-3: Poor fit (requires 3D, VR, specific engine, multiplayer networking, etc.)
- 4-5: Possible but not ideal
- 6-8: Good fit
- 9-10: Great fit (retro theme, pixel art, simple mechanics, etc.)

The blurb should describe what is noteworthy and interesting about the jam; the point \
is to entice readers to consider entering it.  There is no need to mention Mini Micro \
in the blurb. If the score is 5 or below, set blurb to "".

Jam title: {title}
Jam URL: {url}
Jam description:
{description}
"""


# --- HTML Parsing ---

class JamListParser(HTMLParser):
    """Parse jam entries from the itch.io upcoming jams listing page."""

    def __init__(self):
        super().__init__()
        self.jams = []
        self._current = None
        self._in_h3 = False
        self._in_title_link = False
        self._text_buf = ""
        self._div_depth = 0  # track div nesting within a jam entry

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        cls = attrs_dict.get("class", "")

        # Detect jam entry wrapper: <div class="jam lazy_images">
        if tag == "div" and "jam" in cls.split() and self._current is None:
            self._current = {}
            self._div_depth = 1
            return

        if self._current is not None:
            if tag == "div":
                self._div_depth += 1

            if tag == "h3":
                self._in_h3 = True

            if tag == "a" and self._in_h3 and "href" in attrs_dict:
                href = attrs_dict["href"]
                if href.startswith("/jam/"):
                    self._current["url"] = "https://itch.io" + href
                    self._current["slug"] = href.split("/jam/")[1].split("/")[0]
                    self._in_title_link = True
                    self._text_buf = ""

            # Dates are in <span class="date_countdown">ISO_DATE</span>
            if tag == "span" and "date_countdown" in cls:
                # title attr has friendly date, but we'll also grab the text content
                if "title" in attrs_dict:
                    self._current.setdefault("date_str", attrs_dict["title"])

    def handle_data(self, data):
        if self._in_title_link:
            self._text_buf += data

    def handle_endtag(self, tag):
        if self._in_title_link and tag == "a":
            self._in_title_link = False
            self._in_h3 = False
            if self._current is not None and self._text_buf.strip():
                self._current.setdefault("title", self._text_buf.strip())

        if tag == "h3":
            self._in_h3 = False

        if tag == "div" and self._current is not None:
            self._div_depth -= 1
            if self._div_depth <= 0:
                if "url" in self._current:
                    self.jams.append(self._current)
                self._current = None


class JamDescriptionParser(HTMLParser):
    """Extract the description text from an individual jam page."""

    def __init__(self):
        super().__init__()
        self.text_parts = []
        self._in_formatted = False
        self._depth = 0

    def handle_starttag(self, tag, attrs):
        cls = dict(attrs).get("class", "")
        if "formatted" in cls and not self._in_formatted:
            self._in_formatted = True
            self._depth = 1
            return
        if self._in_formatted:
            self._depth += 1
            if tag in ("p", "br", "li", "h1", "h2", "h3", "h4"):
                self.text_parts.append("\n")

    def handle_endtag(self, tag):
        if self._in_formatted:
            self._depth -= 1
            if self._depth <= 0:
                self._in_formatted = False

    def handle_data(self, data):
        if self._in_formatted:
            self.text_parts.append(data)

    def get_text(self):
        return "".join(self.text_parts).strip()


# --- Scraping ---

def _scrape_listing(pages=2):
    """Scrape upcoming jams from itch.io listing pages."""
    all_jams = []
    for page in range(1, pages + 1):
        url = LISTING_URL if page == 1 else f"{LISTING_URL}?page={page}"
        resp = requests.get(url)
        if resp.status_code != 200:
            print(f"  Warning: jams listing page {page} returned {resp.status_code}")
            continue
        parser = JamListParser()
        parser.feed(resp.text)
        all_jams.extend(parser.jams)
        print(f"  Scraped page {page}: {len(parser.jams)} jams")
    return all_jams


def _fetch_jam_description(url):
    """Fetch and extract the description text from a jam page."""
    resp = requests.get(url)
    if resp.status_code != 200:
        return ""
    parser = JamDescriptionParser()
    parser.feed(resp.text)
    return parser.get_text()[:3000]  # cap length to control LLM costs


# --- Cache ---

def _load_cache():
    """Load previously evaluated jams from CSV. Returns dict of url -> (score, blurb)."""
    cache = {}
    if not os.path.exists(CACHE_FILE):
        return cache
    with open(CACHE_FILE, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cache[row["url"]] = (int(row["score"]), row["blurb"])
    return cache


def _save_cache(cache):
    """Write the full cache to CSV."""
    with open(CACHE_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["url", "score", "blurb"])
        writer.writeheader()
        for url, (score, blurb) in sorted(cache.items()):
            writer.writerow({"url": url, "score": score, "blurb": blurb})


# --- Evaluation ---

def _evaluate_jam(title, url, description, config):
    """Ask the LLM to score a jam for Mini Micro fit."""
    import json
    # Import call_llm from the shared module
    from llm import call_llm

    prompt = EVAL_PROMPT.format(title=title, url=url, description=description)
    response = call_llm(prompt, config)

    # Parse the JSON response
    try:
        # Find JSON in the response (LLM may wrap it in markdown)
        match = re.search(r"\{[^}]+\}", response)
        if match:
            data = json.loads(match.group())
            return int(data.get("score", 0)), data.get("blurb", "")
    except (json.JSONDecodeError, ValueError):
        pass
    return 0, ""


# --- Main entry point ---

def fetch(config: dict, since=None) -> list[dict]:
    """Scrape upcoming jams, evaluate new ones, return top picks.

    Unlike other sources, this doesn't use `since` — it always looks at upcoming jams.
    Returns a single entry with the formatted "Upcoming Game Jams" section.
    """
    print("Scraping upcoming game jams...")
    jams = _scrape_listing(pages=2)
    if not jams:
        print("  No jams found.")
        return []

    cache = _load_cache()
    new_count = 0

    for jam in jams:
        url = jam.get("url", "")
        if not url or url in cache:
            continue
        title = jam.get("title", "Unknown Jam")
        print(f"  Evaluating: {title}...")
        description = _fetch_jam_description(url)
        score, blurb = _evaluate_jam(title, url, description, config)
        cache[url] = (score, blurb)
        new_count += 1
        if new_count >= 50:
        	print(f"Bailing out after finding {new_count} new jams")
        	break

    _save_cache(cache)

    # Select top jams: lower the threshold from 10 until we have >= 15, then pick 6 randomly
    all_scored = []
    for jam in jams:
        url = jam.get("url", "")
        if url in cache:
            score, blurb = cache[url]
            if blurb:
                all_scored.append((score, jam, blurb))

    import random
    threshold = 10
    candidates = [c for c in all_scored if c[0] >= threshold]
    while len(candidates) < 15 and threshold > SCORE_THRESHOLD:
        threshold -= 1
        candidates = [c for c in all_scored if c[0] >= threshold]

    top = random.sample(candidates, min(TOP_N, len(candidates)))
    top.sort(key=lambda x: -x[0])  # sort the chosen ones by score for display

    print(f"  {len(jams)} jams scraped, {new_count} newly evaluated, {len(candidates)} candidates (threshold {threshold}), picked {len(top)}")

    if not top:
        return []

    # Format the section directly — this won't go through the newsletter LLM
    lines = ["## Upcoming Game Jams\n",
             "These upcoming jams look like a great fit for Mini Micro:\n"]
    for score, jam, blurb in top:
        title = jam.get("title", "Unknown")
        url = jam.get("url", "")
        date_str = jam.get("date_str", "")
        date_note = f" (starts {date_str})" if date_str else ""
        lines.append(f"- **[{title}]({url})**{date_note} — {blurb}")

    return [{
        "source": "jams",
        "append_raw": True,  # signal to generate.py: append as-is, don't feed to LLM
        "content": "\n".join(lines),
    }]
