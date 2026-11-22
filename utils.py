"""YORDAMCHILAR: JSON o'qish, matnni bo'lib yuborish, uslub matni, stiker paketi.
"""
import asyncio, json, random, re
from datetime import datetime
from config import STATE, STYLES, TZ
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
    await msg.reply_text((text or "...").strip() + extra)

def style_text(st):
    key = (st or {}).get("style") or "muloyim"
    extra = STYLES.get(key, STYLES["muloyim"])[1]
    return ("\n\n" + extra) if extra else ""

async def get_pack(bot, st):
    name = (st or {}).get("sticker_set")
    if not name or st.get("stickers") is False:
        return {}
    cache = STATE.setdefault("packs", {})
    if name in cache:
        return cache[name]
    try:
        ss = await bot.get_sticker_set(name)
        d = {}
        for x in ss.stickers:
            if x.emoji:
                d.setdefault(x.emoji, []).append(x.file_id)
        cache[name] = d
        return d
    except Exception as e:
        print("PAKET xato:", e)
        return {}

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
    muhim = [x for x in rows if tier_of(x["fact"]) == "muhim"][-40:]
    rest = [x for x in rows if tier_of(x["fact"]) != "muhim"]
    room = max(0, limit - len(muhim))
    return muhim + (rest[-room:] if room else [])


def habit_text(cid):
    """Kuniga ko'pi bilan bitta odat, ixtiyoriy eslatiladi. Voqea emas, doimiy xususiyat."""
    from character import HABITS
    day = datetime.now(TZ).strftime("%Y-%m-%d")
    rnd = random.Random(f"habit-{cid}-{day}")
    if rnd.random() > 0.4:
        return ""
    h = rnd.choice(HABITS)
    return ("\n\nOdat (ixtiyoriy, faqat tabiiy bo'lsa): " + h + ". "
            "Buni o'tgan zamondagi voqea qilib aytma, majburlama.")


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
