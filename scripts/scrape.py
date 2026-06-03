#!/usr/bin/env python3
"""
Supreme 26S/S data scraper.
Fetches the full season (released items by week) + left-to-drop (unreleased)
from supremedroplist.com and writes data/data.json for the board.

Run: python scripts/scrape.py
"""
import re, html, json, sys, time, urllib.request, concurrent.futures
from pathlib import Path

SEASON = "springsummer-2026"
BASE = "https://supremedroplist.com"
OUT = Path(__file__).resolve().parent.parent / "data" / "data.json"

CAT_ORDER = ["Jackets", "Shirts", "Tops/Sweaters", "Sweatshirts", "Pants",
             "Shorts", "T-Shirts", "Hats", "Bags", "Accessories", "Shoes", "Skate"]

COLOR_WORDS = ['Heather Grey', 'Light Grey', 'Dark Green', 'Royal', 'Multicolor',
    'Navy', 'Brown', 'Black', 'White', 'Red', 'Green', 'Pink', 'Yellow', 'Purple',
    'Orange', 'Tan', 'Grey', 'Gray', 'Blue', 'Olive', 'Indigo', 'Camo', 'Cream',
    'Burgundy', 'Teal', 'Gold', 'Silver', 'Charcoal', 'Khaki', 'Rust', 'Maroon',
    'Beige', 'Mint', 'Lavender', 'Stone', 'Sand', 'Bone', 'Forest', 'Mustard',
    'Coral', 'Wine', 'Plum', 'Slate', 'Floral', 'Plaid']


def fetch(url, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; SupremeBoardBot/1.0)"})
            return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def clean_name(name):
    n = name.strip()
    n = re.sub(r'\s*-\s*[A-Z][a-zA-Z]+$', '', n)              # " - Milan"
    n = re.sub(r'\s+(Realtree®?.*|Mossy Oak®?.*|Country DNA Camo.*)$', '', n)
    for _ in range(3):
        m = re.search(r'\s+(' + '|'.join(map(re.escape, COLOR_WORDS)) + r')$', n)
        if m:
            n = n[:m.start()].strip()
        else:
            break
    return n


def guess_cat(name):
    n = name.lower()
    if re.search(r'jacket|coat|parka|anorak|casket|varsity', n): return "Jackets"
    if re.search(r'sweatshirt|hoodie|hooded|crewneck|pullover|half zip', n): return "Sweatshirts"
    if re.search(r'jean|pant|trouser|sweatpant', n): return "Pants"
    if re.search(r'short', n): return "Shorts"
    if re.search(r'\b(hat|cap|beanie|6-panel|5-panel|new era|crusher|fitted)\b', n): return "Hats"
    if re.search(r'backpack|duffle|\bbag\b|wallet|pouch|keychain', n): return "Bags"
    if re.search(r'\btee\b|t-shirt', n): return "T-Shirts"
    if re.search(r'cardigan|sweater|knit', n): return "Tops/Sweaters"
    if re.search(r'shirt|\btop\b|jersey|henley', n): return "Shirts"
    if re.search(r'skateboard|wheel|truck|deck', n): return "Skate"
    if re.search(r'\bshoe|sneaker|boot|half cab|vans\b', n): return "Shoes"
    return "Accessories"


def parse_cards(htmltext):
    """Return list of {name,url,img} from anchors to /items/ in a page."""
    out = []
    for m in re.finditer(r'<a[^>]+href="(/items/[^"]+)"[^>]*>(.*?)</a>', htmltext, flags=re.S):
        href, inner = m.group(1), m.group(2)
        am = re.search(r'alt="([^"]+)"', inner)
        if not am:
            continue
        name = html.unescape(am.group(1)).replace("&#38;", "&").strip()
        if not name or name.startswith("Spring/Summer 2026") or "banner" in name.lower():
            continue
        im = re.search(r'(https://supremedroplist\.com/images/item-images/[^\s"]+?\.webp)', inner)
        if not im:
            continue
        out.append({"name": name, "url": BASE + href, "img": im.group(1).split("?")[0]})
    return out


def scrape():
    # 1) left-to-drop (unreleased)
    ltd_raw = fetch(f"{BASE}/season/{SEASON}/left-to-drop")
    ltd_cards = parse_cards(ltd_raw)
    # dedupe by url
    ltd = {}
    for c in ltd_cards:
        ltd[c["url"]] = c

    # 2) released items, week by week (1..20)
    released = {}  # url -> {name,url,img,week}
    def pull_week(w):
        res = []
        try:
            d = fetch(f"{BASE}/season/{SEASON}/week-{w}")
        except Exception:
            return res
        for c in parse_cards(d):
            c2 = dict(c); c2["week"] = w
            res.append(c2)
        return res

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        for batch in ex.map(pull_week, range(1, 21)):
            for c in batch:
                u = c["url"]
                score = 0 if "group-00" in c["img"] else 1
                cur = released.get(u)
                if cur is None or c["week"] < cur["week"] or (c["week"] == cur["week"] and score < cur.get("score", 9)):
                    c["score"] = score
                    released[u] = c

    # unreleased = ltd urls not in released
    released_urls = set(released.keys())

    items = []
    # unreleased first
    uorder = {}
    for url, c in ltd.items():
        if url in released_urls:
            continue
        nm = c["name"]
        cat = guess_cat(nm)
        uorder.setdefault(cat, 0)
        uorder[cat] += 1
        items.append({
            "id": "u-" + cat.lower().replace("/", "-") + "-" + str(uorder[cat]),
            "name": nm, "cat": cat, "price": None,
            "url": url, "img": c["img"], "released": False, "week": None,
        })
    # released
    i = 0
    for url, c in released.items():
        nm = clean_name(c["name"])
        items.append({
            "id": "r-" + str(i), "name": nm, "cat": guess_cat(nm), "price": None,
            "url": url, "img": c["img"], "released": True, "week": c["week"],
        })
        i += 1

    weeks = [c["week"] for c in released.values() if c.get("week")]
    latest = max(weeks) if weeks else None

    data = {
        "items": items,
        "cats": CAT_ORDER,
        "updated": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "latestWeek": latest,
        "counts": {
            "unreleased": sum(1 for x in items if not x["released"]),
            "released": sum(1 for x in items if x["released"]),
        },
    }
    return data


def main():
    data = scrape()
    if data["counts"]["unreleased"] == 0 and data["counts"]["released"] == 0:
        print("ERROR: scraped 0 items, not writing (keeping previous data).", file=sys.stderr)
        sys.exit(1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {OUT} | unreleased={data['counts']['unreleased']} released={data['counts']['released']} latestWeek={data['latestWeek']}")


if __name__ == "__main__":
    main()
