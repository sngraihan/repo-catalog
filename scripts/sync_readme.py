#!/usr/bin/env python3
"""Pull each repo's README from GitHub and distil it into a keyword line for search.

  sync_readme.py              refresh rows that have no readme yet
  sync_readme.py --all        refresh every row
  sync_readme.py --only owner/repo

Why a stored keyword line instead of the README itself:
a full README is 5-40KB each; 52 of them would make the catalog unreadable and
expensive to load. What actually helps search is the VOCABULARY the author uses
("text effects", "DTCG", "percentile"), because that is often more precise than
the one-sentence purpose we wrote by hand. So we keep words, not prose.

Matching weight: readme words count as weak evidence only (see search.py). A hit
in name/tags/purpose still outranks a hit found only in the readme, otherwise a
long README turns into a false-positive machine.
"""
import base64
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request

DATA = pathlib.Path(__file__).resolve().parent.parent / "data" / "catalog.jsonl"
LIMIT = 320          # characters kept per repo
STOP = {
    "the", "and", "for", "with", "that", "this", "from", "your", "you", "our", "are", "was",
    "will", "can", "not", "but", "all", "any", "use", "used", "using", "into", "when", "what",
    "how", "why", "which", "they", "them", "then", "than", "there", "their", "its", "also",
    "more", "most", "some", "such", "only", "just", "like", "make", "made", "get", "set",
    "one", "two", "new", "now", "out", "off", "per", "via", "you", "have", "has", "had",
    "docs", "readme", "license", "http", "https", "www", "com", "github", "repo", "repository",
    "install", "installation", "quick", "start", "example", "examples", "usage", "npm", "pip",
    "badge", "img", "badges", "shields", "svg", "png", "jpg", "table", "contents",
}


def token():
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""


def fetch_readme(repo):
    url = f"https://api.github.com/repos/{repo}/readme"
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        **({"Authorization": f"Bearer {token()}"} if token() else {})})
    try:
        data = json.load(urllib.request.urlopen(req, timeout=25))
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except Exception as e:
        return None, str(e)[:60]
    try:
        return base64.b64decode(data.get("content", "")).decode("utf-8", "ignore"), None
    except Exception as e:
        return None, str(e)[:60]


def distill(text):
    # drop the furniture: code fences, html, images, bare urls, tables, emphasis
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"^\s*\|.*$", " ", text, flags=re.M)
    text = re.sub(r"[`*_>#~|]", " ", text)
    words, seen = [], set()
    for w in re.findall(r"[A-Za-z][A-Za-z0-9+.\-]{2,}", text):
        low = w.lower().strip(".-")
        if len(low) < 3 or low in STOP or low in seen:
            continue
        seen.add(low)
        words.append(low)
    out = ""
    for w in words:
        if len(out) + len(w) + 1 > LIMIT:
            break
        out += w + " "
    return out.strip()


def load():
    lines = DATA.read_text(encoding="utf-8").splitlines()
    return [json.loads(l) for l in lines if l.strip() and not l.lstrip().startswith("#")]


def main():
    args = sys.argv[1:]
    rows = load()
    refresh_all = "--all" in args
    only = None
    if "--only" in args:
        only = args[args.index("--only") + 1]

    changed = skipped = failed = 0
    for r in rows:
        if only and r["repo"] != only:
            continue
        if r.get("readme") and not refresh_all and not only:
            skipped += 1
            continue
        text, err = fetch_readme(r["repo"])
        if err:
            print(f"SKIP  {r['repo']}: {err}")
            failed += 1
            continue
        words = distill(text)
        if len(words) < 20:
            print(f"THIN  {r['repo']}: only {len(words)} chars of usable words")
        if words != r.get("readme"):
            r["readme"] = words
            changed += 1
            print(f"OK    {r['repo']}: {len(words)} chars")
        else:
            skipped += 1

    if changed:
        DATA.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                        encoding="utf-8")
    print(f"\n{changed} updated, {skipped} unchanged, {failed} failed, {len(rows)} rows")


if __name__ == "__main__":
    main()
