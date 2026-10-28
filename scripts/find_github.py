#!/usr/bin/env python3
"""Search outside the catalog: GitHub repos, or the skills.sh registry.

  find_github.py "video render"
  find_github.py "video render" --min-stars 5000
  find_github.py "ui ux" --skills          # skills.sh registry (has install counts)
  find_github.py "ui ux" --skills --min-installs 1000

Prints candidates only. Nothing is installed and nothing is appended.
Pick one, then add it with add.py.

Why the qualifiers on the GitHub path: a bare multi-word query is ANDed across
name+description and buried in noise (2026-10-28: "video render skill" topped out at
1.1k stars while the real match has 74k). `in:name,description` keeps the AND but
searches the right fields.

skills.sh (2026-10-28): a live registry of agent skills with install counts, run by
Vercel Labs (MIT, ~37k stars). Use it when the question is "is there a SKILL for X".
It does not know about non-skill repos (CLIs, component libraries) and it does not
know what this office already installed or rejected - that is what the catalog adds.
"""
import json
import os
import sys
import urllib.parse
import urllib.request

FIELD = "in:name,description"
SKILLS_API = "https://skills.sh/api/search?q="


def _get(url, token=""):
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        return json.load(urllib.request.urlopen(req, timeout=25))
    except Exception as e:
        sys.exit(f"request failed: {e}")


def find_skills(query, min_installs=0, limit=10):
    data = _get(SKILLS_API + urllib.parse.quote(query))
    items = data.get("skills") or []
    return [s for s in items if (s.get("installs") or 0) >= min_installs][:limit]


def find_repos(query, min_stars=0, readme=False, limit=8):
    if "in:" not in query:
        query += " in:name,description,readme" if readme else " " + FIELD
    url = ("https://api.github.com/search/repositories?q=" + urllib.parse.quote(query)
           + f"&sort=stars&order=desc&per_page={max(limit * 2, 20)}")
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    data = _get(url, token)
    if data.get("message"):
        sys.exit(f"GitHub says: {data['message']}")
    return [r for r in data.get("items", []) if r["stargazers_count"] >= min_stars][:limit]


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    min_stars = min_installs = 0
    for flag, key in (("--min-stars", "stars"), ("--min-installs", "installs")):
        if flag in args:
            i = args.index(flag)
            value = int(args[i + 1])
            if key == "stars":
                min_stars = value
            else:
                min_installs = value
            del args[i:i + 2]
    as_skills = "--skills" in args
    readme = "--readme" in args
    args = [a for a in args if a not in ("--skills", "--readme")]
    query = " ".join(args)

    if as_skills:
        items = find_skills(query, min_installs)
        if not items:
            print(f"no skill found for '{query}'. try fewer words")
            return
        for s in items:
            print(f"{s['installs']:>9,} installs  {s['source']}@{s['skillId']}")
            print(f"           https://skills.sh/{s['source']}/{s['skillId']}")
        print("\nNext: check the source repo, then append with add.py")
        return

    items = find_repos(query, min_stars, readme)
    if not items:
        print("no result. fewer words, or add --readme to search README text too")
        return
    for r in items:
        lic = (r.get("license") or {}).get("spdx_id") or "?"
        print(f"{r['full_name']} | {r['stargazers_count']:,} stars | {lic} | "
              f"pushed {str(r.get('pushed_at'))[:10]}")
        print(f"  {(r.get('description') or '')[:150]}")
    print('\nNext: python3 scripts/add.py <owner/repo> --purpose "..." --use-when "..."')


if __name__ == "__main__":
    main()
