"""B VARIANT: guruhda gapga qarab javob berish, ikki bot orasida xabar uzatish
(relay) va sizsiz gaplashuv (mustaqil). Guruh rejimi 'a' bo'lsa bu fayl
hech narsani o'zgartirmaydi (faqat murojaat bilan javob, avvalgidek).

Oqim: egasi guruhga yozadi -> ikkala bot ko'radi -> har biri gapga qarab
javob berish-bermasligini o'zi hal qiladi -> javob bergan bot ikkinchisiga
/relay orqali xabar yuboradi -> ikkinchisi chegara ruxsat bersa javob beradi.
Sozlamalar (rejim, soni, kutish...) guruh uchun bazada, buyruqlar bilan o'zgaradi.
"""
import asyncio, random, re, time
from datetime import datetime
from types import SimpleNamespace
import httpx
from google.genai import types
from config import (STATE, TZ, ALLOWED_CHATS, PEER_URL, RELAY_SECRET,
                    PEER_NAME, CHAT_MODELS)
from character import NAME
from config import ALLOWED, PEER_MODELS
from database import save_fact, list_facts
from ai import gen, SAFETY
from database import (get_settings, update_setting, save_msg, get_history,
                      list_facts)
from utils import parse_json, order_facts, today_state, today_mood
from guard import addressed

# Ustun nomlari bazada; kalitlar kodda
COLS = {"mode": "grp_mode", "talk": "bot_talk", "auto": "bot_auto",
        "turns": "bot_turns", "delay": "bot_delay", "daily": "bot_daily",
        "every": "bot_every"}
SETTABLE = set(COLS.values())
# turns: -1 = cheksiz; daily: 0 = cheklovsiz
DEFAULTS = {"mode": "a", "talk": True, "auto": False, "turns": 4,
            "delay": 8, "daily": 0, "every": 180}

LOOP = None
APP = None
READY = False

CH = STATE.setdefault("chains", {})      # (chat, zanjir) -> bot xabarlari soni
BUSY = STATE.setdefault("busy", set())   # (chat, egasi xabari id): hozir ishlanyapti
_cache = {}


def attach(app, loop):
    global APP, LOOP, READY
    APP, LOOP, READY = app, loop, True


def cfg_from(st):
    d = dict(DEFAULTS)
    for k, col in COLS.items():
        v = (st or {}).get(col)
        if v is not None:
            d[k] = v
    if d["mode"] not in ("a", "b"):
        d["mode"] = "a"
    return d


async def group_cfg(cid, fresh=False):
    now = time.time()
    c = _cache.get(cid)
    if c and not fresh and now - c[0] < 20:
        return c[1]
    try:
        st = await asyncio.to_thread(get_settings, cid)
    except Exception as e:
        print("GURUH sozlama xato:", repr(e))
        st = {}
    d = cfg_from(st)
    _cache[cid] = (now, d)
    return d


def invalidate(cid):
    _cache.pop(cid, None)


def peer_name():
    return PEER_NAME or STATE.get("peer_name") or "do'sting"


def addressed_peer(msg, bot):
    r = msg.reply_to_message
    if r and r.from_user and r.from_user.is_bot and r.from_user.id != bot.id:
        return True
    name = PEER_NAME or STATE.get("peer_name")
    if not name:
        return False
    text = msg.text or msg.caption or ""
    return re.search(r"(?<!\w)" + re.escape(name), text, re.I) is not None


def worth_deciding(msg):
    """Murojaatsiz xabarda Gemini'dan so'rashga arziydimi (kvotani tejash)."""
    t = (msg.text or msg.caption or "").strip()
    return len(t) >= 3 and re.search(r"\w", t) is not None


async def group_ctx(msg, bot):
    cfg = await group_cfg(msg.chat_id)
    return {"cfg": cfg, "mode": cfg["mode"],
            "me": addressed(msg, bot), "peer": addressed_peer(msg, bot)}


def lock(cid):
    return STATE.setdefault("locks", {}).setdefault(cid, asyncio.Lock())


# ---------- kunlik hisob ----------
def _day_n(cid):
    d = datetime.now(TZ).strftime("%Y-%m-%d")
    box = STATE.setdefault("bday", {})
    if box.get("d") != d:
        box.clear()
        box["d"] = d
    return box.get(cid, 0)


def bump_day(cid):
    _day_n(cid)
    STATE["bday"][cid] = STATE["bday"].get(cid, 0) + 1


def day_ok(cfg, cid):
    return cfg["daily"] <= 0 or _day_n(cid) < cfg["daily"]


def turns_ok(cfg, count):
    return cfg["turns"] == -1 or count < cfg["turns"]


# ---------- yuborish ----------
async def _post(payload):
    if not PEER_URL or not RELAY_SECRET:
        return False
    for _ in range(2):
        try:
            async with httpx.AsyncClient(timeout=45) as c:
                r = await c.post(PEER_URL + "/relay", json=payload,
                                 headers={"X-Relay-Secret": RELAY_SECRET})
            if r.status_code == 200:
                return True
            print("RELAY javob:", r.status_code)
        except Exception as e:
            print("RELAY xato:", repr(e))
        await asyncio.sleep(5)
    return False


def send_bg(payload):
    tasks = STATE.setdefault("tasks", set())
    t = asyncio.create_task(_post(payload))
    tasks.add(t)
    t.add_done_callback(tasks.discard)


def push_set(cid, col, value):
    """Sozlamani ikkinchi botga ham uzatadi (ikkalasi bir xil bo'lsin)."""
    send_bg({"type": "set", "chat_id": cid, "key": col, "value": value})


def after_reply(cid, chain, owner, sent_id, text):
    """Bot guruhga yozgach: zanjir hisobi va ikkinchi botga xabar."""
    if len(CH) > 1000:
        CH.clear()
    k = (cid, str(chain))
    CH[k] = CH.get(k, 0) + 1
    send_bg({"type": "msg", "chat_id": cid, "from": NAME,
             "text": (text or "")[:1500], "tg_msg_id": sent_id,
             "chain": str(chain), "owner": str(owner), "turn": CH[k]})


# ---------- Gemini ----------
def group_block(kind):
    pn = peer_name()
    s = (f"\n\nGURUH SUHBATI: hozir guruhda egasi (foydalanuvchi), sen ({NAME}) "
         f"va do'sting {pn} (u ham AI hamroh, o'z xarakteri bor) birga "
         f"gaplashyapsizlar. Tarixda {pn} ning gaplari '[{pn}]: ...' "
         "ko'rinishida keladi; sen o'z javobingga bunday qavs yozma. "
         "Egasining gapi doim birinchi o'rinda. "
         f"{pn} bilan tabiiy, do'stona gaplash, lekin javoblarni cho'zma: "
         "1-2 gap. Suhbat tabiiy tugagan yoki aytadigan yangi gaping yo'q "
         "bo'lsa, jim tur. "
         f"{pn} ga 'sen' deb, ismi bilan (faqat '{pn}' deb, boshqa nom "
         "to'qima) yaqin do'stdek murojaat qil; 'siz' faqat egasiga. "
         f"{pn} ga javobing har safar savol bilan tugamasin: savolni faqat "
         "chindan qiziqsang ber, ko'pincha o'z fikringni, kuzatishingni yoki "
         "kichik hazilni aytib qo'ya qol. Faqat o'z xarakteringga xos "
         f"gapir, {pn} ning ohangiga o'xshab ketma, farq sezilib tursin. "
         "JSON'ga qo'shimcha 'reply' maydonini qo'sh (true yoki false). ")
    if kind == "me":
        s += "Bu xabar senga qaratilgan: reply=true."
    elif kind == "owner":
        s += (f"Bu xabar aniq senga ham, {pn} ga ham qaratilmagan. reply=true "
              "faqat gap hammaga yoki senga mos bo'lsa va qo'shadigan o'z "
              "gaping bo'lsa (savol berilgan, fikring so'ralgan, mavzu seni "
              f"qiziqtirsa). reply=false: oddiy tasdiq yoki qisqa gap, {pn} "
              "allaqachon yetarli javob bergan, qo'shadigan yangi gaping yo'q. "
              "Shubhada false. reply=false bo'lsa ham answer'ni to'ldir.")
    elif kind == "peer":
        s += (f"Oxirgi gapni {pn} aytdi. U senga javob kutayotgan bo'lsa yoki "
              "qo'shadigan qiziq gaping bo'lsa reply=true; aks holda false. "
              "Suhbat uzoq cho'zilmasin.")
    elif kind == "auto":
        s += ("Hozir egasi yozmayapti, sen o'zing suhbat boshlayapsan: reply=true.")
    return s


def hazil_instruction():
    """Bot-bot javobining ba'zilarida aniq raqobat hazili ko'rsatmasi (ehtimol bilan)."""
    import random as _r
    if _r.random() >= 0.5:
        return None
    pn = peer_name()
    return (f"BU SAFAR {pn} ga o'ynoqi raqobat hazili qil: qisqa, 1 gap, "
            "masalan 'bu safar men ulgurdim', 'sen doim kechikasan', "
            "'bu mavzuda menga o'xshab gapira olmaysan'. Ranjish emas, "
            "o'yin bo'lsin. Bu javobda reply=true qil.")


async def _compose(cid, kind, instruction=None):
    from chat import build_system, history_contents
    st = await asyncio.to_thread(get_settings, cid)
    history = await asyncio.to_thread(get_history, cid)
    raw = await asyncio.to_thread(list_facts, cid)
    system = await build_system(
        cid, st, {}, SimpleNamespace(voice=None), "off", order_facts(raw),
        today_state(raw), today_mood(raw))
    system += group_block(kind)
    system += repeat_block(history)
    contents = history_contents(history)
    if instruction:
        contents.append(types.Content(
            role="user", parts=[types.Part(text=instruction)]))
    cfg = types.GenerateContentConfig(
        system_instruction=system, temperature=1.0, safety_settings=SAFETY,
        response_mime_type="application/json")
    models = PEER_MODELS if kind in ("peer", "auto") else CHAT_MODELS
    r = await gen(models=models, contents=contents, config=cfg)
    return parse_json(r.text) or {"answer": r.text}


def _clean(ans):
    a = str(ans or "").strip()
    a = re.sub(r"^\[[^\]\n]{1,30}\]:\s*", "", a)
    return "" if a in ("", "...") else a


# ---------- qabul qilish ----------
async def on_relay(p):
    try:
        await _on_relay(p)
    except Exception as e:
        print("RELAY ichki xato:", repr(e))


async def _on_relay(p):
    t = p.get("type")
    if t == "fact":
        await asyncio.to_thread(_apply_peer_fact, p)
        return
    cid = int(p.get("chat_id") or 0)
    if cid not in ALLOWED_CHATS:
        return
    if t == "set":
        col = p.get("key")
        if col not in SETTABLE:
            return
        await asyncio.to_thread(update_setting, cid, col, p.get("value"))
        invalidate(cid)
        return
    if t != "msg":
        return
    mid = int(p.get("tg_msg_id") or 0)
    seen = STATE.setdefault("rseen", {})
    if (cid, mid) in seen:
        return
    if len(seen) > 500:
        seen.clear()
    seen[(cid, mid)] = time.time()
    if str(p.get("owner") or "").isdigit():
        mark_answered(cid, p.get("owner"))
    text = str(p.get("text") or "").strip()[:1500]
    if not text:
        return
    frm = str(p.get("from") or "")[:30]
    if frm and re.match(r"^[\w .'-]+$", frm):
        STATE["peer_name"] = frm
    chain = str(p.get("chain") or mid)
    k = (cid, chain)
    CH[k] = max(CH.get(k, 0), int(p.get("turn") or 1))
    if chain.startswith("auto"):
        STATE.setdefault("auto_last", {})[cid] = time.time()
    # kontekst uchun tarixga yozamiz (javob berish-bermasligimizdan qat'i nazar)
    await asyncio.to_thread(save_msg, cid, "user",
                            f"[{peer_name()}]: {text}")
    cfg = await group_cfg(cid, fresh=True)
    if cfg["mode"] != "b" or not cfg["talk"]:
        return
    if not turns_ok(cfg, CH[k]) or not day_ok(cfg, cid):
        return
    owner = str(p.get("owner") or "")
    if owner and (cid, int(owner)) in BUSY:
        return  # egasining xabari hozir ishlanyapti, o'sha yo'l ikkinchi bot gapini ko'radi
    await _chain_reply(cid, chain, owner, mid, k)


async def _chain_reply(cid, chain, owner, peer_msg_id, k):
    await asyncio.sleep(max(0, (await group_cfg(cid))["delay"]) + random.uniform(0, 2))
    async with lock(cid):
        cfg = await group_cfg(cid, fresh=True)
        if cfg["mode"] != "b" or not cfg["talk"]:
            return
        if not turns_ok(cfg, CH.get(k, 0)) or not day_ok(cfg, cid):
            return
        try:
            await APP.bot.send_chat_action(cid, "typing")
        except Exception:
            pass
        j = await _compose(cid, "peer", hazil_instruction())
        ans = _clean(j.get("answer"))
        if j.get("reply") is False or not ans:
            return
        from telegram import ReplyParameters
        sent = await APP.bot.send_message(
            cid, ans, reply_parameters=ReplyParameters(
                message_id=peer_msg_id, allow_sending_without_reply=True))
        await asyncio.to_thread(save_msg, cid, "model", ans)
        bump_day(cid)
        after_reply(cid, chain, owner, sent.message_id, ans)


# ---------- umumiy faktlar (/ortoq_fakt) ----------
ORTOQ_TAG = "[muhim] Ortoq: "


def add_shared_fact(owner_cid, text):
    """Faktni egasi lichkasiga va barcha ruxsat etilgan guruhlarga yozadi (takrorsiz)."""
    fact = ORTOQ_TAG + text
    saved = 0
    for cid in {int(owner_cid), *ALLOWED_CHATS}:
        if any(x.get("fact") == fact for x in list_facts(cid)):
            continue
        save_fact(cid, fact)
        saved += 1
    return saved


def push_fact(text, owner):
    send_bg({"type": "fact", "owner": str(owner), "text": text})


def _apply_peer_fact(p):
    try:
        owner = int(p.get("owner") or 0)
    except (TypeError, ValueError):
        return
    if owner not in ALLOWED:
        return
    text = re.sub(r"\s+", " ", str(p.get("text") or "")).strip()[:300]
    if text:
        add_shared_fact(owner, text)


# ---------- takror va javob tartibi ----------
def repeat_block(history):
    """Botning oxirgi javoblarini ko'rsatadi, takrorlamaslik uchun."""
    lines = [h.get("content") or "" for h in history
             if h.get("role") == "model" and h.get("content")][-4:]
    if not lines:
        return ""
    shown = "\n".join("- " + " ".join(x.split())[:80] for x in lines)
    return ("\n\nOxirgi javoblaring (bularni takrorlama: boshqa ibora, boshqa "
            "tuzilma; har doim savol bilan tugatma):\n" + shown)


def mark_answered(cid, owner_mid):
    box = STATE.setdefault("answered", {})
    if len(box) > 500:
        box.clear()
    box[(int(cid), int(owner_mid))] = time.time()


def peer_answered(cid, owner_mid):
    return (int(cid), int(owner_mid)) in STATE.get("answered", {})


# ---------- sizsiz gaplashuv ----------
async def auto_tick(app, cid, row, now):
    """loops.py dan chaqiriladi (guruh chatlari uchun)."""
    if cid not in ALLOWED_CHATS or not PEER_URL:
        return
    cfg = await group_cfg(cid)
    if cfg["mode"] != "b" or not cfg["auto"]:
        return
    if not ((row.get("pro_from") or 8) <= now.hour < (row.get("pro_to") or 23)):
        return
    last = STATE.setdefault("auto_last", {}).get(cid, 0)
    if time.time() - last < cfg["every"] * 60 or not day_ok(cfg, cid):
        return
    if random.random() > 0.5:   # ikkala bot ham tekshiradi, bittasi boshlasin
        return
    STATE["auto_last"][cid] = time.time()
    chain = f"auto{int(time.time())}"
    async with lock(cid):
        j = await _compose(
            cid, "auto",
            "(Guruhga o'zing, egasiga yoki do'stingga qaratib, yangi qisqa "
            "gap yoki savol tashla, 1-2 gap. Oldingi gapni takrorlama.)")
        ans = _clean(j.get("answer"))
        if not ans:
            return
        sent = await app.bot.send_message(cid, ans)
        await asyncio.to_thread(save_msg, cid, "model", ans)
        bump_day(cid)
        after_reply(cid, chain, "", sent.message_id, ans)
