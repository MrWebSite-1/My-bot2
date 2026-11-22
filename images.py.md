# images.py

```python
"""RASM: tayyor rasm qidirish (Pixabay, Pexels, Wikimedia) va yuborish.
Qidiruv inglizcha ishlaydi: o'zbek va rus so'zlari avval inglizchaga o'tkaziladi.
"""
import asyncio, os, random, re
import httpx
from telegram import InputMediaPhoto
from config import PIXABAY_KEY

PEXELS_KEY = os.environ.get("PEXELS_KEY", "")

TAG_RE = re.compile(r"<[^>]+>")
UA = {"User-Agent": "RezeBot/1.0 (personal Telegram bot)"}
DL_UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Mobile Safari/537.36"}

# Rasm ko'rsatilmaydigan so'rovlar: mualliflik huquqi ostidagi seriya/personajlar
# va botning o'zi (uning haqiqiy rasmi yo'q)
SELF_TERMS = ["reze", "rezе", "rеze"]
COPYRIGHT_TERMS = [
    "chainsaw man", "naruto", "one piece", "jujutsu", "attack on titan",
    "dragon ball", "pokemon", "pokémon", "harry potter", "marvel", "avengers",
    "spiderman", "spider-man", "batman", "superman", "disney", "pixar",
    "nintendo", "mario", "zelda", "frozen", "simpsons", "anime character",
]

def blocked_reason(query):
    q = query.lower()
    if any(t in q for t in COPYRIGHT_TERMS):
        return "copyright"
    if any(t in q for t in SELF_TERMS):
        return "self"
    return None

# O'zbek va rus so'zlari -> inglizcha (Pixabay va Pexels inglizchada yaxshi ishlaydi)
WORDS = {
    "kofe": "coffee", "qahva": "coffee", "кофе": "coffee",
    "choy": "tea", "чай": "tea",
    "kitob": "book", "книга": "book", "kitob o'qish": "reading book",
    "o'qish": "reading", "чтение": "reading",
    "sport": "sport", "спорт": "sport",
    "yugurish": "running", "бег": "running",
    "yurish": "walk", "sayr": "walk", "прогулка": "walk",
    "tabiat": "nature", "природа": "nature",
    "dengiz": "sea", "море": "sea",
    "tog'": "mountain", "tog": "mountain", "горы": "mountains",
    "daraxt": "tree", "дерево": "tree",
    "gul": "flower", "цветы": "flowers", "гул": "flower",
    "quyosh": "sun", "солнце": "sun",
    "yomg'ir": "rain", "yomgir": "rain", "дождь": "rain",
    "ob-havo": "weather", "погода": "weather",
    "ertalab": "morning", "утро": "morning",
    "kechqurun": "evening", "kechki": "evening", "вечер": "evening",
    "uyqu": "sleep", "сон": "sleep",
    "ovqat": "food", "еда": "food", "oshxona": "kitchen", "кухня": "kitchen",
    "shahar": "city", "город": "city",
    "mushuk": "cat", "кот": "cat", "кошка": "cat",
    "it": "dog", "собака": "dog",
    "musiqa": "music", "музыка": "music",
    "kino": "movie", "кино": "movie",
    "uy": "home", "дом": "home",
    "ish": "work", "работа": "work",
    "dam olish": "relaxation", "отдых": "relaxation",
    "kun": "day", "день": "day",
}

# Rasm so'rovidagi buyruq so'zlari (qidiruvga kirmaydi)
STOP = {"rasm", "rasmi", "rasmini", "rasmga", "rasmlar", "rasmlarini",
        "tasha", "tashla", "tashlab", "tashing", "tashlang", "ko'rsat",
        "korsat", "ko'rsating", "ber", "yubor", "menga", "va", "bir",
        "iltimos", "kerak"}
SUFFIXES = ("larining", "larini", "lari", "ining", "ini", "ning", "dan",
            "da", "ga", "ni")

def _stem(w):
    for suf in SUFFIXES:
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[:-len(suf)]
    return w

def to_english(query):
    q = query.lower().strip()
    if q in WORDS:
        return WORDS[q]
    words = re.findall(r"[a-zA-Z\u0400-\u04FF\u00C0-\u024F']+", q)
    out = []
    for w in words:
        if w in STOP:
            continue
        if w in WORDS:
            out.append(WORDS[w])
            continue
        st = _stem(w)
        if st in WORDS:
            out.append(WORDS[st])
        elif st.isascii():
            out.append(st)
    out = [x for x in out if x]
    return " ".join(out[:4]) or query

async def search_pixabay(c, query, n):
    r = await _get(c, "https://pixabay.com/api/", params={
        "key": PIXABAY_KEY, "q": query[:100],
        "image_type": "photo", "safesearch": "true",
        "per_page": 20})
    hits = r.json().get("hits", [])
    random.shuffle(hits)
    return [{"url": h.get("largeImageURL") or h["webformatURL"],
             "who": h.get("user") or "?", "src": "Pixabay"}
            for h in hits[:n + 2]]

async def search_pexels(c, query, n):
    r = await _get(c, "https://api.pexels.com/v1/search", params={
        "query": query[:100], "per_page": 15, "size": "medium"},
        headers={"Authorization": PEXELS_KEY})
    photos = r.json().get("photos", [])
    random.shuffle(photos)
    return [{"url": p["src"]["large"],
             "who": p.get("photographer") or "?", "src": "Pexels"}
            for p in photos[:n + 2]]

async def _get(c, url, **kw):
    """GET; 429 (limit) bo'lsa bir marta kutib qayta urinadi."""
    r = await c.get(url, **kw)
    if r.status_code == 429:
        await asyncio.sleep(3)
        r = await c.get(url, **kw)
    r.raise_for_status()
    return r

async def search_openverse(c, query, n):
    """Openverse: kalitsiz, ochiq litsenziyali rasmlar (CC). mature=false filtri bilan."""
    r = await _get(c, "https://api.openverse.org/v1/images/", params={
        "q": query[:100], "page_size": 20, "mature": "false"}, headers=UA)
    hits = r.json().get("results", [])
    random.shuffle(hits)
    out = []
    for h in hits:
        u = h.get("url") or ""
        if not u.lower().split("?")[0].endswith((".jpg", ".jpeg", ".png")):
            continue
        who = (h.get("creator") or "noma'lum")[:60]
        lic = (h.get("license") or "").upper()
        out.append({"url": u, "alt": h.get("thumbnail"), "src": "Openverse",
                    "who": f"{who} (CC {lic})" if lic else who})
        if len(out) >= n + 2:
            break
    return out

async def search_commons(c, query, n):
    r = await c.get("https://commons.wikimedia.org/w/api.php", params={
        "action": "query", "generator": "search",
        "gsrsearch": query + " filetype:bitmap",
        "gsrnamespace": 6, "gsrlimit": 20, "prop": "imageinfo",
        "iiprop": "url|extmetadata", "iiurlwidth": 1024,
        "format": "json"}, headers=UA)
    r.raise_for_status()
    pages = (r.json().get("query") or {}).get("pages") or {}
    out = []
    for p in pages.values():
        ii = (p.get("imageinfo") or [{}])[0]
        u = ii.get("thumburl") or ii.get("url")
        if not u or not u.lower().split("?")[0].endswith(
                (".jpg", ".jpeg", ".png")):
            continue
        meta = ii.get("extmetadata") or {}
        who = TAG_RE.sub("", (meta.get("Artist") or {})
                         .get("value", "") or "").strip()[:60]
        lic = (meta.get("LicenseShortName") or {}).get("value", "")
        who = who or "noma'lum"
        out.append({"url": u, "src": "Wikimedia Commons",
                    "who": f"{who} ({lic})" if lic else who})
    random.shuffle(out)
    return out[:n + 2]

async def _search_term(c, term, n):
    """Bitta so'z uchun manbalar navbati bilan; birinchi topilgan natija."""
    if PIXABAY_KEY:
        try:
            res = await search_pixabay(c, term, n)
            print(f"RASM Pixabay '{term}': {len(res)} ta")
            if res:
                return res
        except Exception as e:
            print("PIXABAY xato:", repr(e))
    try:
        res = await search_openverse(c, term, n)
        print(f"RASM Openverse '{term}': {len(res)} ta")
        if res:
            return res
    except Exception as e:
        print("OPENVERSE xato:", repr(e))
    if PEXELS_KEY:
        try:
            res = await search_pexels(c, term, n)
            if res:
                return res
        except Exception as e:
            print("PEXELS xato:", repr(e))
    return []

async def find_photos(query, n):
    eng = to_english(query)
    terms = [t for t in dict.fromkeys([eng] + eng.split()) if t][:4]
    async with httpx.AsyncClient(
            timeout=20, follow_redirects=True) as c:
        res = []
        for term in terms:
            res = await _search_term(c, term, n)
            if res:
                break
        if not res:
            try:
                res = await search_commons(c, eng or query, n)
                print(f"RASM Commons '{eng}': {len(res)} ta")
            except Exception as e:
                print("COMMONS xato:", repr(e))
        if not res:
            print(f"RASM topilmadi: so'rov='{query}', ingliz='{eng}', terminlar={terms}")
        out = []
        for p in res:
            if len(out) >= n:
                break
            for u in [p.get("url"), p.get("alt")]:
                if not u:
                    continue
                try:
                    d = await c.get(u, headers=DL_UA)
                    d.raise_for_status()
                    if len(d.content) < 9000000:
                        out.append((d.content, p))
                        break
                except Exception as e:
                    print("YUKLASH xato:", repr(e))
        return out

async def send_photos(msg, query, count, fallback=None):
    reason = blocked_reason(query) or (blocked_reason(fallback) if fallback else None)
    if reason == "self":
        await msg.reply_text(
            "O'zimning rasmimni tashlay olmayman, chunki menda haqiqiy yuz yo'q 🙂 "
            "Boshqa narsa, masalan manzara yoki kitob rasmini so'rashingiz mumkin.")
        return
    if reason == "copyright":
        await msg.reply_text(
            "Bu seriya yoki personaj rasmini tashlay olmayman. "
            "Boshqa mavzu aytsangiz, topishga harakat qilaman.")
        return
    got = await find_photos(query, count)
    if not got and fallback:
        print(f"RASM: model so'rovi topilmadi, asl matn bilan: '{fallback}'")
        got = await find_photos(fallback, count)
    if not got:
        await msg.reply_text("Bu haqda mos rasm topa olmadim 😔")
        return
    srcs = ", ".join(dict.fromkeys(
        f'{p["who"]} · {p["src"]}' for _, p in got))
    cap = f"📷 {srcs}"[:1000]
    if len(got) == 1:
        await msg.reply_photo(got[0][0], caption=cap)
    else:
        media = [InputMediaPhoto(b, caption=cap if i == 0 else None)
                 for i, (b, _) in enumerate(got)]
        await msg.reply_media_group(media)
```
