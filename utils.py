"""YORDAMCHILAR: JSON o'qish, matnni bo'lib yuborish, uslub matni, stiker paketi.
"""
import asyncio, json, random, re
from datetime import datetime
from config import STATE, STYLES, TZ, STICKER_PRIMARY_P
from character import MOODS

def parse_json(t):
    t = (t or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t).strip()
    try:
        d = json.loads(t)
        return d if isinstance(d, dict) else None
    except Exception:
        pass
    m = re.search(r'"answer"\s*:\s*"((?:[^"\\]|\\.)*)"', t, re.S)
    if m:
        try:
            return {"answer": json.loads('"' + m.group(1) + '"')}
        except Exception:
            return {"answer": m.group(1)}
    return None

async def send_text(msg, bot, text, extra=""):
    # Javob doim bitta xabar bo'lib yuboriladi
    return await msg.reply_text((text or "...").strip() + extra)

def style_text(st):
    key = (st or {}).get("style") or "muloyim"
    extra = STYLES.get(key, STYLES["muloyim"])[1]
    return ("\n\n" + extra) if extra else ""

def _ne(e):
    """Emojini taqqoslash uchun: ko'rinmas FE0F belgisiz, bo'shliqsiz."""
    return str(e or "").replace("\ufe0f", "").strip()


# Stiker belgilari (hissiyot). Bitta paketda stikerlar emojisi bir xil bo'lsa ham
# ular belgilanadi (/stiker_belgila) va model emoji o'rniga shu so'zni tanlaydi.
STICKER_LABELS = ["sevinch", "kulgi", "erkalash", "xafa", "yig'lash", "jahl",
                  "hayron", "uyqu", "uyalish", "ma'qullash", "salomlashish",
                  "o'ylash", "boshqa"]
_LABEL_EMOJI = {
    "sevinch": "😊 😄 😃 😀 🙂 😌 🥳 🎉 🤩 ✨ 🌟 😁",
    "kulgi": "😂 🤣 😆 😹 😜 😝 🤪 😏 😎 😈",
    "erkalash": "🥰 😍 😘 ❤ 💕 💖 💗 💘 💞 🤗 😚 😙 💋 🫶 💝",
    "xafa": "😔 😞 😟 🙁 ☹ 😕 🥺 😒 🙄 😑 😐 😩 😫 😓",
    "yig'lash": "😢 😭 🥲 😿 💔 😥",
    "jahl": "😠 😡 🤬 😤 👿 😾 💢",
    "hayron": "😮 😲 😱 😳 🤯 😨 😧 🙀 😯 🤨 😵",
    "uyqu": "😴 🥱 😪 💤 🛌",
    "uyalish": "🙈 😅 ☺ 🫣 😶 😬 🤭",
    "ma'qullash": "👍 👌 ✅ 👏 🙌 💪 🫡 🆒 🙏 💯 🔥",
    "salomlashish": "👋 🤝 ✌ 🖐 🤚 🤙",
    "o'ylash": "🤔 🧐 🤓 💭 🫤",
}
EMOJI_LABEL = {_ne(e): lab for lab, es in _LABEL_EMOJI.items() for e in es.split()}


def pack_names(st):
    return [x.strip() for x in str((st or {}).get("sticker_set") or "").split(",") if x.strip()]


def labels_of(st):
    """Saqlangan belgilar: {paket: {stiker_uid: belgi}} (settings.sticker_labels)."""
    raw = (st or {}).get("sticker_labels")
    if isinstance(raw, dict):
        return raw
    try:
        d = json.loads(raw) if raw else {}
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


async def _load_pack(bot, name):
    try:
        ss = await bot.get_sticker_set(name)
        d, items = {}, []
        for x in ss.stickers:
            if getattr(x, "type", None) == "custom_emoji":
                continue  # oddiy stiker sifatida yuborib bo'lmaydi
            if x.emoji:
                d.setdefault(x.emoji, []).append(x.file_id)
            th = getattr(x, "thumbnail", None)
            items.append({
                "fid": x.file_id, "uid": getattr(x, "file_unique_id", None) or x.file_id,
                "emoji": _ne(x.emoji),
                "anim": bool(getattr(x, "is_animated", False) or getattr(x, "is_video", False)),
                "thumb": getattr(th, "file_id", None) if th else None})
        print("PAKET yuklandi:", name, len(items), "stiker,", len(d), "xil emoji")
        return name, d, items
    except Exception as e:
        print("PAKET xato:", name, e)
        return name, None, None


async def ensure_packs(bot, names):
    """Keshda yo'q paketlarni bir vaqtda yuklaydi. Yuklanganlar ro'yxatini qaytaradi."""
    cache = STATE.setdefault("packs", {})
    cache_i = STATE.setdefault("packitems", {})
    missing = [n for n in names if n not in cache or n not in cache_i]
    if missing:
        for name, d, items in await asyncio.gather(*(_load_pack(bot, n) for n in missing)):
            if d is not None:
                cache[name] = d
                cache_i[name] = items
    return [n for n in names if n in cache and n in cache_i]


async def get_pack(bot, st):
    """Barcha paketlarni (vergul bilan) birlashtirib, emotsiya bo'yicha qaytaradi.
    Keshda yo'q paketlar bir vaqtda yuklanadi."""
    names = pack_names(st)
    if not names or (st or {}).get("stickers") is False:
        return {}
    await ensure_packs(bot, names)
    cache = STATE.get("packs", {})
    merged = {}
    for name in names:
        for k, v in cache.get(name, {}).items():
            merged.setdefault(k, []).extend(v)
    return merged


def primary_pack(st):
    """Asosiy paket (ro'yxatdagi birinchi) stikerlari, emotsiya bo'yicha. get_pack dan keyin chaqiriladi."""
    names = pack_names(st)
    if not names or (st or {}).get("stickers") is False:
        return {}
    return STATE.get("packs", {}).get(names[0], {})


def sticker_prompt(st, pack):
    """Modelga stiker tanlash ko'rsatmasi: belgilangan paketlardan so'zlar,
    belgilanmaganlardan emojilar. Stiker har javobga emas."""
    if not pack:
        return ""
    labs = labels_of(st)
    items = STATE.get("packitems", {})
    words, emojis = [], []
    for n in pack_names(st):
        lm = labs.get(n) or {}
        if lm:
            for lab in STICKER_LABELS[:-1] + ["boshqa"]:
                if lab in lm.values() and lab not in words:
                    words.append(lab)
        else:
            for e in (STATE.get("packs", {}).get(n) or {}):
                if e not in emojis:
                    emojis.append(e)
    options = words + emojis[:max(10, 40 - len(words))]
    if not options:
        return ""
    return ("\n\nStiker: javobingga mos stiker yuborish uchun sticker maydoniga "
            "quyidagi so'zlar yoki emojilardan BITTASINI yoz: " + " ".join(options)
            + ". Stikerni har javobga emas, faqat his aniq bo'lganda (quvonch, "
            "erkalash, hayrat, xafalik, hazil) ishlat: taxminan har 3-4 "
            "javobning birida. Qolgan paytda sticker null bo'lsin.")


def choose_sticker(st, stk):
    """Avval paket tanlanadi (asosiy paket STICKER_PRIMARY_P ehtimol bilan), keyin
    shu paketdan modelning so'ziga/emojisiga mos stiker; mos kelmasa paketdan
    tasodifiy. Qaytaradi: (paket nomi, file_id) yoki None."""
    key = str(stk or "").strip()
    if not key:
        return None
    names = pack_names(st)
    items = STATE.get("packitems", {})
    loaded = [n for n in names if items.get(n)]
    if not loaded:
        return None
    primary = names[0] if items.get(names[0]) else None
    others = [n for n in loaded if n != primary]
    if primary and (not others or random.random() < STICKER_PRIMARY_P):
        pk = primary
    else:
        pk = random.choice(others or loaded)
    its = items[pk]
    lm = labels_of(st).get(pk) or {}
    low = key.lower().replace("\u2019", "'").replace("\u02bb", "'").replace("`", "'")
    if low in STICKER_LABELS:
        if lm:
            cands = [i for i in its if lm.get(i["uid"]) == low]
        else:
            cands = [i for i in its if EMOJI_LABEL.get(i["emoji"]) == low]
    else:
        ne = _ne(key)
        cands = [i for i in its if i["emoji"] == ne]
        if not cands and lm and EMOJI_LABEL.get(ne):
            cands = [i for i in its if lm.get(i["uid"]) == EMOJI_LABEL[ne]]
    return pk, random.choice(cands or its)["fid"]


async def _sticker_image(bot, it):
    """Belgilash uchun stikerning rasmi (animatsiyali bo'lsa kichik rasmi)."""
    from google.genai import types
    fid = it["thumb"] if it["anim"] else it["fid"]
    if not fid:
        return None
    f = await bot.get_file(fid)
    raw = bytes(await f.download_as_bytearray())
    ext = (f.file_path or "").lower().rsplit(".", 1)[-1]
    mime = {"webp": "image/webp", "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "png": "image/png"}.get(ext)
    if not mime or len(raw) > 4000000:
        return None
    return types.Part.from_bytes(data=raw, mime_type=mime)


async def label_pack(bot, cid, st, name, save, batch=10):
    """Paketdagi belgilanmagan stikerlarni Gemini bilan belgilaydi (10 tadan so'rov).
    save(cid, matn) har bo'lakdan keyin saqlaydi. st['sticker_labels'] yangilanadi.
    Qaytaradi: (belgilar soni {belgi: n}, belgilanmay qolganlar soni)."""
    from google.genai import types
    from ai import gen, SAFETY
    from config import CHAT_MODELS
    if name not in await ensure_packs(bot, [name]):
        raise RuntimeError("paket yuklanmadi")
    items = STATE["packitems"][name]
    allv = labels_of(st)
    cur = dict(allv.get(name) or {})
    todo = [i for i in items if i["uid"] not in cur]
    for k in range(0, len(todo), batch):
        chunk = todo[k:k + batch]
        imgs = []
        for it in chunk:
            try:
                part = await _sticker_image(bot, it)
            except Exception as e:
                print("BELGILASH rasm xato:", e)
                part = None
            if part is not None:
                imgs.append((it, part))
        if not imgs:
            continue
        prompt = ("Quyida %d ta stiker rasmi tartib bilan. Har birining hissiyotini "
                  "quyidagi so'zlardan FAQAT BIRI bilan belgila: %s. Faqat JSON "
                  'qaytar: {"labels": ["so\'z", ...]}, rasmlar tartibida, aynan %d ta.'
                  % (len(imgs), ", ".join(STICKER_LABELS), len(imgs)))
        parts = [types.Part(text=prompt)]
        for n, (_, part) in enumerate(imgs, 1):
            parts += [types.Part(text="%d-rasm:" % n), part]
        try:
            r = await gen(models=CHAT_MODELS, contents=[types.Content(role="user", parts=parts)],
                          config=types.GenerateContentConfig(
                              temperature=0.2, safety_settings=SAFETY,
                              response_mime_type="application/json"))
            labs = (parse_json(r.text) or {}).get("labels")
        except Exception as e:
            print("BELGILASH xato:", repr(e))
            continue
        if not isinstance(labs, list) or len(labs) != len(imgs):
            print("BELGILASH: javob soni mos emas")
            continue
        for (it, _), lab in zip(imgs, labs):
            lab = str(lab or "").strip().lower().replace("\u2019", "'")
            cur[it["uid"]] = lab if lab in STICKER_LABELS else "boshqa"
        allv[name] = cur
        st["sticker_labels"] = json.dumps(allv, ensure_ascii=False)
        await save(cid, st["sticker_labels"])
    counts = {}
    for it in items:
        lab = cur.get(it["uid"])
        if lab:
            counts[lab] = counts.get(lab, 0) + 1
    return counts, sum(1 for it in items if it["uid"] not in cur)


def mark(cur, key, label):
    return ("✔ " if cur == key else "") + label


def _period(h):
    if h < 5:
        return "tun"
    if h < 11:
        return "ertalab"
    if h < 17:
        return "kunduzi"
    if h < 22:
        return "kechqurun"
    return "kech tun"

BOTKAYF_TAG = "[botkayf "
KECHA_TAG = "[kecha "
KUNOXI_TAG = "[kunoxi "
ODATREJIM_TAG = "[odatrejim] "
ODATKUN_TAG = "[odatkun "

def auto_mood(cid, now=None):
    now = now or datetime.now(TZ)
    seed = f"{cid}-{now.strftime('%Y-%m-%d')}-{_period(now.hour)}"
    return random.Random(seed).choice(MOODS)

def period_key(now=None):
    now = now or datetime.now(TZ)
    return now.strftime("%Y-%m-%d") + "-" + _period(now.hour)

def today_mood(rows, now=None):
    """Shu kun qismi uchun qo'yilgan kayfiyat (qo'lda), bo'lmasa None."""
    tag = BOTKAYF_TAG + period_key(now) + "] "
    found = [x["fact"][len(tag):] for x in rows if x["fact"].startswith(tag)]
    return found[-1] if found else None

def mood_text(cid, override=None):
    """Har chat va har kun uchun bir xil kayfiyat (kun ichida o'zgarmaydi)."""
    m = auto_mood(cid) if override is None else override
    return ("\n\nBugungi kayfiyating: " + m + ". Buni javobingda "
            "tabiiy seze olsin, lekin o'zingni tushuntirib o'tirma.\n"
            "Faktlar orasida 'Ichki hazil' bo'lsa, ularni o'rinli "
            "ishlat, hammasini birdan emas.")


UZ_DAYS = ["dushanba", "seshanba", "chorshanba", "payshanba",
           "juma", "shanba", "yakshanba"]

def time_text(now=None):
    """Hafta kuni, kun vaqti va shunga mos ohang haqida qisqa kontekst."""
    now = now or datetime.now(TZ)
    wd, h = now.weekday(), now.hour
    if h < 5:
        per = "tun"
    elif h < 11:
        per = "ertalab"
    elif h < 17:
        per = "kunduzi"
    elif h < 22:
        per = "kechqurun"
    else:
        per = "kech tun"
    hint = ""
    if wd >= 5:
        hint = "Bugun dam olish kuni: ohang bo'shroq, rejalar haqida erkin."
    elif wd == 0:
        hint = "Bugun dushanba: odamlar odatda ish boshlanishidan charchoq bo'ladi."
    elif wd == 4:
        hint = "Bugun juma: hafta oxiri his-tuyg'usi bor."
    if per in ("tun", "kech tun"):
        hint += (" Hozir tun: javoblaring qisqa, sekinroq va kam emoji bilan,"
                 " uyqusirab yozayotgandek.")
    return ("Hozir " + UZ_DAYS[wd] + ", " + per + ", soat "
            + now.strftime("%H:%M") + ". " + hint
            + " Shu vaqtga mos his bilan yoz, vaqtni aynan aytib o'tirma.")


TIERS = ("muhim", "oddiy", "yengil")

def tier_of(fact):
    for t in TIERS:
        if fact.startswith("[" + t + "]"):
            return t
    return "oddiy"

def with_tier(fact, default="oddiy"):
    if any(fact.startswith("[" + t + "]") for t in TIERS):
        return fact
    return "[" + default + "] " + fact

STATE_TAG = "[holat "

def today_state(rows, now=None):
    """Shu kun uchun foydalanuvchi aytgan kayfiyat/holat, bo'lmasa None."""
    today = (now or datetime.now(TZ)).strftime("%Y-%m-%d")
    tag = STATE_TAG + today + "] "
    found = [x["fact"][len(tag):] for x in rows if x["fact"].startswith(tag)]
    return found[-1] if found else None

def order_facts(rows, limit=60):
    """Muhimlar doim e'tiborda; qolganlari eng yangisidan boshlab, limit ichida."""
    rows = [x for x in rows if not x["fact"].startswith(STATE_TAG)]
    rows = [x for x in rows if not x["fact"].startswith("[odat]")]
    rows = [x for x in rows if not x["fact"].startswith(BOTKAYF_TAG)]
    rows = [x for x in rows if not x["fact"].startswith(KECHA_TAG)]
    rows = [x for x in rows if not x["fact"].startswith(KUNOXI_TAG)]
    rows = [x for x in rows if not x["fact"].startswith(ODATREJIM_TAG)]
    rows = [x for x in rows if not x["fact"].startswith(ODATKUN_TAG)]
    muhim = [x for x in rows if tier_of(x["fact"]) == "muhim"][-40:]
    rest = [x for x in rows if tier_of(x["fact"]) != "muhim"]
    room = max(0, limit - len(muhim))
    return muhim + (rest[-room:] if room else [])


def parse_odat(fact):
    """'[odat] emoji|matn|rasm so'rovi' -> (emoji, matn, rasm so'rovi)"""
    body = fact[len("[odat] "):] if fact.startswith("[odat] ") else fact
    bits = body.split("|", 2) + ["", "", ""]
    return bits[0].strip(), bits[1].strip(), bits[2].strip()


def get_odat_mode(rows):
    """Odat rejimi: A, B, AB (standart), yoq."""
    found = [x["fact"][len(ODATREJIM_TAG):].strip() for x in rows
             if x["fact"].startswith(ODATREJIM_TAG)]
    return found[-1] if found else "AB"

def habit_rule(mode):
    if "B" in mode:
        return (". O'tgan zamonda bir marta aytishing mumkin (bugun), "
                "faqat shu odat haqida, bosimsiz.")
    return ". Buni o'tgan zamondagi voqea qilib aytma, majburlama."

def intimacy_text(n):
    """Suhbat uzunligiga qarab sekin samimiylik (foydalanuvchi xabarlari soni bo'yicha)."""
    if n < 30:
        s = ("Siz bilan hali yangi tanishmiz: ehtiyotkor, iliq va hurmatli gapir, "
             "shaxsiy savollarni ortiqcha so'rama.")
    elif n < 200:
        s = ("Suhbatimiz ancha tanish: iliqroq va do'stona gapir, lekin sirlarga "
             "tez kirmagin.")
    else:
        s = ("Siz bilan ancha yaqinmiz: samimiy va erkin gapir, lekin egalik yoki "
             "yakkaxonlik bildirma.")
    return "\n\n" + s


_PEER_LINE = re.compile(r"^\[[^\]\n]{1,30}\]: ")

def is_peer_line(content):
    """Ikkinchi botning gapi bazada '[Ism]: matn' ko'rinishida saqlanadi."""
    return bool(_PEER_LINE.match(content or ""))
