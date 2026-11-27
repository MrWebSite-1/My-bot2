"""FIKR TIZIMI (2-bosqich, 4-band): javobga 👎/👍 reaksiya, /fikr, uslubni moslash.
Baza: settings.feedback (JSON matn). Oxirgi javoblar xotirada (qayta ishga tushsa tozalanadi).
"""
import asyncio, json
from collections import OrderedDict
from database import get_settings, update_setting

# belgi -> (tugma matni, modelga ko'rsatma)
TAGS = {
    "uzun": ("📏 Uzun", "javoblaring uzun bo'ldi: qisqaroq, ixchamroq yoz"),
    "sovuq": ("🧊 Sovuq", "javoblaring sovuq tuyuldi: iliqroq, jonliroq, yaqinroq gapir"),
    "hazil": ("🙄 Hazil ortiqcha", "hazil ortiqcha bo'ldi: hazilni kamaytir"),
    "qisqa": ("✂️ Juda qisqa", "javoblaring juda qisqa bo'ldi: to'liqroq yoz"),
}
OPPOSITE = {"uzun": "qisqa", "qisqa": "uzun"}
KEEP = 12          # oxirgi nechta izoh hisobga olinadi (eskisi o'zi so'nadi)
SENT = OrderedDict()
SENT_MAX = 200


def remember(cid, mid, text):
    SENT[(cid, mid)] = (text or "")[:300]
    while len(SENT) > SENT_MAX:
        SENT.popitem(last=False)


def lookup(cid, mid):
    return SENT.get((cid, mid))


def _load(st):
    try:
        d = json.loads((st or {}).get("feedback") or "{}")
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


async def _update(cid, fn):
    d = _load(await asyncio.to_thread(get_settings, cid))
    fn(d)
    await asyncio.to_thread(update_setting, cid, "feedback",
                            json.dumps(d, ensure_ascii=False))


async def add_tag(cid, tag):
    def f(d):
        tags = [t for t in d.get("tags", []) if t in TAGS] + [tag]
        d["tags"] = tags[-KEEP:]
    await _update(cid, f)


async def add_like(cid, text):
    def f(d):
        likes = [x for x in d.get("likes", []) if isinstance(x, str)]
        t = (text or "").strip()[:100]
        if t and t not in likes:
            likes.append(t)
        d["likes"] = likes[-2:]
    await _update(cid, f)


async def clear(cid):
    await asyncio.to_thread(update_setting, cid, "feedback", None)


def active_tags(st):
    seen = []
    for t in reversed(_load(st).get("tags", [])):
        if t in TAGS and t not in seen and OPPOSITE.get(t) not in seen:
            seen.append(t)
    return seen


def prompt_text(st):
    out = ""
    tags = active_tags(st)
    if tags:
        out += ("\n\nFoydalanuvchi fikri (👎 bosgan): "
                + "; ".join(TAGS[t][1] for t in tags)
                + ". Shunga moslash, lekin buni o'zing eslatib o'tirma.")
    likes = _load(st).get("likes") or []
    if likes:
        out += ("\nYoqqan javoblaring namunasi (uslubini saqla, "
                "takrorlama): " + " | ".join(likes))
    return out
