#!/usr/bin/env python3
"""Search GitHub when the catalog has no match.

  find_github.py "video render"
  find_github.py "dashboard ui" --min-stars 5000
  find_github.py "explainer" --readme      # also search README text

Prints candidates only. Nothing is installed and nothing is appended.
Pick one, then add it with add.py.

Why the qualifiers: a bare multi-word query is ANDed across name+description and
buried in noise (2026-10-28: "video render skill" topped out at 1.1k stars while the
real match has 74k). `in:name,description` keeps the AND but searches the right fields.
"""
import json
import os
import sys
import urllib.parse
import urllib.request

FIELD = "in:name,description"


def search(query, min_stars=0, readme=False, limit=8):
    if "in:" not in query:
        query += " in:name,description,readme" if readme else " " + FIELD
    url = ("https://api.github.com/search/repositories?q=" + urllib.parse.quote(query)
           + f"&sort=stars&order=desc&per_page={max(limit * 2, 20)}")
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        data = json.load(urllib.request.urlopen(req, timeout=25))
    except Exception as e:
        sys.exit(f"GitHub search failed: {e}")
    if data.get("message"):
        sys.exit(f"GitHub says: {data['message']}")
    return [r for r in data.get("items", []) if r["stargazers_count"] >= min_stars][:limit]


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    min_stars = 0
    if "--min-stars" in args:
        i = args.index("--min-stars")
        min_stars = int(args[i + 1])
        del args[i:i + 2]
    readme = "--readme" in args
    args = [a for a in args if a != "--readme"]
    items = search(" ".join(args), min_stars, readme)
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
