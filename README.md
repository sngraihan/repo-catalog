# Repo Catalog

A small, boring, local catalog of GitHub repos for AI agents.

The problem it solves: an agent that "knows about repos" from training data proposes whatever it half-remembers. Names get mangled, dead projects get recommended, licenses are unknown, and the same job gets solved twice by two different tools. This skill replaces memory with a file you control.

Every row answers four questions an agent actually needs:

- what does this repo do
- when should I reach for it
- **when must I not** (and which repo already covers that job)
- is it installed, not yet, or did we reject it and why

Search is a 200-line Python script with no dependencies and no network calls. Adding a row is one command; star count, license and last-check date are pulled from the GitHub API for you, and anything unverifiable is refused rather than stored.

## Install

Copy this directory into your agent's skills folder:

```bash
git clone https://github.com/sngraihan/repo-catalog.git ~/.hermes/skills/repo-catalog
```

Works anywhere that reads `SKILL.md` with YAML frontmatter (Hermes, Claude Code, Codex, Cursor). The scripts are stdlib Python 3 — nothing to install.

## Use

```bash
cd ~/.hermes/skills/repo-catalog

python3 scripts/search.py "ui ux website prettier"
python3 scripts/search.py "video" --status missing
python3 scripts/find_github.py "video render" --min-stars 5000     # when the catalog has no match
python3 scripts/add.py owner/repo --purpose "..." --use-when "..." # append what you found
python3 scripts/search.py --all --web > catalog.html               # browse it in a browser
python3 scripts/search.py --check                                  # re-verify every row
python3 scripts/search.py --test                                   # self-check
```

Sample output:

```
UI UX Pro Max (nextlevelbuilder/ui-ux-pro-max-skill) - 141,677 stars - INSTALLED - proven
  what    : Gives the agent a designer's eye: layout, colour, type, spacing.
  use when: Building or fixing pages and apps.
  avoid   : Design is already locked in a design document; follow that first.
  checked : 2026-10-28
```

## Why not just ask the model

Because the model cannot tell you:

- that a repo is dead, renamed, or was never real
- that it has no license, so you cannot ship it inside a paid product
- that you already rejected it three months ago for a reason that still holds
- that another tool in your stack does the exact same job

Those four failure modes cost real time. A JSONL file that takes one command to extend costs none.

## Data

`data/catalog.jsonl` ships with 52 rows collected from real work: stars, license, purpose, when to use, when not to use, install status, and the reason behind every rejection. Copy it as a starting point, or empty it out and fill it with what your own work reaches for. The rows that matter most are the ones marked `rejected` — a rejection with a reason is a decision you never have to make twice.

## License

MIT.
