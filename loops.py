"""FON ISHLARI: eslatma sikli va botning o'zi birinchi yozishi (salomlar).
"""
import asyncio, random
from datetime import datetime, timedelta
from google.genai import types
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from ai import gen
from character import NAME, BASE, SLOT_PROMPTS, ANGLES
from config import (TZ, STATE, REPEATS, CHAT_MODELS,
                    JIMLIK_HOURS, UNANSWERED_RETRY_H, JIMLIK_START, JIMLIK_END,
                    PROACTIVE_HOURS, PROACTIVE_PER_DAY,
                    PROACTIVE_GAP)
from database import (get_recent, list_facts, get_history, get_settings,
                      last_user_time,
                      get_summary, save_msg, cleanup_db, proactive_chats,
                      set_slot, due_reminders, advance, mark_done)
from utils import (KUNOXI_TAG, style_text, mood_text, time_text, order_facts,
                   today_state, get_pack, parse_odat, today_mood,
                   intimacy_text, get_odat_mode, habit_rule)
from images import find_photos
from relay import auto_tick
from ai import gen, SAFETY
from config import FALLBACKS
from database import messages_between, save_fact, del_fact, count_user_messages
from database import BOT_OPEN_TAG
from google.genai import types
from datetime import timezone, timedelta

def event_context(rows, kind):
    today = datetime.now(TZ).date()
    tod, tom = [], []
    for x in rows:
        u = x.get("expires_at")
        if not u:
            continue
        try:
            d = (datetime.fromisoformat(u.replace("Z", "+00:00"))
                 .date() - timedelta(days=1))
        except Exception:
            continue
        if d == today:
            tod.append(x["fact"])
        elif d == today + timedelta(days=1):
            tom.append(x["fact"])
    parts = []
    if kind == "ertalab" and tod:
        parts.append("Bugun bo'ladigan voqealar: "
                     + "; ".join(tod)
                     + ". Omad tila yoki tayyorgarlikni so'ra.")
    if kind == "kechqurun":
        if tod:
            parts.append("Bugun bo'lgan voqealar: "
                         + "; ".join(tod)
                         + ". Qanday o'tganini so'ra.")
        if tom:
            parts.append("Ertaga bo'ladigan voqealar: "
                         + "; ".join(tom)
                         + ". Tayyorgarlik haqida iliq so'ra "
                         "yoki omad tila.")
    return " ".join(parts)

def period_of(h):
    if h < 11:
        return "ertalab, uyg'ongan bo'lishing mumkin"
    if h < 18:
        return "kunduzi, ishda yoki yo'lda bo'lishing mumkin"
    if h < 23:
        return "kechqurun, biroz charchagan bo'lishing mumkin"
    return "tun, uyqusiraysan"

def day_plan(cid, day, cfg=None):
    cfg = cfg or {}
    """Chat va kun uchun tasodifiy vaqtlar (daqiqada), har safar bir xil."""
    rnd = random.Random(f"plan-{cid}-{day}")
    lo = cfg.get("pro_from") or PROACTIVE_HOURS[0]
    hi = cfg.get("pro_to") or PROACTIVE_HOURS[1]
    mn = cfg.get("pro_min") or PROACTIVE_PER_DAY[0]
    mx = max(mn, cfg.get("pro_max") or PROACTIVE_PER_DAY[1])
    gap = cfg.get("pro_gap") or PROACTIVE_GAP
    n = rnd.randint(mn, mx)
    times = []
    for _ in range(300):
        if len(times) >= n:
            break
        m = rnd.randint(lo * 60, hi * 60 - 1)
        if all(abs(m - t) >= gap for t in times):
            times.append(m)
    return sorted(times)

async def kun_oxiri(app, cid):
    """Kechqurun, bugun kamida 4 ta xabar bo'lsa, bir marta qisqa kun oxiri xabari."""
    if cid < 0:
        return  # guruhda kun oxiri xabari yo'q
    now = datetime.now(TZ)
    day = now.strftime("%Y-%m-%d")
    rows = await asyncio.to_thread(list_facts, cid)
    if any(x["fact"].startswith(KUNOXI_TAG + day) for x in rows):
        return
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    msgs = await asyncio.to_thread(
        messages_between, cid,
        start.astimezone(timezone.utc).isoformat(),
        now.astimezone(timezone.utc).isoformat())
    if sum(1 for m in msgs if m["role"] == "user") < 4:
        return
    await asyncio.to_thread(save_fact, cid, KUNOXI_TAG + day + "] done")
    convo = "\n".join(f"{m['role']}: {m['content']}" for m in msgs[-60:])[:6000]
    prompt = ("Quyida bugungi suhbat. Sen " + NAME + ": iliq va samimiy. Bugungi suhbatni "
              "eslab, 2-3 gapli qisqa kun oxiri xabari yoz (o'zbekcha): bugun nima "
              "haqida gaplashdik va ertaga uchun yengil, bosimsiz bir so'z. "
              "Ro'yxat, sarlavha yo'q. Faqat matn.\n\n" + convo)
    try:
        r = await gen(models=FALLBACKS, contents=[types.Content(
            role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(
                temperature=0.8, safety_settings=SAFETY))
        text = (r.text or "").strip()[:400]
    except Exception as e:
        print("KUNOXI xato:", repr(e))
        return
    if not text:
        return
    try:
        await app.bot.send_chat_action(cid, "typing")
    except Exception:
        pass
    await asyncio.sleep(2)
    await app.bot.send_message(cid, text)
    await asyncio.to_thread(save_msg, cid, "model", text)

def pick_habit(cid, frows):
    """Kunda ko'pi bilan bitta odat (ixtiyoriy). Bot o'zi va siz qo'shgan odatlar."""
    from character import HABITS
    if get_odat_mode(frows) == "yoq":
        return None
    day = datetime.now(TZ).strftime("%Y-%m-%d")
    rnd = random.Random(f"habit-{cid}-{day}")
    if rnd.random() > 0.4:
        return None
    pool = [{"text": h, "emoji": "", "query": ""} for h in HABITS]
    for x in frows:
        if x["fact"].startswith("[odat] "):
            e, t, q = parse_odat(x["fact"])
            if t:
                pool.append({"text": t, "emoji": e, "query": q})
    return rnd.choice(pool)

async def ensure_digest(cid, frows):
    """Kechagi suhbatning qisqa mavzusi; bir kunda bir marta yaratiladi."""
    from utils import KECHA_TAG
    now = datetime.now(TZ)
    yday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    tag = KECHA_TAG + yday + "] "
    for x in frows:
        if x["fact"].startswith(tag):
            return x["fact"][len(tag):]
    start = datetime.strptime(yday, "%Y-%m-%d").replace(tzinfo=TZ)
    end = start + timedelta(days=1)
    rows = await asyncio.to_thread(
        messages_between, cid,
        start.astimezone(timezone.utc).isoformat(),
        end.astimezone(timezone.utc).isoformat())
    if len(rows) < 4:
        return None
    convo = "\n".join(f"{r['role']}: {r['content']}" for r in rows[-60:])[:6000]
    prompt = ("Quyida kechagi suhbat. Asosiy mavzuni bir-ikki gapda, o'zbekcha yoz. "
              "Faqat matn.\n\n" + convo)
    try:
        r = await gen(models=FALLBACKS, contents=[types.Content(
            role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(
                temperature=0.3, safety_settings=SAFETY))
        text = (r.text or "").strip()[:200]
    except Exception as e:
        print("KECHA xato:", e)
        return None
    if not text:
        return None
    for x in frows:
        if x["fact"].startswith(KECHA_TAG):
            await asyncio.to_thread(del_fact, cid, x["id"])
    await asyncio.to_thread(save_fact, cid, tag + text)
    return text

def _alive(x):
    """Ochiq ish hali muddati o'tmagan bo'lsa True."""
    from datetime import datetime as _dt, timezone as _tz
    e = x.get("expires_at")
    if not e:
        return True
    try:
        return _dt.fromisoformat(str(e).replace("Z", "+00:00")) > _dt.now(_tz.utc)
    except Exception:
        return True


def unanswered_old_enough(msg):
    """Oxirgi bot xabaridan UNANSWERED_RETRY_H soat o'tdimi."""
    if not UNANSWERED_RETRY_H:
        return False
    try:
        t = datetime.fromisoformat(
            str(msg.get("created_at")).replace("Z", "+00:00"))
    except Exception:
        return False
    return (datetime.now(timezone.utc) - t >=
            timedelta(hours=UNANSWERED_RETRY_H))


async def greet(app, cid, kind, prompt_kind=None):
    if cid < 0:
        return  # guruhda o'zi yozmaydi
    recent = await asyncio.to_thread(get_recent, cid, 3)
    frows = await asyncio.to_thread(list_facts, cid)
    ev = event_context(frows, kind)
    # oxirgi ketma-ket bot xabarlari soni (3 gacha sanaladi)
    tail = 0
    for m in reversed(recent):
        if m["role"] != "model":
            break
        tail += 1
    unanswered = tail >= 2
    followup = False
    if unanswered and not ev:
        # Javob yo'q. Faqat 2 ta yozilgan bo'lsa va oxirgisidan
        # UNANSWERED_RETRY_H soat o'tgan bo'lsa, BIR marta qo'shimcha eslatadi.
        if tail == 2 and unanswered_old_enough(recent[-1]):
            followup = True
        else:
            print("SALOM o'tkazib yuborildi: javob yo'q", cid)
            return
    if not ev and random.random() < 0.1:
        print("SALOM tasodifan o'tkazildi", cid)
        return
    history = await asyncio.to_thread(get_history, cid)
    facts = [x["fact"] for x in order_facts(frows)]
    st = await asyncio.to_thread(get_settings, cid)
    system = (BASE + "\n\nHozirgi Toshkent vaqti: "
              + time_text())
    system += style_text(st)
    kecha = await ensure_digest(cid, frows) if kind == "ertalab" else None
    if kecha and random.random() < 0.5:
        system += ("\n\nKecha suhbatimiz: " + kecha
                   + ". Shu haqida tabiiy so'rashing mumkin, bosimsiz.")
    system += intimacy_text(await asyncio.to_thread(count_user_messages, cid))
    system += mood_text(cid, today_mood(frows))
    picked = pick_habit(cid, frows)
    if picked:
        system += ("\n\nOdat (ixtiyoriy, faqat tabiiy bo'lsa): " + picked["text"]
                   + habit_rule(get_odat_mode(frows)))
    if facts:
        system += ("\n\nFoydalanuvchi haqida bilganlaring ([muhim] eng muhim, doim e'tiborda; sog'liq va moliya haqidagilarni faqat o'zi so'ralganda ishlat):\n- "
                   + "\n- ".join(facts))
    st_now = today_state(frows)
    if st_now:
        system += ("\n\nBugungi holat (foydalanuvchi aytgan): " + st_now
                   + ". Shuni hisobga ol, lekin eslatib o'tirma.")
    summ = await asyncio.to_thread(get_summary, cid)
    if summ:
        system += ("\n\nOldingi suhbatlar xulosasi (faqat "
                   "kontekst uchun):\n" + summ)
    hist = "\n".join(f'{h["role"]}: {h["content"]}'
                     for h in history[-8:])
    prompt = SLOT_PROMPTS[prompt_kind or kind]
    opens = [x["fact"] for x in frows
             if "Ochiq ish" in x["fact"]]
    # Bot ochiq ishlari: navbat bilan (eng eskisi), bir marta, muddati o'tmaganlari
    nudged = None
    bot_open = [x for x in frows
                if x["fact"].startswith(BOT_OPEN_TAG) and _alive(x)]
    if bot_open and not ev:
        nudged = bot_open[0]
        prompt += ("\n\nOchiq ish: " + nudged["fact"][len(BOT_OPEN_TAG):]
                   + ". Shu haqida tabiiy so'ra, bir marta, bosim qilmasdan.")
    elif opens and not ev and random.random() < 0.5:
        prompt += ("\n\nOchiq ish: " + random.choice(opens)
                   + ". Shu haqida tabiiy so'ra (natijasi qanday bo'ldi), bir marta, bosim qilmasdan.")
    elif ev:
        prompt += "\n\nMUHIM: " + ev
    else:
        prompt += "\n\nBu safar: " + random.choice(ANGLES) + "."
    if followup:
        prompt += ("\n\nFoydalanuvchi bir kundan beri javob bermadi. Bu "
                   "yengil, bosimsiz bitta eslatma: qisqa yoz, aybdor qilma, "
                   "savol bilan tugatma shart emas.")
    prompt += ("\n\nOldingi xabarlaringdagi gaplarni "
               "takrorlama.\n\nOxirgi suhbat:\n" + hist)
    r = await gen(
        models=CHAT_MODELS, contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system, temperature=1.0))
    text = (r.text or "").strip()
    if text:
        try:
            await app.bot.send_chat_action(cid, "typing")
        except Exception:
            pass
        await asyncio.sleep(min(3, 1 + len(text) / 120))
        await app.bot.send_message(cid, text)
        await asyncio.to_thread(save_msg, cid, "model", text)
        if nudged is not None:
            # eslatildi: qayta eslatilmasin
            await asyncio.to_thread(del_fact, cid, nudged["id"])
        if picked:
            try:
                if picked["emoji"]:
                    pack = await get_pack(app.bot, st)
                    lst = pack.get(picked["emoji"]) or []
                    if lst:
                        await app.bot.send_sticker(cid, random.choice(lst))
                if picked["query"]:
                    got = await find_photos(picked["query"], 1)
                    if got:
                        await app.bot.send_photo(cid, got[0][0])
            except Exception as e:
                print("ODAT media xato:", e)

async def proactive_loop(app):
    while True:
        try:
            now = datetime.now(TZ)
            day = now.strftime("%Y-%m-%d")
            if STATE.get("clean") != day:
                STATE["clean"] = day
                STATE["offs"] = {}
                try:
                    await asyncio.to_thread(cleanup_db)
                except Exception as e:
                    print("TOZALASH xato:", e)
            rows = await asyncio.to_thread(proactive_chats)
            for row in rows:
                cid = row["chat_id"]
                if cid < 0:
                    # guruhda tasodifiy salom, jimlik, kun oxiri yo'q;
                    # faqat B rejimda sozlangan mustaqil gaplashuv
                    try:
                        await auto_tick(app, cid, row, now)
                    except Exception as e:
                        print("AVTO xato:", repr(e))
                    continue
                last = row.get("last_slot")
                try:
                    last_dt = datetime.fromisoformat(last) if last else None
                except Exception:
                    last_dt = None
                # 1) Rejalashtirilgan vaqtlar
                for m in day_plan(cid, day, row):
                    t = now.replace(hour=m // 60, minute=m % 60,
                                    second=0, microsecond=0)
                    if t > now:
                        break
                    if now - t > timedelta(minutes=30):
                        continue  # eskirgan (server qayta ishga tushgan)
                    if last_dt and last_dt >= t:
                        continue  # bu vaqt allaqachon bajarilgan
                    await asyncio.to_thread(set_slot, cid, now.isoformat())
                    h = t.hour
                    kind = "ertalab" if h < 11 else (
                        "tushlik" if h < 18 else "kechqurun")
                    pk = kind if (kind != "tushlik" or
                                  random.random() < 0.3) else "tasodifiy"
                    if kind != "tushlik" and random.random() < 0.5:
                        pk = "tasodifiy"
                    try:
                        await greet(app, cid, kind, pk)
                    except Exception as e:
                        print("SALOM xato:", e)
                    break  # bir loop aylanishida bitta xabar
                # 2) Uzoq jimlik: user 8 soat yozmasa va bot ham 8 soatdan beri yozmagan bo'lsa
                if 21 <= now.hour < 23 and random.random() < 0.5:
                    try:
                        await kun_oxiri(app, cid)
                    except Exception as e:
                        print("KUNOXI xato:", repr(e))
                if not (JIMLIK_START <= now.hour < JIMLIK_END):
                    continue
                jh = row.get("jimlik_h") or JIMLIK_HOURS
                user_last = await asyncio.to_thread(last_user_time, cid)
                if not user_last or now - user_last < timedelta(hours=jh):
                    continue
                if last_dt and now - last_dt < timedelta(hours=jh):
                    continue
                if random.random() < 0.5:
                    continue
                await asyncio.to_thread(set_slot, cid, now.isoformat())
                try:
                    await greet(app, cid, "jimlik")
                except Exception as e:
                    print("JIMLIK xato:", e)
        except Exception as e:
            print("PROAKTIV xato:", e)
        await asyncio.sleep(300)

REM_TRIES = {}          # {eslatma id: urinishlar soni} (xotirada)
REM_MAX_TRIES = 20      # ~10 daqiqa (sikl 30 s); undan keyin voz kechiladi

def _rem_permanent(e):
    """Qayta urinish foydasiz xatolar: bot bloklangan, chat topilmadi."""
    return type(e).__name__ in ("Forbidden", "BadRequest", "ChatMigrated")

async def reminder_loop(app):
    while True:
        try:
            rows = await asyncio.to_thread(due_reminders)
            for x in rows:
                kb = InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "⏰ 10 daq", callback_data=f"snz:{x['id']}:10"),
                    InlineKeyboardButton(
                        "⏰ 1 soat", callback_data=f"snz:{x['id']}:60")],
                    [InlineKeyboardButton(
                        "✅ Bajarildi", callback_data=f"ok:{x['id']}")]])
                sent = False
                try:
                    await app.bot.send_message(
                        x["chat_id"], "⏰ Eslatma: " + x["task"],
                        reply_markup=kb)
                    sent = True
                except Exception as e:
                    n = REM_TRIES.get(x["id"], 0) + 1
                    REM_TRIES[x["id"]] = n
                    print("Yuborish xato:", x["id"], n, e)
                    if _rem_permanent(e) or n >= REM_MAX_TRIES:
                        print("Eslatma tashlandi:", x["id"], e)
                        sent = True   # qayta urinish foydasiz
                if not sent:
                    continue          # belgilanmaydi, keyingi siklda qayta
                REM_TRIES.pop(x["id"], None)
                if x.get("repeat") in REPEATS:
                    await asyncio.to_thread(
                        advance, x["id"], x["remind_at"], x["repeat"])
                else:
                    await asyncio.to_thread(mark_done, x["id"])
        except Exception as e:
            print("SIKL xato:", e)
        await asyncio.sleep(30)

async def start_loop(app):
    app.bot_data["t1"] = asyncio.create_task(reminder_loop(app))
    app.bot_data["t2"] = asyncio.create_task(proactive_loop(app))
