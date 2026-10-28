#!/usr/bin/env python3
"""Search the repo catalog. stdlib only, no network.

  search.py "ui ux"                 search
  search.py "video" --status missing
  search.py --all                   dump whole catalog
  search.py "slides" --web          HTML page
  search.py --check [--write]       re-verify against GitHub API
  search.py --test                  self-check
"""
import html
import json
import pathlib
import re
import sys

DATA = pathlib.Path(__file__).resolve().parent.parent / "data" / "catalog.jsonl"
STOP = {"the", "a", "an", "and", "or", "for", "with", "make", "want", "need", "please",
        "my", "our", "to", "of", "in", "on", "is", "it", "that", "this", "more", "better",
        "how", "what", "some", "any", "can", "you", "me", "i", "we", "do", "does", "be"}
LABEL = {"installed": "INSTALLED", "missing": "NOT YET", "rejected": "REJECTED"}


def load():
    lines = DATA.read_text(encoding="utf-8").splitlines()
    return [json.loads(l) for l in lines if l.strip() and not l.lstrip().startswith("#")]


def search(catalog, words, status=None):
    keys = [w.lower() for w in words.split() if w.strip() and w.lower() not in STOP]
    found = []
    for r in catalog:
        if status and r.get("status") != status:
            continue
        hay = " ".join(str(r.get(k, "")) for k in
                       ("name", "repo", "purpose", "use_when", "dont_use_when", "tags")).lower()
        hits = 0
        for k in keys:
            # short words must match whole ("ui" must not match "build"); longer words may be partial
            if (re.search(rf"\b{re.escape(k)}\b", hay) if len(k) <= 3 else k in hay):
                hits += 1
        if keys and hits == 0:
            continue
        found.append((hits, r))
    found.sort(key=lambda x: (-x[0], -x[1].get("stars", 0)))
    return [r for _, r in found]


def show(r):
    out = [f"{r['name']} ({r['repo']}) - {r.get('stars', 0):,} stars - "
           f"{LABEL.get(r.get('status'), r.get('status'))} - {r.get('level', '?')}"]
    out.append(f"  what    : {r.get('purpose', '')}")
    out.append(f"  use when: {r.get('use_when', '')}")
    if r.get("dont_use_when"):
        out.append(f"  avoid   : {r['dont_use_when']}")
    if r.get("status") == "rejected" and r.get("rejected_reason"):
        out.append(f"  rejected: {r['rejected_reason']}")
    out.append(f"  checked : {r.get('checked', '?')}")
    return "\n".join(out)


def web(catalog):
    rows = []
    for r in sorted(catalog, key=lambda x: (x.get("status") != "installed", -x.get("stars", 0))):
        cls = {"installed": "ok", "rejected": "no"}.get(r.get("status"), "")
        rows.append(
            f'<tr class="{cls}"><td><b>{html.escape(r["name"])}</b><br>'
            f'<a href="https://github.com/{html.escape(r["repo"])}">{html.escape(r["repo"])}</a></td>'
            f'<td>{r.get("stars", 0):,}</td><td>{html.escape(str(r.get("license", "")))}</td>'
            f'<td>{html.escape(str(r.get("status", "")))}</td>'
            f'<td>{html.escape(r.get("purpose", ""))}<br><i>{html.escape(r.get("dont_use_when") or "")}</i></td></tr>')
    return f"""<!doctype html><meta charset="utf-8"><title>Repo catalog</title>
<style>body{{font:15px/1.5 system-ui;margin:24px;background:#0d1117;color:#c9d1d9}}
table{{border-collapse:collapse;width:100%}}td,th{{padding:8px;border-bottom:1px solid #30363d;vertical-align:top}}
a{{color:#58a6ff}}tr.ok td{{background:#0d2818}}tr.no td{{background:#2d1416;opacity:.7}}i{{color:#8b949e}}</style>
<h2>Repo catalog ({len(catalog)})</h2><table><tr><th>Repo</th><th>Stars</th><th>License</th><th>Status</th><th>Purpose</th></tr>
{chr(10).join(rows)}</table>"""


def check(write=False):
    """Re-verify every row against GitHub: still exists, stars, license, last push."""
    import datetime
    import os
    import urllib.request

    catalog = load()
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    changed = 0
    for r in catalog:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{r['repo']}",
            headers={"Accept": "application/vnd.github+json",
                     **({"Authorization": f"Bearer {token}"} if token else {})})
        try:
            d = json.load(urllib.request.urlopen(req, timeout=20))
        except Exception as e:
            print(f"GONE/ERR  {r['repo']}: {e}")
            changed += 1
            continue
        fresh = {"stars": d.get("stargazers_count") or 0,
                 "license": (d.get("license") or {}).get("spdx_id") or "?",
                 "checked": datetime.date.today().isoformat()}
        diff = [f"{k} {r.get(k)} -> {v}" for k, v in fresh.items()
                if r.get(k) != v and k != "checked"]
        if diff:
            print(f"CHANGED  {r['repo']}: " + "; ".join(diff))
            changed += 1
        r.update(fresh)
    if write and changed:
        DATA.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in catalog) + "\n",
                        encoding="utf-8")
        print(f"catalog rewritten, {changed} rows changed")
    else:
        print(f"{len(catalog)} repos checked, {changed} need attention")


def test():
    c = load()
    assert len(c) >= 1, "catalog is empty"
    assert all("repo" in r and "purpose" in r for r in c), "row missing repo/purpose"
    assert all(r["status"] in ("installed", "missing", "rejected") for r in c), "bad status value"
    assert all(r.get("rejected_reason") for r in c if r["status"] == "rejected"), "rejected row without reason"
    res = search(c, "ui ux")
    assert res, "query 'ui ux' returned nothing"
    assert any("ui-ux" in r["repo"] or "taste" in r["repo"] for r in res), "design repos not found"
    assert not search(c, "zzz-nothing-here"), "gibberish query returned results"
    assert all(r["status"] == "missing" for r in search(c, "code", status="missing"))
    print(f"PASS: {len(c)} repos, search works, status filter works, rejected rows carry reasons")


def main():
    args = sys.argv[1:]
    if "--test" in args:
        return test()
    if "--check" in args:
        return check(write="--write" in args)
    catalog = load()
    status = None
    if "--status" in args:
        i = args.index("--status")
        status = args[i + 1]
        del args[i:i + 2]
    as_web = "--web" in args
    args = [a for a in args if a != "--web"]
    words = "" if "--all" in args else " ".join(args)
    res = search(catalog, words, status)
    if not res:
        print('No match in the catalog. Search GitHub directly with '
              'scripts/find_github.py "<keywords>", then append results to data/catalog.jsonl.')
        return
    print(web(res) if as_web else "\n\n".join(show(r) for r in res))


if __name__ == "__main__":
    main()
