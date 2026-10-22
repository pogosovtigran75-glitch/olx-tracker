import json
import os
import re
import time
import requests

MODELS = range(13, 19)   # iPhone 13 ... 18
MAX_USD = 1000           # бюджет в долларах
USD_RATE = 12500         # сум за 1$ (примерно, можно поправить)
CITIES = ["ташкент", "tashkent"]
BAD_WORDS = ["чехол", "case", "стекло", "кабель", "зарядк",
             "ремонт", "куплю", "ищу", "запчаст", "коробк"]

TOKEN = os.environ["TG_TOKEN"]
CHAT = os.environ["TG_CHAT"]
SEEN_FILE = "seen.json"

MODEL_RE = re.compile(r"(iphone|айфон)\s*-?\s*(1[3-8])(?!\d)", re.I)
QUERIES = [f"{name} {n}" for n in MODELS for name in ("iphone", "айфон")]


def tg(text):
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT, "text": text},
        timeout=20,
    )


def get_offers(query):
    r = requests.get(
        "https://www.olx.uz/api/v1/offers/",
        params={
            "query": query,
            "limit": 40,
            "offset": 0,
            "sort_by": "created_at:desc",
        },
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("data", [])


def price_usd(o):
    for p in o.get("params", []):
        if p.get("key") == "price":
            v = p.get("value", {})
            val = v.get("value")
            if val is None:
                return None, v.get("label", "")
            if str(v.get("currency", "")).upper() == "USD":
                return val, v.get("label", "")
            return val / USD_RATE, v.get("label", "")
    return None, "цена не указана"


def city_of(o):
    return (o.get("location", {}).get("city", {}) or {}).get("name", "")


def suitable(o):
    title = (o.get("title") or "").lower()
    if not MODEL_RE.search(title):
        return False
    if any(w in title for w in BAD_WORDS):
        return False
    if not any(c in city_of(o).lower() for c in CITIES):
        return False
    usd, _ = price_usd(o)
    if usd is not None and usd > MAX_USD:
        return False
    return True


offers = {}
fails = 0
for q in QUERIES:
    try:
        for o in get_offers(q):
            offers[str(o["id"])] = o
    except Exception as e:
        fails += 1
        print("ошибка:", q, e)
    time.sleep(1)

if fails == len(QUERIES):
    raise SystemExit("OLX не отвечает")

if os.path.exists(SEEN_FILE):
    seen = set(json.load(open(SEEN_FILE)))
    first_run = False
else:
    seen = set()
    first_run = True

if first_run:
    tg("Бот запущен. Слежу за iPhone 13-18, Ташкент, до 1000$")
else:
    for oid, o in offers.items():
        if oid in seen or not suitable(o):
            continue
        usd, label = price_usd(o)
        approx = f" (~{usd:.0f}$)" if usd is not None else ""
        tg(f"{o.get('title')}\n{label}{approx}\n{city_of(o)}\n{o.get('url')}")

seen.update(offers.keys())
json.dump(sorted(seen)[-5000:], open(SEEN_FILE, "w"))
