# miniscript-news

An LLM-powered agent that gathers content from multiple sources and generates a weekly MiniScript community newsletter.  It implements a multi-step workflow, using various tools for sourcing raw data, applying LLM calls for several subtasks (including evaluating jams for suitability, and summarizing blog posts), and then finally calling another LLM to write the final content.

## Sources

- **GitHub** (`sources/devlogs.py`) — fetches DEV_LOG.md entries and recent commits from configured repos
- **itch.io projects** (`sources/itchio.py`) — finds recently updated MiniScript/Mini Micro tagged games
- **itch.io game jams** (`sources/jams.py`) — scrapes upcoming jams, uses an LLM to score them for Mini Micro fit, and picks top recommendations
- **Discord** (`sources/discord.py`) — pulls recent messages from configured channels on the MiniScript Discord server
- **dev.to** (`sources/devto.py`) — finds MiniScript-related blog posts, fetches full text, and generates LLM summaries
- **Manual blurbs** (`sources/manual.py`) — reads `.md` files from the `manual/` directory for hand-written news items

## Setup

1. Create a micromamba environment: `micromamba create -n miniscript-news python=3.12 pip`
2. Install dependencies: `micromamba run -n miniscript-news pip install openai anthropic requests pyyaml`
3. Create `secret.yaml` with your API keys
4. Edit `config.yaml` to configure repos, channels, authors, and LLM settings

## Usage

```
./run              # default: look back 7 days
./run --days 14    # custom lookback window
```

The script gathers sources, shows a summary, and asks for confirmation before calling the LLM to generate the newsletter. Output goes to `output/YYYY-MM-DD-news.md` and `output/YYYY-MM-DD-prompt.md`.  The token usage and estimated cost is also printed (typical cost seems to be about 4 cents per run so far).

## Configuration

- `config.yaml` — repos, channels, authors, LLM model and pricing
- `secret.yaml` — API keys (gitignored)
- `prompt.md` — the newsletter generation prompt template
- `manual/` — drop `.md` files here for manual news blurbs
