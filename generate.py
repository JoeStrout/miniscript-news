#!/usr/bin/env python3
"""MiniScript Weekly News generator.

Gathers data from all configured sources, sends it to an LLM,
and writes the resulting newsletter to output/.
"""

import argparse
import os
import sys
import yaml
from datetime import datetime, timedelta

from llm import call_llm, print_usage_report
from sources import devlogs, itchio, discord, devto, manual, jams


def load_config(path="config.yaml", secrets_path="secret.yaml"):
    with open(path) as f:
        config = yaml.safe_load(f)
    try:
        with open(secrets_path) as f:
            secrets = yaml.safe_load(f) or {}
        config.update(secrets)
    except FileNotFoundError:
        print(f"Warning: {secrets_path} not found; continuing without secrets.")
    return config


def gather_sources(config, since):
    """Collect entries from all sources. Aborts on fatal errors (e.g. repo not found)."""
    all_entries = []
    for mod in [itchio, manual, discord, devlogs, jams, devto]:
        try:
            entries = mod.fetch(config, since=since)
            all_entries.extend(entries)
        except RuntimeError as e:
            print(f"Error: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Warning: {mod.__name__} failed: {e}")
    return all_entries


def format_sources_for_prompt(entries):
    """Format gathered entries into text for the LLM prompt."""
    if not entries:
        return "(No source material gathered this week.)"

    parts = []
    for entry in entries:
        header = f"[{entry['source']}]"
        if "repo" in entry:
            header += f" {entry['repo']}"
        elif "filename" in entry:
            header += f" {entry['filename']}"
        elif "channel" in entry:
            header += f" #{entry['channel']}"
        parts.append(f"### {header}\n\n{entry['content']}")

    return "\n\n---\n\n".join(parts)


def build_prompt(entries, date_str):
    """Load the prompt template and fill it in."""
    with open("prompt.md") as f:
        template = f.read()

    sources_text = format_sources_for_prompt(entries)
    return template.replace("{sources}", sources_text).replace("{date}", date_str)


def main():
    parser = argparse.ArgumentParser(description="Generate MiniScript Weekly News")
    parser.add_argument("--days", type=int, default=7, help="Number of days to look back (default: 7)")
    args = parser.parse_args()

    config = load_config()
    since = datetime.now() - timedelta(days=args.days)
    date_str = datetime.now().strftime("%B %d, %Y")

    print(f"Gathering sources since {since.strftime('%Y-%m-%d')}...")
    entries = gather_sources(config, since)

    # Separate raw-append entries (e.g. jams) from LLM-input entries
    llm_entries = [e for e in entries if not e.get("append_raw")]
    raw_entries = [e for e in entries if e.get("append_raw")]
    print(f"  Found {len(llm_entries)} entries for LLM, {len(raw_entries)} raw sections.")

    if not llm_entries and not raw_entries:
        print("No entries found. Add some content to manual/ or configure sources.")
        print("Generating anyway with empty source material...")

    prompt = build_prompt(llm_entries, date_str)

    print(f"\nPrompt length: {len(prompt)} chars")
    answer = input("Call LLM to generate newsletter? [y/N] ").strip().lower()
    if answer != "y":
        if input("View the prompt? [y/N] ").strip().lower() == "y":
            print("\n" + "=" * 60)
            print(prompt)
            print("=" * 60)
        print_usage_report(config)
        return

    print("Calling LLM...")
    newsletter = call_llm(prompt, config)

    # Append raw sections (e.g. game jams)
    for entry in raw_entries:
        newsletter += "\n\n" + entry["content"]

    os.makedirs("output", exist_ok=True)
    date_prefix = datetime.now().strftime('%Y-%m-%d')
    prompt_file = f"output/{date_prefix}-prompt.md"
    news_file = f"output/{date_prefix}-news.md"

    with open(prompt_file, "w") as f:
        f.write(prompt)
    with open(news_file, "w") as f:
        f.write(newsletter)

    print(f"Prompt written to {prompt_file}")
    print(f"Newsletter written to {news_file}")
    print_usage_report(config)


if __name__ == "__main__":
    main()
