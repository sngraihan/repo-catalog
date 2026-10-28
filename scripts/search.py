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

# Catalog fields are English (agents read them), but the owner searches in Indonesian.
# Map the words he actually types onto the English terms used in tags/purpose.
SYNONYM = {
    "kode": "code", "ngoding": "code", "coding": "code", "program": "code",
    "desain": "design", "tampilan": "web ui ux website", "ui": "ui", "ux": "ux",
    "website": "website web", "situs": "website web", "halaman": "web page",
    "video": "video", "presentasi": "presentation slides", "slide": "presentation slides",
    "dokumen": "document", "ppt": "presentation pptx", "powerpoint": "presentation pptx",
    "tulisan": "writing", "nulis": "writing", "naskah": "writing academic",
    "memori": "memory", "ingatan": "memory", "peta": "map", "gambar": "visual diagram",
    "diagram": "diagram", "hemat": "token saving", "jualan": "sales marketing",
    "iklan": "sales marketing", "lowongan": "jobs cv", "loker": "jobs cv",
    "riset": "research", "pasar": "market research",
    # "cari" alone means search; it used to also inject "research", which made
    # "cari skill" rank research repos above the skills registry (found 28/10)
    "cari": "search",
    "keamanan": "security", "uang": "payment", "bayar": "payment",
    "hadiah": "reward", "suara": "voice audio", "musik": "music audio",
    "web": "web", "desainer": "design", "tabel": "document excel spreadsheet",
    "excel": "excel spreadsheet", "word": "word document", "pdf": "pdf document",
    "reels": "video reels short", "animasi": "video animation",
    # words that name the ACTION rather than the artifact - found by false-negative
    # testing 28/10: "bongkar desain website" and "panduan ui web" both returned only
    # the three big design skills while the actually-correct repo sat outside the top 3
    "bongkar": "extract teardown", "tiru": "extract clone reference",
    "contek": "extract clone reference", "sontek": "extract clone reference",
    "panduan": "guidelines rules", "aturan": "guidelines rules", "pedoman": "guidelines rules",
    "cek": "audit review", "periksa": "audit review", "nilai": "audit review",
    # gaps found 28/10 by probing Indonesian queries that returned nothing useful
    "efek": "effect animation", "teks": "text typography", "bergerak": "animation motion",
    "kontras": "contrast wcag", "warna": "colour color", "ukuran": "size layout",
    "laporan": "report", "kerja": "work", "hasil": "report output", "cetak": "export print",
}


def load():
    lines = DATA.read_text(encoding="utf-8").splitlines()
    return [json.loads(l) for l in lines if l.strip() and not l.lstrip().startswith("#")]


def search(catalog, words, status=None):
    keys = []
    for w in words.lower().split():
        if not w.strip() or w in STOP:
            continue
        # expand one Indonesian word into the English terms the catalog actually uses
        keys.extend(SYNONYM.get(w, w).split())
    found = []
    for r in catalog:
        if status and r.get("status") != status:
            continue
        # dont_use_when is excluded on purpose: it names what the repo is NOT for,
        # so matching it produces false hits ("not for design tasks" hits "design").
        hay = " ".join(str(r.get(k, "")) for k in
                       ("name", "repo", "purpose", "use_when", "tags")).lower()
        strong_hay = (str(r.get("name", "")) + " " + str(r.get("tags", ""))).lower()
        # readme words are evidence too, but the weakest kind: every README is full of
        # generic vocabulary, so a readme hit must never outrank a curated field hit.
        readme_hay = str(r.get("readme", "")).lower()
        hits = strong = soft = 0
        for k in keys:
            # short words must match whole ("ui" must not match "build"); longer words may be partial
            whole = len(k) <= 3
            here = bool(re.search(rf"\b{re.escape(k)}\b", hay) if whole else k in hay)
            if here:
                hits += 1
                if (re.search(rf"\b{re.escape(k)}\b", strong_hay) if whole else k in strong_hay):
                    strong += 1
            elif (re.search(rf"\b{re.escape(k)}\b", readme_hay) if whole else k in readme_hay):
                soft += 1
        if keys:
            if hits == 0:
                # readme-only match needs near-total coverage, otherwise every long README
                # answers every query (e.g. "tokens" appearing in a video repo's blurb)
                need = len(keys) if len(keys) <= 2 else max(2, (len(keys) + 1) // 2)
                if soft < need:
                    continue
            # drop weak matches: one shared word out of many ("the web" in a research repo) is noise
            elif hits < (2 if len(keys) >= 4 else 1):
                if soft < len(keys):
                    continue
        # a match on name/tags is worth more than one buried in prose, and prose more than the readme
        found.append((strong * 4 + (hits - strong) * 2 + soft, r))
    # ties: prefer what the office already has, then popularity
    RANK = {"installed": 0, "missing": 1, "rejected": 2}
    found.sort(key=lambda x: (-x[0], RANK.get(x[1].get("status"), 3), -x[1].get("stars", 0)))
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
        status = {"installed": "installed", "missing": "not yet", "rejected": "rejected"}.get(
            r.get("status"), r.get("status", ""))
        rows.append(
            f'<tr class="{cls}"><td data-l="repo"><b>{html.escape(r["name"])}</b>'
            f'<a href="https://github.com/{html.escape(r["repo"])}">{html.escape(r["repo"])}</a></td>'
            f'<td data-l="stars">{r.get("stars", 0):,}</td>'
            f'<td data-l="license">{html.escape(str(r.get("license", "")))}</td>'
            f'<td data-l="status">{html.escape(status)}</td>'
            f'<td data-l="what">{html.escape(r.get("purpose", ""))}'
            f'<i>{html.escape(r.get("dont_use_when") or "")}</i></td></tr>')
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Repo catalog</title>
<style>
:root{{color-scheme:dark}}
body{{font:16px/1.5 system-ui,-apple-system,sans-serif;margin:0;padding:16px;background:#0d1117;color:#c9d1d9}}
h1{{font-size:20px;margin:0 0 12px}}table{{border-collapse:collapse;width:100%}}
td,th{{padding:10px;border-bottom:1px solid #30363d;vertical-align:top;text-align:left}}
th{{font-size:13px;color:#8b949e;text-transform:uppercase;letter-spacing:.04em}}
a{{color:#58a6ff;text-decoration:none;display:block;font-size:14px}}
tr.ok td{{background:#0d2818}}tr.no td{{background:#2d1416;opacity:.7}}i{{color:#8b949e;display:block;font-size:14px}}
@media (max-width:640px){{
  body{{padding:12px}}
  thead{{display:none}}
  tr{{display:block;margin:0 0 12px;border:1px solid #30363d;border-radius:10px;overflow:hidden}}
  td{{display:block;border:0;padding:6px 12px}}
  td[data-l="repo"]{{padding-top:12px}}
  td[data-l="what"]{{padding-bottom:12px}}
  td[data-l="stars"]::before{{content:"★ " attr(data-l) ": ";color:#8b949e}}
  td[data-l="license"]::before{{content:"license: ";color:#8b949e}}
  td[data-l="status"]::before{{content:"status: ";color:#8b949e}}
  td[data-l="stars"],td[data-l="license"],td[data-l="status"]{{display:inline-block;font-size:14px;color:#8b949e}}
}}
</style>
<h1>Repo catalog ({len(catalog)})</h1><table><thead><tr><th>Repo</th><th>Stars</th><th>License</th>
<th>Status</th><th>Purpose</th></tr></thead><tbody>
{chr(10).join(rows)}</tbody></table></html>"""


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
    # owner searches in Indonesian: these must all find something.
    # guarded: a fresh catalog has a handful of rows and cannot satisfy them.
    if len(c) >= 20:
        for q in ("kode", "desain", "video", "presentasi", "tulisan", "memori", "peta"):
            assert search(c, q), f"Indonesian query '{q}' returned nothing"
    # every one of these must reach the intended repo in the top 3.
    # 2026-10-28: the first run of this list failed on 2 of 15, which is the whole
    # point of having it - a false negative is invisible unless something checks.
    must_find = [
        ("bikin video dari html", "heygen-com/hyperframes"),
        ("presentasi sidang", "hugohe3/ppt-master"),
        ("cari kerjaan loker", "career-ops-hq/career-ops"),
        ("riset tren pasar", "mvanhorn/last30days-skill"),
        ("baca internet tanpa api", "Panniantong/Agent-Reach"),
        ("animasi scroll website", "greensock/gsap-skills"),
        ("komponen animasi react", "DavidHDev/react-bits"),
        ("transisi modal dropdown", "Jakubantalik/transitions.dev"),
        ("bongkar desain website", "Manavarya09/design-extract"),
        ("cek keamanan aplikasi", "usestrix/strix"),
        ("peta kode", "Graphify-Labs/graphify"),
        ("naskah skripsi", "nothinx/naskah-id"),
        ("hemat token", "JuliusBrussee/caveman"),
        ("logo produk", "kaankiziltug/logo-design-skill"),
        ("panduan ui web", "vercel-labs/web-interface-guidelines"),
        ("cari skill", "vercel-labs/skills"),
        ("daftar skill", "vercel-labs/skills"),
        # these three only pass once the readme field exists: the words are in the
        # README, not in the one-sentence purpose we wrote by hand
        ("efek teks bergerak", "DavidHDev/react-bits"),
        ("cek kontras warna", "Manavarya09/design-extract"),
        ("laporan hasil kerja", "kharmanskyi/open-steps"),
    ]
    if len(c) >= 20:
        missed = [f"{q} -> {want}" for q, want in must_find
                  if want not in [r["repo"] for r in search(c, q)[:3]]]
        assert not missed, "queries that lost their intended repo: " + "; ".join(missed)

    # precision: nonsense must return nothing, not everything
    for q in ("zzz", "asdf", "makan bakso", "harga sepeda"):
        assert not search(c, q), f"nonsense query '{q}' returned results"

    # the readme field feeds weak matching; if it silently disappeared, search would
    # still pass but with less vocabulary - so assert it is actually there
    if len(c) >= 20:
        missing_readme = [r["repo"] for r in c if not r.get("readme")]
        assert not missing_readme, f"rows without readme words: {missing_readme} (run sync_readme.py)"

    # a long query must not drag in repos that share one generic word
    long_q = search(c, "website ui ux redesign landing page prettier")
    names = [r["repo"] for r in long_q]
    assert names, "long design query returned nothing"
    assert not any("ppt-master" in n or "hyperframes" in n for n in names), \
        f"long query pulled in unrelated repos: {names}"
    print(f"PASS: {len(c)} repos, search works, status filter works, "
          f"rejected rows carry reasons, weak matches dropped")


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
