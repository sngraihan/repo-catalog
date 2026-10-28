---
name: repo-catalog
description: "A searchable catalog of GitHub repos for AI agents: purpose, when to use, when NOT to use, license, and status (installed / not yet / rejected with reason). Call it when starting a task to get relevant repo recommendations. Trigger: 'which repo fits X', 'any tool for Y', 'find a github repo', before installing or proposing any third-party tool, or when a task needs a capability the agent does not have."
version: 1.0.0
license: MIT
metadata:
  hermes:
    tags: [repo, catalog, tooling, discovery, skills]
---

# Repo Catalog

One place that answers: "for this job, which repo do we use, what for, and how?"

This skill **finds candidates**. It does not install anything. Verification of a repo (does it exist, what does the source actually do, do the marketing claims hold) is a separate, mandatory step before touching a system.

## Core rules

1. **The catalog is data, not prose.** Every repo lives in `data/catalog.jsonl`. Never write repo lists inside SKILL.md — it gets read every session and burns tokens.
2. **Always search via the script, never read the whole catalog.** `scripts/search.py "<task keywords>"`.
3. **State the check date.** Every row has `checked`. If it is older than 30 days, run `--check` before quoting stars or license to anyone.
4. **If the catalog has no match, search GitHub directly** with `scripts/find_github.py`, then append the result with `scripts/add.py`. A catalog that cannot grow is a catalog that goes stale.
5. **Rejections are binding.** Rows with `rejected` status must not be proposed again without a strong new reason. The reason lives in `rejected_reason`.
6. **Check for overlap before proposing.** `dont_use_when` names the repo that already covers the same job. Propose one, not two of the same.

## Workflow

```bash
python3 scripts/search.py "ui ux website prettier"     # search
python3 scripts/search.py "video" --status missing     # only not-yet-installed
python3 scripts/search.py --all --web > catalog.html   # your own HTML page
python3 scripts/search.py --check                      # re-verify against GitHub
python3 scripts/search.py --check --write              # save the re-verification
python3 scripts/search.py --test                       # self-check
```

1. Turn the request into 3–6 keywords naming the artifact ("website ui ux", "explainer video", "defense slides"). Never paste a whole sentence.
2. Run `search.py`. If it returns nothing, go to "Growing the catalog" below.
3. Filter: drop `rejected` rows, drop mismatched purposes, keep at most 3.
4. Report each candidate as: **purpose → why it fits this job → installed or not → the action** (install / use what is installed / not needed).
5. After installing, run the verification step for that repo, then flip its `status` to `installed` and `level` to `proven`.

For the `--check` step set `GITHUB_TOKEN` (any classic token with public read is enough). Without it GitHub allows ~60 requests per hour, which is not enough for a full sweep.

## Growing the catalog

Add a row whenever any of these happens — do not wait to be asked:

1. **Someone names a repo** (a link, a video listing, "try repo X").
2. **`search.py` returns nothing** and `find_github.py` finds something usable.
3. **A repo gets installed, reviewed or rejected** — flip its `status`/`level` in the same session.

```bash
# 1. look outside the catalog
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

`add.py` refuses input it cannot trust: a dead or misspelled repo (GitHub 404), a repo already in the catalog, a missing `--purpose`, or `--status rejected` without `--rejected-reason`.

Flipping status later — edit that one JSON line, never reorder rows:

```json
{"status": "installed", "level": "proven"}
{"status": "missing",   "level": "reviewed"}
{"status": "rejected",  "level": "owner rejected", "rejected_reason": "why"}
```

## Row format

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

Why `dont_use_when` exists: star count is not fitness. Two repos that both "turn code into a map" mean you must pick one, and the catalog has to say so before the agent proposes both.

## Pitfalls

- **Trusting repo names from a video transcript or article.** Names get mangled. `REA` is `morluto/rea`, `ECC` is `affaan-m/ECC`, `GSAC` in one popular list was actually `garrytan/gstack`. Verify against the GitHub API before naming a repo to a human.
- **Writing long repo lists into a chat reply.** Only when asked. Default: at most 3 candidates plus reasons.
- **Re-proposing a rejected repo.** Check `status` first.
- **Copying the whole catalog into a prompt.** Wasteful. The script filters.
- **Bare multi-word GitHub queries.** `"video render"` alone is ANDed across name+description and drowns in noise. `find_github.py` adds `in:name,description` for you; if you query the API by hand, do the same.

## License

MIT. See `LICENSE`.
