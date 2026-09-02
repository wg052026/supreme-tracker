#!/usr/bin/env python3
"""
Supreme data scraper (v3) - 시즌을 자동으로 따라간다.
- Released items by week (1..20) + left-to-drop (unreleased) from supremedroplist.com
- Prices: parsed per-card from week pages (released items only)
- Images: multiple images per item pulled from each item's detail page (for hover preview)
Writes data/data.json for the board.

Run: python scripts/scrape.py
"""
import re, html, json, sys, time, urllib.request, concurrent.futures
from pathlib import Path

BASE = "https://supremedroplist.com"
OUT = Path(__file__).resolve().parent.parent / "data" / "data.json"

SEASON_FALLBACK = "springsummer-2026"  # used only if auto-detect fails
SEASON_SUFFIX = "ss26"  # 상품 주소 꼬리 - set_season_suffix() 가 시즌에서 정한다


def detect_season():
    """Find the currently-active season from the homepage.
    The live season uses a long slug (springsummer-YYYY / fallwinter-YYYY)
    and is the only one with /week-N links. Returns (slug, kream_tag, label)."""
    try:
        h = fetch(BASE + "/")
    except Exception:
        h = ""
    # season that has week links = the one in progress
    wk = re.findall(r'/season/((?:springsummer|fallwinter)-\d{4})/week-\d+', h)
    cand = wk[0] if wk else None
    if not cand:
        longs = re.findall(r'/season/((?:springsummer|fallwinter)-\d{4})', h)
        cand = max(set(longs), key=longs.count) if longs else SEASON_FALLBACK
    m = re.match(r'(springsummer|fallwinter)-(\d{4})', cand)
    if m:
        sec, year = m.group(1), m.group(2)
        yy = year[2:]
        tag = f"{yy}ss" if sec == "springsummer" else f"{yy}fw"
        label = ("Spring/Summer " if sec == "springsummer" else "Fall/Winter ") + year
        return cand, tag, label
    return SEASON_FALLBACK, "26ss", "Spring/Summer 2026"

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
    orig = n
    # drop a trailing duplicated colourway tail like "... Mossy Oak® Country DNA"
    n = re.sub(r'\s+(Mossy Oak®?|Realtree®?)\s+(Country\s+DNA.*|Camo.*)$', '', n, flags=re.I).strip()
    # strip trailing colour words, but never reduce below 2 words / 6 chars
    for _ in range(3):
        m = re.search(r'\s+(' + '|'.join(map(re.escape, COLOR_WORDS)) + r')$', n)
        if not m:
            break
        cand = n[:m.start()].strip()
        if len(cand) < 6 or len(cand.split()) < 2:
            break
        n = cand
    return n or orig


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


IMG_RE = re.compile(r'(https://supremedroplist\.com/images/item-images/media/[^\s"\'<>]+?\.webp)')
ANCHOR_RE = re.compile(r'href="(/items/[^"]+-ss26)"')


def set_season_suffix(sfx):
    """상품 주소 꼬리를 시즌에 맞춘다.

    [실패 2026-08-20 ~ 09-02 · 13일 동안 매번 `scraped 0 items`]
    시즌이 26SS -> 26FW 로 넘어갔는데 꼬리 `-ss26` 이 코드에 박혀 있어
    상품 링크를 한 건도 못 잡았다. 시즌 감지(detect_season)는 잘 되고 있었다.
    실측 2026-09-02 : /items/supreme-nike-air-max-2001-air-ecstasy-fw26
    """
    global SEASON_SUFFIX, ANCHOR_RE
    SEASON_SUFFIX = sfx
    ANCHOR_RE = re.compile(r'href="(/items/[^"]+-' + re.escape(sfx) + r')"')


def slug_from_url(url):
    m = re.search(r'/items/([^"/]+)-' + re.escape(SEASON_SUFFIX), url)
    return m.group(1) if m else ""


def parse_page_cards(htmltext):
    """Split a season/week page into per-item cards (anchor to next anchor).
    Returns list of {slug,url,name,img,price}."""
    starts = [m.start() for m in ANCHOR_RE.finditer(htmltext)]
    starts.append(len(htmltext))
    out = []
    seen = set()
    for i in range(len(starts) - 1):
        block = htmltext[starts[i]:starts[i + 1]]
        am = ANCHOR_RE.search(block)
        if not am:
            continue
        href = am.group(1)
        url = BASE + href
        slug = slug_from_url(url)
        if not slug or slug in seen:
            continue
        # name: prefer alt text, else line-clamp paragraph
        nm = re.search(r'alt="([^"]+)"', block)
        if nm:
            name = html.unescape(nm.group(1)).strip()
        else:
            pm = re.search(r'line-clamp-2[^>]*>\s*([^<]+?)\s*</p>', block)
            name = html.unescape(pm.group(1)).strip() if pm else ""
        if not name or re.match(r'(spring/summer|fall/winter)', name.lower()):
            continue
        im = IMG_RE.search(block)
        if not im:
            continue
        img = im.group(1).split("?")[0]
        # price: first $NN(N) in the card
        pm = re.search(r'\$\s?(\d{2,4})(?:\.\d{2})?\b', block)
        price = "$" + pm.group(1) if pm else None
        out.append({"slug": slug, "url": url, "name": name, "img": img, "price": price})
        seen.add(slug)
    return out


def detail_images(slug, fallback_img):
    """Pull all images belonging to this item from its detail page (for hover)."""
    try:
        h = fetch(f"{BASE}/items/{slug}-{SEASON_SUFFIX}")
    except Exception:
        return [fallback_img]
    key = slug.replace("-", "")[:20]
    out = []
    for x in IMG_RE.findall(h):
        x = x.split("?")[0]
        fn = x.split("/")[-1].replace("-", "")
        if fn.startswith(key) and x not in out:
            out.append(x)
    if fallback_img and fallback_img not in out:
        out.insert(0, fallback_img)
    return out or [fallback_img]


def scrape(with_detail_images=True, max_detail_workers=8):
    season, kream_tag, season_label = detect_season()
    set_season_suffix(("ss" if season.startswith("springsummer") else "fw") + season[-2:])

    # 1) unreleased
    ltd_raw = fetch(f"{BASE}/season/{season}/left-to-drop")
    ltd = {c["url"]: c for c in parse_page_cards(ltd_raw)}

    # 2) released by week
    released = {}

    def pull_week(w):
        try:
            d = fetch(f"{BASE}/season/{season}/week-{w}")
        except Exception:
            return []
        res = []
        for c in parse_page_cards(d):
            c = dict(c); c["week"] = w
            res.append(c)
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

    released_urls = set(released.keys())

    items = []
    uorder = {}
    for url, c in ltd.items():
        if url in released_urls:
            continue
        nm = c["name"]
        cat = guess_cat(nm)
        uorder[cat] = uorder.get(cat, 0) + 1
        items.append({
            "id": "u-" + cat.lower().replace("/", "-") + "-" + str(uorder[cat]),
            "name": nm, "cat": cat, "price": None,
            "url": url, "img": c["img"], "imgs": [c["img"]],
            "released": False, "week": None,
        })
    i = 0
    for url, c in released.items():
        nm = clean_name(c["name"])
        items.append({
            "id": "r-" + str(i), "name": nm, "cat": guess_cat(nm),
            "price": c.get("price"),
            "url": url, "img": c["img"], "imgs": [c["img"]],
            "released": True, "week": c["week"],
        })
        i += 1

    # 3) detail images (hover) — fetch each item's detail page
    if with_detail_images:
        def enrich(it):
            it["imgs"] = detail_images(slug_from_url(it["url"]), it["img"])
            return it
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_detail_workers) as ex:
            list(ex.map(enrich, items))

    weeks = [c["week"] for c in released.values() if c.get("week")]
    latest = max(weeks) if weeks else None

    return {
        "items": items,
        "cats": CAT_ORDER,
        "updated": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "latestWeek": latest,
        "season": season,
        "seasonLabel": season_label,
        "kreamTag": kream_tag,
        "counts": {
            "unreleased": sum(1 for x in items if not x["released"]),
            "released": sum(1 for x in items if x["released"]),
        },
    }


def main():
    detail = "--no-detail" not in sys.argv
    data = scrape(with_detail_images=detail)
    if data["counts"]["unreleased"] == 0 and data["counts"]["released"] == 0:
        print("ERROR: scraped 0 items, not writing.", file=sys.stderr)
        sys.exit(1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    npriced = sum(1 for x in data["items"] if x.get("price"))
    nmulti = sum(1 for x in data["items"] if len(x.get("imgs", [])) > 1)
    print(f"Wrote {OUT} | unreleased={data['counts']['unreleased']} released={data['counts']['released']} "
          f"latestWeek={data['latestWeek']} priced={npriced} multiImg={nmulti}")


if __name__ == "__main__":
    main()
