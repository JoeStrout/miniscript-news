# CLAUDE.md

## Project overview

This is an LLM-powered agent that generates a weekly MiniScript community newsletter. It gathers data from multiple sources, optionally uses the LLM for sub-tasks (jam evaluation, article summarization), then sends all gathered material to the LLM to produce the final newsletter.

## Architecture

- `generate.py` — main entry point; orchestrates source gathering, prompting, and output
- `llm.py` — shared LLM interface with token usage tracking; used by generate.py and individual sources
- `prompt.md` — the template prompt for newsletter generation (editable independently from code)
- `sources/` — one module per data source, each exposing a `fetch(config, since)` function that returns a list of entry dicts
- `config.yaml` — all non-secret configuration; `secret.yaml` — API keys (gitignored)
- `run` — shell wrapper that activates the micromamba environment and runs generate.py

## Adding a new source

1. Create `sources/newsource.py` with a `fetch(config: dict, since: datetime) -> list[dict]` function
2. Each returned dict must have `source` (string) and `content` (string) keys
3. Optionally add `repo`, `filename`, `channel`, etc. for the header formatting in `format_sources_for_prompt`
4. Set `append_raw: True` on entries that should be appended directly to the newsletter (not sent through the LLM)
5. Import and add the module to the `gather_sources` loop in `generate.py`
6. Add any needed config keys to `config.yaml`
7. If the source needs LLM calls (like jams or devto), import `call_llm` from `llm.py` — usage is tracked automatically

## Key conventions

- Sources that hit external APIs should print a summary line (e.g., `  dev.to: 3 relevant articles`)
- Fatal errors (like a missing GitHub repo) should raise `RuntimeError` to abort the run
- Non-fatal issues should print a warning and return an empty list
- The LLM provider/model is configured in `config.yaml` under `llm:`; secrets go in `secret.yaml`
- The micromamba environment is named `miniscript-news`; dependencies: openai, anthropic, requests, pyyaml
