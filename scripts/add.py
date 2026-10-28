#!/usr/bin/env python3
"""Append one repo to the catalog, pulling stars/license/date from GitHub.

  add.py owner/repo --purpose "one plain sentence" \
                    --use-when "concrete trigger" \
                    [--avoid "when it is wrong + the repo that already covers it"] \
                    [--status missing|installed|rejected] [--level unverified|reviewed|proven|owner rejected] \
                    [--tags "kode video desain"] [--rejected-reason "why owner said no"]

Refuses to append when the row cannot be trusted (no purpose, dead repo, duplicate).
Then run: python3 scripts/search.py --test
"""
import datetime
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

DATA = pathlib.Path(__file__).resolve().parent.parent / "data" / "catalog.jsonl"


def load():
    lines = DATA.read_text(encoding="utf-8").splitlines()
    return [json.loads(l) for l in lines if l.strip() and not l.lstrip().startswith("#")]


def gh(repo):
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}",
        headers={"Accept": "application/vnd.github+json",
                 **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        return json.load(urllib.request.urlopen(req, timeout=20))
    except urllib.error.HTTPError as e:
        sys.exit(f"GitHub says {e.code} for {repo} - not adding. Check the owner/name.")


def main():
    args = sys.argv[1:]
    if not args or args[0].startswith("-"):
        sys.exit(__doc__)
    repo = args[0]
    opts = {k: v for k, v in zip(args[1::2], args[2::2])}
    purpose = opts.get("--purpose", "").strip()
    if not purpose:
        sys.exit("--purpose is required: one plain sentence on what the repo does.")

    catalog = load()
    if any(r["repo"].lower() == repo.lower() for r in catalog):
        sys.exit(f"{repo} is already in the catalog. Edit that row instead of adding a second one.")

    d = gh(repo)
    status = opts.get("--status", "missing")
    if status not in ("missing", "installed", "rejected"):
        sys.exit("--status must be missing, installed or rejected")
    reason = opts.get("--rejected-reason", "")
    if status == "rejected" and not reason:
        sys.exit("--rejected-reason is required when status is rejected")

    row = {
        "name": opts.get("--name") or repo.split("/")[-1],
        "repo": d["full_name"],
        "stars": d.get("stargazers_count") or 0,
        "license": (d.get("license") or {}).get("spdx_id") or "?",
        "checked": datetime.date.today().isoformat(),
        "status": status,
        "level": opts.get("--level", "owner rejected" if status == "rejected" else "unverified"),
        "purpose": purpose,
        "use_when": opts.get("--use-when", ""),
        "dont_use_when": opts.get("--avoid", ""),
        "tags": opts.get("--tags", ""),
    }
    if reason:
        row["rejected_reason"] = reason

    with DATA.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"added: {row['name']} ({row['repo']}) {row['stars']:,} stars, license {row['license']}, "
          f"status {row['status']}")
    print("next: python3 scripts/search.py --test")


if __name__ == "__main__":
    main()
