---
name: repo-catalog
description: "Office repo catalog: one list of GitHub repos with purpose, when to use, when NOT to use, license, and status (installed / not yet / rejected with reason). Call it when starting any task to get relevant repo recommendations. Trigger: 'which repo fits X', 'any tool for Y', 'find a github repo', before installing or proposing any third-party tool, or when a task needs a capability the office does not have."
version: 1.1.0
metadata:
  hermes:
    tags: [ai-team, repo, catalog, tooling, discovery]
---

# Repo Catalog — office repo catalog

One place that answers: "for this job, which repo do we use, what for, and how?"

Different from `external-tool-vetting`: this skill **finds candidates**. Vetting (verify entity → read source → claims vs facts) is still mandatory before installing anything.

## Core rules

1. **The catalog is data, not prose.** Every repo lives in `data/catalog.jsonl`. Never write repo lists inside SKILL.md — it gets read every session and burns tokens.
2. **Always search via the script, never read the whole catalog.** `scripts/search.py "<task keywords>"`.
3. **State the check date.** Every row has `checked`. If it is older than 30 days, run `--check` before quoting stars/license to the owner.
4. **If the catalog has no match, search GitHub directly.** Do not stop at the list. Use `external-tool-vetting/references/skill-discovery.md` (search API + awesome lists), then add the result to the catalog.
5. **Owner decisions are binding.** Rows with `rejected` status must not be proposed again without a strong new reason. The reason must be stored in `rejected_reason`.
6. **Check for overlap before proposing.** `dont_use_when` stores repos with the same job. Propose one, not two of the same.

## Workflow (5 steps)

```bash
cd ~/.hermes/skills/ai-team/repo-catalog
python3 scripts/search.py "ui ux website prettier"        # search
python3 scripts/search.py "video" --status missing        # only not-yet-installed
python3 scripts/search.py --all --web > /tmp/catalog.html # owner's private page
python3 scripts/search.py --check                         # re-verify against GitHub
python3 scripts/search.py --check --write                 # save check results
python3 scripts/search.py --test                          # self-check
```

To view the page on a phone, render the HTML to PDF (vertical page, readable at
any zoom) instead of sending the HTML file, which chat apps do not display:

```bash
uv run --with playwright python -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    pg.goto('file:///tmp/catalog.html'); pg.wait_for_timeout(400)
    pg.pdf(path='/tmp/catalog.pdf', format='A3', print_background=True)
    b.close()"
```

The page needs no server for local use: `file://` works in any browser. The owner
cannot reach files on the VPS, so to let him read it on his phone it is published at
`https://kantor.raihann.me/katalog/` behind basic auth (Caddy `handle_path /katalog/*`,
root `/usr/share/caddy/katalog/index.html`). Refresh it after the catalog changes:

```bash
python3 scripts/search.py --all --web > ~/obsidian/kantor-ai/catalog.html
sudo cp ~/obsidian/kantor-ai/catalog.html /usr/share/caddy/katalog/index.html
```

Keep it password protected: office rows carry internal statuses and rejection reasons.

1. Turn the owner's request into 3–6 keywords naming the artifact ("website ui ux", "explainer video", "defense slides"). Never paste a whole sentence.
2. Run `search.py`. If empty, the script itself tells you to search GitHub.
3. Filter results: drop `rejected` rows, drop mismatched purposes, keep at most 3.
4. For each candidate report: **purpose → why it fits this job → installed or not → the action** (install / use what is installed / not needed).
5. If installing: continue to `external-tool-vetting` (verify entity + read source + claims vs facts) before touching the system. After install, set `status` to `installed` and `level` to `proven`.

## Adding a new repo (three entry points)

The catalog must keep growing. Add a row whenever any of these happens — do not wait to be asked:

1. **The owner names a repo** ("coba repo X", pastes a link, shows a video/list).
2. **`search.py` returns nothing** and `find_github.py` finds something usable.
3. **A repo gets installed, reviewed or rejected** — flip its `status`/`level` the same session.

```bash
cd ~/.hermes/skills/ai-team/repo-catalog

# 1a. is there a SKILL for this? -> skills.sh registry, ranked by install count
python3 scripts/find_github.py "ui ux design" --skills --min-installs 30000

# 1b. is there a REPO for this (CLI, library, component kit)? -> GitHub search
python3 scripts/find_github.py "video render" --min-stars 5000

# 2. append the one you picked; stars/license/date are pulled from GitHub automatically
python3 scripts/add.py owner/repo \
  --purpose "one plain sentence: what it does" \
  --use-when "the concrete moment to reach for it" \
  --avoid "when it is wrong + which repo already covers that job" \
  --status missing --tags "video render short"

# 3. prove the catalog is still healthy
python3 scripts/search.py --test
```

### Two external sources, two different questions

| Question | Use | Why |
|---|---|---|
| "is there a **skill** for X?" | `--skills` (skills.sh) | live registry, install counts are a real quality signal, far more skills than we track |
| "is there a **repo/tool** for X?" | `--min-stars` (GitHub search) | skills.sh only lists SKILL.md packages, so CLIs, component libraries and apps are invisible there |

skills.sh is run by Vercel Labs (MIT, ~37k stars, `vercel-labs/skills`). The office API
call is `https://skills.sh/api/search?q=<words>` and returns JSON with `installs` per skill.
`npx skills find` does the same thing but drags in a whole Node package tree — prefer the API.

**What skills.sh cannot tell you, and why this catalog still exists:**
it has no idea which repo is installed in this office, which one the owner rejected and why,
which two repos do the same job, or when a tool is wrong for our load. It also cannot see
non-skill repos. So: search skills.sh for candidates, then still record the decision here.

`add.py` refuses input it cannot trust: dead or misspelled repo (GitHub 404), a repo already in the catalog, a missing `--purpose`, or `--status rejected` without `--rejected-reason`.

Flipping status after install / rejection — edit that one JSON line (never reorder rows):

```bash
# installed and actually used
"status": "installed", "level": "proven"
# read but not used yet
"status": "missing", "level": "reviewed"
# owner said no - reason is mandatory
"status": "rejected", "level": "owner rejected", "rejected_reason": "..."
```

## Catalog row format

One JSON object per line in `data/catalog.jsonl`:

| Field | Content |
|---|---|
| `name` | everyday name |
| `repo` | `owner/name` exactly as on GitHub |
| `stars` | star count at `checked` |
| `license` | SPDX (`MIT`, `Apache-2.0`, `AGPL-3.0`) or `?` when absent |
| `checked` | last verification date (`YYYY-MM-DD`) |
| `status` | `installed` / `missing` / `rejected` |
| `level` | `proven` (used, effect visible) / `reviewed` (read, not used) / `unverified` / `owner rejected` |
| `purpose` | one plain sentence: what this repo does |
| `use_when` | concrete trigger |
| `dont_use_when` | when it is wrong, plus the repo that already covers it |
| `rejected_reason` | required when `status: rejected` |
| `tags` | extra search keywords, synonyms included |
| `readme` | ~300 chars of distilled README words, auto-filled by `sync_readme.py`. Weak evidence only: a readme hit never outranks a hit in name/tags/purpose |

### Three tiers of evidence

Search scores every match by where it was found, because the fields differ in trust:

| Tier | Fields | Weight | Why |
|---|---|---|---|
| strong | `name`, `tags` | 4 | hand-picked, no filler |
| prose | `repo`, `purpose`, `use_when` | 2 | written for this office, one sentence each |
| weak | `readme` | 1 | every README is full of generic words, so it cannot be trusted to rank alone |

A repo that only matches through its README needs near-total coverage of the query before it
qualifies at all — otherwise a long README answers every question (a video repo mentions
"tokens", a design repo mentions "video"). Refresh the readme words with
`python3 scripts/sync_readme.py` (or `--all` to redo every row).

Adding an entry = append one JSON line. Do not reorder other lines. Then run `python3 scripts/search.py --test`.

## Publishing this system publicly

What gets published is the **system** (SKILL.md + `search.py` + an empty example catalog + README), **not the office catalog contents**. Users fill their own. The office catalog holds internal notes (status, owner rejection reasons, server paths) — those never leave.

The web page (`--web`) is for office use only and is not published.

## Pitfalls

- ❌ **Trusting repo names from a video transcript or article.** 2026-10-28: four names were wrong (REA, ECC, Agent Reach, GSAC) because the transcript was trusted. Correct: `morluto/rea`, `affaan-m/ECC`, `Panniantong/Agent-Reach`, `garrytan/gstack`. Always verify against the GitHub API before naming.
- ❌ **Writing long repo lists into the chat reply.** Only when the owner asks. Default: at most 3 candidates plus reasons.
- ❌ **Re-proposing a rejected repo.** Check `status` first.
- ❌ **Treating 100k stars as fitness.** Stars ≠ fit for office load; read `dont_use_when`.
- ❌ **Copying the whole catalog into a prompt or skill.** Wasteful. The script filters.
- ❌ **Writing skill/catalog text in Indonesian.** Everything an agent reads (skill files, catalog fields, commit messages, briefs) is English; only owner-facing chat uses Indonesian.
