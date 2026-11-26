"""BUYRUQLAR (/unut, /xotira, /uslub, /ovoz, /stiker_... va boshqalar).
"""
import asyncio
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import (TZ, REPEATS, STYLES, VOICE, VOICES, RATES, VMODES,
                    ENGINES, GVOICES, STATE)
from database import (wipe, pending, del_rem, set_proactive, list_facts,
                      del_fact, save_fact, get_summary, get_settings,
                      update_setting)
from character import NAME
from memory import update_facts
from utils import mark, tier_of, today_state, STATE_TAG
from voice import tts, tts_gemini

async def forget(update, ctx):
    await asyncio.to_thread(wipe, update.message.chat_id)
    await update.message.reply_text("Xotira tozalandi.")

async def list_rem(update, ctx):
    rows = await asyncio.to_thread(pending, update.message.chat_id)
    if not rows:
        await update.message.reply_text("Eslatma yo'q.")
        return
    lines = []
    for x in rows:
        t = datetime.fromisoformat(
            x["remind_at"].replace("Z", "+00:00")).astimezone(TZ)
        tag = (f' 🔁 {REPEATS[x["repeat"]]}'
               if x.get("repeat") in REPEATS else "")
        lines.append(f'{x["id"]}. {x["task"]} — '
                     f'{t.strftime("%d.%m %H:%M")}{tag}')
    await update.message.reply_text(
        "\n".join(lines) + "\n\nBekor qilish: /bekor <raqam>")

async def cancel(update, ctx):
    try:
        rid = int(ctx.args[0])
    except Exception:
        await update.message.reply_text("Masalan: /bekor 3")
        return
    await asyncio.to_thread(del_rem, update.message.chat_id, rid)
    await update.message.reply_text("Bekor qilindi.")

async def msg_on(update, ctx):
    await asyncio.to_thread(
        set_proactive, update.message.chat_id, True)
    await update.message.reply_text(
        "Yaxshi, ba'zan o'zim yozib turaman.")

async def msg_off(update, ctx):
    await asyncio.to_thread(
        set_proactive, update.message.chat_id, False)
    await update.message.reply_text(
        "Xo'p, endi o'zim yozmayman. Qaytarish: /xabar_bor")

async def my_id(update, ctx):
    m = update.message
    text = f"Sizning ID: {update.effective_user.id}"
    if m.chat.type != "private":
        text += f"\nChat ID: {m.chat_id}"
    await m.reply_text(text)

def _fact_tail(x):
    if x.get("expires_at"):
        d = datetime.fromisoformat(
            x["expires_at"].replace("Z", "+00:00"))
        return f" (gacha: {d.astimezone(TZ).strftime('%d.%m')})"
    return ""

def _tier_of_row(fact):
    if fact.startswith("[odat]"):
        return "odat"
    if fact.startswith(("[botkayf ", "[kecha ", "[kunoxi ", "[odatrejim] ", "[odatkun ")):
        return "boshqa"
    return "holat" if fact.startswith(STATE_TAG) else tier_of(fact)

async def _tier_reply(update, want, title, empty):
    rows = await asyncio.to_thread(
        list_facts, update.message.chat_id)
    lines = []
    # Raqamlar umumiy ro'yxatdagidek qoladi, shunda /fakt_ochir to'g'ri ishlaydi
    for i, x in enumerate(rows, 1):
        if _tier_of_row(x["fact"]) == want:
            lines.append(f'{i}. {x["fact"]}{_fact_tail(x)}')
    if not lines:
        await update.message.reply_text(empty)
        return
    await update.message.reply_text(
        title + "\n" + "\n".join(lines) + "\n\n"
        "O'chirish: /fakt_ochir 2, 5")

async def memory_cmd(update, ctx):
    rows = await asyncio.to_thread(
        list_facts, update.message.chat_id)
    if not rows:
        await update.message.reply_text(
            "Hozircha siz haqingizda hech narsa saqlanmagan.")
        return
    cnt = {"muhim": 0, "oddiy": 0, "holat": 0}
    for x in rows:
        t = _tier_of_row(x["fact"])
        if t in cnt:
            cnt[t] += 1
    now_state = today_state(rows)
    holat = now_state if now_state else "aytilmagan"
    await update.message.reply_text(
        "Xotira bo'limlari:\n\n"
        f"🔒 Muhim: {cnt['muhim']} ta (ism, oila, muhim sanalar)\n"
        f"📝 Oddiy: {cnt['oddiy']} ta (hobbi, odat, loyiha)\n"
        f"💭 Bugungi holat: {holat}\n\n"
        "Ko'rish: /xotira_muhim, /xotira_oddiy, /xotira_holat\n"
        "Qo'shish: /eslab_qol <matn>")

async def memory_muhim(update, ctx):
    await _tier_reply(update, "muhim", "🔒 Muhim:",
                      "Muhim fakt yo'q.")

async def memory_oddiy(update, ctx):
    await _tier_reply(update, "oddiy", "📝 Oddiy:",
                      "Oddiy fakt yo'q.")

async def memory_holat(update, ctx):
    rows = await asyncio.to_thread(
        list_facts, update.message.chat_id)
    st_now = today_state(rows)
    if st_now:
        await update.message.reply_text(
            f"💭 Bugungi holat: {st_now}\n\n"
            "Yangisini aytsangiz, shu almashadi.")
    else:
        await update.message.reply_text(
            "Bugun kayfiyat yoki holat aytilmagan.")

async def fact_del(update, ctx):
    cid = update.message.chat_id
    raw = " ".join(ctx.args).replace(",", " ")
    nums = [int(x) for x in raw.split() if x.isdigit()]
    if not nums:
        await update.message.reply_text(
            "Masalan: /fakt_ochir 2, 5, 7")
        return
    rows = await asyncio.to_thread(list_facts, cid)
    ids = [rows[n - 1]["id"] for n in dict.fromkeys(nums)
           if 1 <= n <= len(rows)]
    if not ids:
        await update.message.reply_text(
            "Bunday raqam yo'q. Ro'yxat: /xotira")
        return
    for fid in ids:
        await asyncio.to_thread(del_fact, cid, fid)
    await update.message.reply_text(
        f"O'chirildi: {len(ids)} ta. Yangi ro'yxat: /xotira")

async def fact_add(update, ctx):
    text = " ".join(ctx.args).strip()
    if not text:
        await update.message.reply_text(
            "Masalan: /eslab_qol Tug'ilgan kunim 5-may")
        return
    await asyncio.to_thread(
        save_fact, update.message.chat_id, text[:300])
    await update.message.reply_text("Eslab qoldim.")

async def summary_cmd(update, ctx):
    s_ = await asyncio.to_thread(
        get_summary, update.message.chat_id)
    await update.message.reply_text(
        s_ or "Xulosa hali yo'q (30 xabardan keyin paydo bo'ladi).")

async def refresh_cmd(update, ctx):
    cid = update.message.chat_id
    try:
        await update_facts(cid)
        await update.message.reply_text(
            "Xotira yangilandi. Ko'rish: /xotira")
    except Exception as e:
        print("YANGILA xato:", e)
        await update.message.reply_text(
            "Hozir yangilab bo'lmadi, keyinroq urinib ko'ring.")

async def style_cmd(update, ctx):
    st = await asyncio.to_thread(
        get_settings, update.message.chat_id)
    cur = st.get("style") or "muloyim"
    rows = [[InlineKeyboardButton(
        mark(cur, k, v[0]), callback_data=f"set:style:{k}")]
        for k, v in STYLES.items()]
    await update.message.reply_text(
        "Qaysi uslubda gaplashay? Asosiy xarakterim (muloyim, "
        "g'amxo'r) o'zgarmaydi, faqat ohang almashadi.",
        reply_markup=InlineKeyboardMarkup(rows))

async def voice_cmd(update, ctx):
    st = await asyncio.to_thread(
        get_settings, update.message.chat_id)
    ce = st.get("engine") or "gemini"
    cg = st.get("gvoice") or "Sulafat"
    cv = st.get("voice") or VOICE
    cr = st.get("rate") or "+0%"
    cm = st.get("vmode") or "auto"
    def row(items, cur, key):
        return [InlineKeyboardButton(
            mark(cur, k, v), callback_data=f"set:{key}:{k}")
            for k, v in items]
    g = list(GVOICES.items())
    rows = [
        row(ENGINES.items(), ce, "engine"),
        row(g[:2], cg, "gvoice"),
        row(g[2:], cg, "gvoice"),
        row(VOICES.items(), cv, "voice"),
        row(RATES.items(), cr, "rate"),
        row(VMODES.items(), cm, "vmode"),
    ]
    await update.message.reply_text(
        "Ovoz sozlamalari:\n"
        "1-qator: ovoz turi (Insoniy = Gemini)\n"
        "2-3-qator: Gemini ovozlari\n"
        "4-qator: oddiy (Edge) ovoz\n"
        "5-qator: tezlik, 6-qator: qachon ovozli.\n"
        "Solishtirish: /ovoz_test",
        reply_markup=InlineKeyboardMarkup(rows))

async def sticker_pack_cmd(update, ctx):
    cid = update.message.chat_id
    arg = " ".join(ctx.args).strip().rstrip("/")
    if not arg:
        await update.message.reply_text(
            "Menga bironta stiker yuboring, uning paketini "
            "o'zim eslab qolaman. Yoki: /stiker_paket <nom "
            "yoki t.me/addstickers/... havolasi>")
        return
    name = arg.split("/")[-1]
    try:
        await ctx.bot.get_sticker_set(name)
    except Exception:
        await update.message.reply_text(
            "Bunday stiker paketi topilmadi.")
        return
    await asyncio.to_thread(update_setting, cid, "sticker_set", name)
    await asyncio.to_thread(update_setting, cid, "stickers", True)
    STATE.get("packs", {}).pop(name, None)
    await update.message.reply_text(
        "Paket saqlandi, endi suhbatda stikerlardan "
        "foydalanaman 🎴")

async def sticker_off(update, ctx):
    await asyncio.to_thread(
        update_setting, update.message.chat_id, "stickers", False)
    await update.message.reply_text(
        "Stiker yubormayman. Qaytarish: /stiker_bor")

async def sticker_on(update, ctx):
    await asyncio.to_thread(
        update_setting, update.message.chat_id, "stickers", True)
    await update.message.reply_text("Stikerlar yoqildi 🎴")

async def voice_test(update, ctx):
    cid = update.message.chat_id
    st = await asyncio.to_thread(get_settings, cid)
    text = (" ".join(ctx.args).strip() or
            "Salom, kuningiz qanday o'tdi? Charchagan bo'lsangiz, "
            "biroz dam oling, men shu yerdaman.")
    await update.message.reply_text("1) Oddiy (Edge) ovoz:")
    try:
        await update.message.reply_voice(await tts(
            text, st.get("voice"), st.get("rate")))
    except Exception as e:
        await update.message.reply_text(f"Edge xato: {str(e)[:150]}")
    await update.message.reply_text("2) Insoniy (Gemini) ovoz:")
    try:
        await update.message.reply_voice(await tts_gemini(text, st))
    except Exception as e:
        print("GEMINI TTS test xato:", e)
        await update.message.reply_text(
            f"Gemini ovozi chiqmadi: {str(e)[:200]}")


def _ints(ctx, n):
    try:
        vals = [int(a) for a in ctx.args[:n]]
    except ValueError:
        return None
    return vals if len(vals) == n else None

async def yozish_cmd(update, ctx):
    from database import update_setting
    v = _ints(ctx, 2)
    if not v or not (1 <= v[0] <= v[1] <= 10):
        await update.message.reply_text(
            "Masalan: /yozish 3 5 (kuniga kamida 3, ko'pi bilan 5 marta)")
        return
    cid = update.message.chat_id
    await asyncio.to_thread(update_setting, cid, "pro_min", v[0])
    await asyncio.to_thread(update_setting, cid, "pro_max", v[1])
    await update.message.reply_text(
        f"Endi kuniga {v[0]}–{v[1]} marta o'zim yozaman.")

async def oraliq_cmd(update, ctx):
    from database import update_setting
    v = _ints(ctx, 1)
    if not v or not (30 <= v[0] <= 600):
        await update.message.reply_text(
            "Masalan: /yozish_oraliq 75 (ikki xabar orasi, 30 dan 600 daqiqagacha)")
        return
    await asyncio.to_thread(update_setting, update.message.chat_id, "pro_gap", v[0])
    await update.message.reply_text(
        f"Xabarlar orasida kamida {v[0]} daqiqa bo'ladi.")

async def saat_cmd(update, ctx):
    from database import update_setting
    v = _ints(ctx, 2)
    if not v or not (0 <= v[0] < v[1] <= 23):
        await update.message.reply_text(
            "Masalan: /yozish_saat 8 23 (soat oralig'i, 0 dan 23 gacha)")
        return
    cid = update.message.chat_id
    await asyncio.to_thread(update_setting, cid, "pro_from", v[0])
    await asyncio.to_thread(update_setting, cid, "pro_to", v[1])
    await update.message.reply_text(
        f"Endi {v[0]}:00 dan {v[1]}:00 gacha yozaman.")

async def jimlik_cmd(update, ctx):
    from database import update_setting
    v = _ints(ctx, 1)
    if not v or not (1 <= v[0] <= 72):
        await update.message.reply_text(
            "Masalan: /jimlik 8 (siz necha soat yozmasangiz, o'zim yozaman)")
        return
    await asyncio.to_thread(update_setting, update.message.chat_id, "jimlik_h", v[0])
    await update.message.reply_text(
        f"Siz {v[0]} soat yozmasangiz, o'zim yozaman.")

async def yozish_holat(update, ctx):
    from database import get_settings
    st = await asyncio.to_thread(get_settings, update.message.chat_id)
    mn = st.get("pro_min") or 3
    mx = st.get("pro_max") or 5
    try:
        from loops import day_plan
        from config import TZ
        from datetime import datetime
        day = datetime.now(TZ).strftime("%Y-%m-%d")
        pl = day_plan(update.message.chat_id, day, st)
        plan_text = ", ".join(f"{m // 60:02d}:{m % 60:02d}" for m in pl) or "yo'q"
    except Exception:
        plan_text = "ko'rsatib bo'lmadi"
    await update.message.reply_text(
        "O'zim yozish sozlamalari:\n"
        f"• Kuniga: {mn}–{mx} marta\n"
        f"• Orasi: kamida {st.get('pro_gap') or 75} daqiqa\n"
        f"• Soatlar: {st.get('pro_from') or 8}:00–{st.get('pro_to') or 23}:00\n"
        f"• Jimlik: {st.get('jimlik_h') or 8} soat\n"
        f"• Bugungi reja: {plan_text}\n\n"
        "O'zgartirish: /yozish, /yozish_oraliq, /yozish_saat, /jimlik")

async def odat_qosh(update, ctx):
    from database import save_fact, list_facts
    cid = update.message.chat_id
    raw = " ".join(ctx.args).strip()
    if not raw:
        await update.message.reply_text(
            "Masalan: /odat_qosh ☕ Ertalab kofe ichaman | coffee cup morning\n"
            "(| dan keyin rasm qidiruvi, ixtiyoriy)")
        return
    parts = raw.split(" ", 1)
    emoji, body = "", raw
    if len(parts) == 2 and not any(c.isascii() and c.isalnum() for c in parts[0]):
        emoji, body = parts[0], parts[1]
    bits = [b.strip() for b in body.split("|")]
    text = bits[0][:150]
    query = bits[1][:60] if len(bits) > 1 else ""
    if not text:
        await update.message.reply_text("Odat matnini yozing.")
        return
    rows = await asyncio.to_thread(list_facts, cid)
    if sum(1 for x in rows if x["fact"].startswith("[odat]")) >= 10:
        await update.message.reply_text(
            "Ko'pi bilan 10 ta odat bo'ladi. Avval /odat_ochir bilan birini o'chiring.")
        return
    await asyncio.to_thread(save_fact, cid, f"[odat] {emoji}|{text}|{query}")
    extra = f" (rasm: {query})" if query else ""
    await update.message.reply_text(f"Odat qo'shildi: {emoji} {text}{extra}".strip())

async def _my_odatlar(cid):
    from database import list_facts
    rows = await asyncio.to_thread(list_facts, cid)
    return [x for x in rows if x["fact"].startswith("[odat]")]

async def odatlar(update, ctx):
    from utils import parse_odat
    od = await _my_odatlar(update.message.chat_id)
    if not od:
        await update.message.reply_text(
            "Hali o'zingiz qo'shgan odat yo'q. /odat_qosh bilan qo'shing.")
        return
    lines = []
    for i, x in enumerate(od, 1):
        e, t, q = parse_odat(x["fact"])
        extra = f" (rasm: {q})" if q else ""
        lines.append(f"{i}. {e} {t}{extra}".strip())
    await update.message.reply_text(
        "Sizning odatlaringiz:\n" + "\n".join(lines)
        + "\n\nO'chirish: /odat_ochir 2")

async def odat_ochir(update, ctx):
    from database import del_fact
    cid = update.message.chat_id
    v = _ints(ctx, 1)
    od = await _my_odatlar(cid)
    if not v or not (1 <= v[0] <= len(od)):
        await update.message.reply_text(
            "Raqamini yozing, masalan: /odat_ochir 2 (ro'yxat: /odatlar)")
        return
    await asyncio.to_thread(del_fact, cid, od[v[0] - 1]["id"])
    await update.message.reply_text("Odat o'chirildi.")


async def kayfiyat_cmd(update, ctx):
    from database import list_facts
    from utils import auto_mood, today_mood, period_key
    cid = update.message.chat_id
    rows = await asyncio.to_thread(list_facts, cid)
    over = today_mood(rows)
    cur = over if over else auto_mood(cid)
    kind = "qo'lda qo'yilgan" if over else "avtomatik"
    await update.message.reply_text(
        f"Hozirgi kayfiyatim ({kind}): {cur}\n"
        f"Qism: {period_key().split('-', 3)[-1]} (faqat shu qism uchun)\n\n"
        "O'zgartirish: /kayfiyat_qoy <matn>\n"
        "Qo'lda qo'yilganini olib tashlash: /kayfiyat_tozala")

async def kayfiyat_qoy(update, ctx):
    from database import save_fact, list_facts, del_fact
    from utils import BOTKAYF_TAG, period_key
    cid = update.message.chat_id
    text = " ".join(ctx.args).strip()[:150]
    if not text:
        await update.message.reply_text(
            "Masalan: /kayfiyat_qoy sokin va biroz o'ychan")
        return
    key = BOTKAYF_TAG + period_key() + "] "
    rows = await asyncio.to_thread(list_facts, cid)
    for x in rows:
        if x["fact"].startswith(key):
            await asyncio.to_thread(del_fact, cid, x["id"])
    await asyncio.to_thread(save_fact, cid, key + text)
    await update.message.reply_text(
        f"Endi shu qism uchun kayfiyatim: {text}")

async def kayfiyat_tozala(update, ctx):
    from database import list_facts, del_fact
    from utils import BOTKAYF_TAG, period_key
    cid = update.message.chat_id
    key = BOTKAYF_TAG + period_key() + "] "
    rows = await asyncio.to_thread(list_facts, cid)
    n = 0
    for x in rows:
        if x["fact"].startswith(key):
            await asyncio.to_thread(del_fact, cid, x["id"])
            n += 1
    await update.message.reply_text(
        "Qo'lda qo'yilgan kayfiyat olib tashlandi, endi avtomatik." if n
        else "Qo'lda qo'yilgan kayfiyat yo'q edi.")


async def holat_cmd(update, ctx):
    from database import list_facts, get_settings, messages_between
    from config import CHAT_MODELS, FALLBACKS, PIXABAY_KEY, TZ
    from images import PEXELS_KEY
    from datetime import datetime, timezone
    cid = update.message.chat_id
    rows = await asyncio.to_thread(list_facts, cid)
    cnt = {"muhim": 0, "oddiy": 0, "holat": 0}
    for x in rows:
        t = _tier_of_row(x["fact"])
        if t in cnt:
            cnt[t] += 1
    st = await asyncio.to_thread(get_settings, cid)
    now = datetime.now(TZ)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today = await asyncio.to_thread(
        messages_between, cid,
        start.astimezone(timezone.utc).isoformat(),
        now.astimezone(timezone.utc).isoformat())
    user_today = sum(1 for m in today if m["role"] == "user")
    models = CHAT_MODELS if CHAT_MODELS else FALLBACKS
    srcs = ["Openverse", "Wikimedia"]
    if PIXABAY_KEY:
        srcs.append("Pixabay")
    if PEXELS_KEY:
        srcs.append("Pexels")
    proactive = st.get("proactive", True) if st else True
    yoz_holat = "yoqilgan" if proactive else "o'chirilgan"
    await update.message.reply_text(
        "📊 Holat\n\n"
        f"Bugun siz yozgan xabarlar: {user_today}\n"
        f"Saqlangan faktlar: muhim {cnt['muhim']}, oddiy {cnt['oddiy']}\n"
        f"Bugungi holat: {'bor' if cnt['holat'] else 'aytilmagan'}\n"
        f"O'zi yozish: {yoz_holat}\n"
        f"Javob modeli: {models[0]}\n"
        f"Zaxira modellar: {', '.join(FALLBACKS)}\n"
        f"Rasm manbalari: {', '.join(srcs)}\n\n"
        "Gemini kunlik limitini AI Studio → Rate limit bo'limidan ko'ring.")


async def eksport_cmd(update, ctx):
    from io import BytesIO
    from database import list_facts, pending
    from config import TZ
    from datetime import datetime
    from utils import parse_odat
    cid = update.message.chat_id
    rows = await asyncio.to_thread(list_facts, cid)
    muhim, oddiy, odat = [], [], []
    prefixes = ("[muhim] ", "[oddiy] ", "[yengil] ")
    for x in rows:
        f = x["fact"]
        if f.startswith(("[holat ", "[botkayf ", "[kecha ", "[kunoxi ", "[odatkun ")):
            continue
        if f.startswith("[odat] "):
            e, t, q = parse_odat(f)
            odat.append((f"{e} {t}" + (f" (rasm: {q})" if q else "")).strip())
            continue
        text = f
        for p in prefixes:
            if text.startswith(p):
                text = text[len(p):]
        if _tier_of_row(f) == "muhim":
            muhim.append(text)
        else:
            oddiy.append(text)
    rems = await asyncio.to_thread(pending, cid)
    lines = ["REZE: MA'LUMOT EKSPORTI", ""]
    lines += ["== MUHIM FAKTLAR =="] + [f"- {t}" for t in muhim] + [""]
    lines += ["== ODDIY FAKTLAR =="] + [f"- {t}" for t in oddiy] + [""]
    lines += ["== ODATLAR =="] + [f"- {t}" for t in odat] + [""]
    lines += ["== KUTILAYOTGAN ESLATMALAR =="]
    for r in rems or []:
        try:
            when = datetime.fromisoformat(
                r["remind_at"].replace("Z", "+00:00")).astimezone(TZ)
            when = when.strftime("%Y-%m-%d %H:%M")
        except Exception:
            when = str(r.get("remind_at", ""))
        lines.append(f"- {r.get('task', '')} ({when})")
    bio = BytesIO("\n".join(lines).encode("utf-8"))
    bio.name = f"{NAME.lower()}-eksport.txt"
    await update.message.reply_document(
        document=bio, caption="Mana, saqlangan ma'lumotlaringiz.")


async def odat_rejim_cmd(update, ctx):
    from database import list_facts, save_fact, del_fact
    from utils import ODATREJIM_TAG, get_odat_mode
    cid = update.message.chat_id
    rows = await asyncio.to_thread(list_facts, cid)
    arg = ctx.args[0].upper() if ctx.args else ""
    if not arg:
        await update.message.reply_text(
            f"Hozirgi odat rejimi: {get_odat_mode(rows)}\n\n"
            "A: hozirgi yoki umumiy zamonda (\"hozir choy ichyapman\")\n"
            "B: kuniga bir marta, o'tgan zamonda (\"bugun kitob o'qidim\")\n"
            "AB: ikkalasi (standart)\n"
            "yoq: odat umuman aytilmaydi\n\n"
            "O'zgartirish: /odat_rejim AB (yoki A, B, yoq). Standartga qaytarish: /odat_rejim tozala")
        return
    if arg not in ("A", "B", "AB", "YOQ", "TOZALA"):
        await update.message.reply_text(
            "Variantlar: A, B, AB, yoq, tozala. Masalan: /odat_rejim B")
        return
    for x in rows:
        if x["fact"].startswith(ODATREJIM_TAG):
            await asyncio.to_thread(del_fact, cid, x["id"])
    if arg == "TOZALA":
        await update.message.reply_text("Odat rejimi standartga qaytdi: AB.")
        return
    val = "yoq" if arg == "YOQ" else arg
    await asyncio.to_thread(save_fact, cid, ODATREJIM_TAG + val)
    await update.message.reply_text(f"Odat rejimi endi: {val}")


def _pack_names(st):
    return [x.strip() for x in str((st or {}).get("sticker_set") or "").split(",") if x.strip()]


async def sticker_list_cmd(update, ctx):
    from utils import ensure_packs, labels_of
    cid = update.message.chat_id
    st = await asyncio.to_thread(get_settings, cid)
    names = _pack_names(st)
    state = "yoqilgan" if st.get("stickers") is not False else "o'chirilgan"
    if not names:
        await update.message.reply_text(
            f"Stiker paketi yo'q (stikerlar {state}). Qo'shish: /stiker_qosh <nom>")
        return
    ok = await ensure_packs(ctx.bot, names)
    labs = labels_of(st)
    lines = [f"Stikerlar: {state}. Paketlar: {len(names)} ta"]
    for i, n in enumerate(names, 1):
        mark_ = "  ← asosiy" if i == 1 else ""
        if n in ok:
            its = STATE["packitems"][n]
            emo = len({x["emoji"] for x in its if x["emoji"]})
            lm = labs.get(n) or {}
            done = sum(1 for x in its if x["uid"] in lm)
            info = f"{len(its)} stiker, {emo} xil emoji, belgilangan {done}"
        else:
            info = "YUKLANMADI (nom noto'g'ri yoki paket o'chgan)"
        lines.append(f"{i}. {n}  (t.me/addstickers/{n}){mark_}\n   {info}")
    lines.append("Qo'shish: /stiker_qosh <nom>\nO'chirish: /stiker_ochir <nom>\n"
                 "Belgilash: /stiker_belgila (asosiy paket) yoki /stiker_belgila hammasi")
    await update.message.reply_text("\n".join(lines))


async def sticker_label_cmd(update, ctx):
    """Paket stikerlarini Gemini bilan hissiyot bo'yicha belgilaydi (bir martalik)."""
    from utils import label_pack
    cid = update.message.chat_id
    arg = " ".join(ctx.args).strip().rstrip("/")
    st = await asyncio.to_thread(get_settings, cid)
    names = _pack_names(st)
    if not names:
        await update.message.reply_text("Avval stiker paketi qo'shing: /stiker_qosh <nom>")
        return
    if not arg:
        targets = names[:1]
    elif arg.lower() == "hammasi":
        targets = names
    else:
        nm = arg.split("/")[-1]
        if nm not in names:
            await update.message.reply_text("Bu paket ro'yxatda yo'q. Ro'yxat: /stiker_royxat")
            return
        targets = [nm]
    if STATE.get("labeling"):
        await update.message.reply_text("Belgilash allaqachon ketyapti, tugashini kuting.")
        return
    STATE["labeling"] = True
    await update.message.reply_text(
        "Belgilashni boshladim (har 10 stikerga 1 ta so'rov). Tugagach yozaman, "
        "bu orada suhbatlashishingiz mumkin.")

    async def save(c, text):
        await asyncio.to_thread(update_setting, c, "sticker_labels", text)

    async def job():
        try:
            for n in targets:
                try:
                    counts, left = await label_pack(ctx.bot, cid, st, n, save)
                except Exception as e:
                    msg_ = ("Bazada sticker_labels ustuni yo'q: sql-B-variant.sql "
                            "dagi oxirgi qatorni ishga tushiring."
                            if "sticker_labels" in str(e) else f"xato: {e}")
                    await ctx.bot.send_message(cid, f"{n}: belgilanmadi ({msg_})")
                    return
                rows = ", ".join(f"{k}: {v}" for k, v in
                                 sorted(counts.items(), key=lambda x: -x[1])) or "yo'q"
                tail = (f"\nBelgilanmay qoldi: {left} (qayta yozsangiz faqat shular uriniladi)"
                        if left else "")
                await ctx.bot.send_message(cid, f"{n} belgilandi.\n{rows}{tail}")
        except Exception as e:
            print("BELGILASH job xato:", repr(e))
        finally:
            STATE["labeling"] = False

    tasks = STATE.setdefault("tasks", set())
    t = asyncio.create_task(job())
    tasks.add(t)
    t.add_done_callback(tasks.discard)


async def sticker_add_cmd(update, ctx):
    cid = update.message.chat_id
    arg = " ".join(ctx.args).strip().rstrip("/")
    if not arg:
        await update.message.reply_text(
            "Ishlatish: /stiker_qosh <nom yoki t.me/addstickers/... havolasi>")
        return
    name = arg.split("/")[-1]
    st = await asyncio.to_thread(get_settings, cid)
    names = _pack_names(st)
    if name in names:
        await update.message.reply_text("Bu paket allaqachon ro'yxatda.")
        return
    try:
        ss = await ctx.bot.get_sticker_set(name)
    except Exception:
        await update.message.reply_text("Bunday stiker paketi topilmadi.")
        return
    names.append(name)
    await asyncio.to_thread(update_setting, cid, "sticker_set", ",".join(names))
    await asyncio.to_thread(update_setting, cid, "stickers", True)
    STATE.get("packs", {}).pop(name, None)
    await update.message.reply_text(
        f"Qo'shildi: {name} ({len(ss.stickers)} ta stiker). Jami {len(names)} paket.")


async def sticker_del_cmd(update, ctx):
    cid = update.message.chat_id
    arg = " ".join(ctx.args).strip().rstrip("/")
    if not arg:
        await update.message.reply_text(
            "Ishlatish: /stiker_ochir <nom> (ro'yxat: /stiker_royxat)")
        return
    name = arg.split("/")[-1]
    st = await asyncio.to_thread(get_settings, cid)
    names = _pack_names(st)
    if name not in names:
        await update.message.reply_text(
            "Bu paket ro'yxatda yo'q. Ro'yxat: /stiker_royxat")
        return
    names.remove(name)
    await asyncio.to_thread(update_setting, cid, "sticker_set", ",".join(names))
    STATE.get("packs", {}).pop(name, None)
    await update.message.reply_text(
        f"O'chirildi: {name}. Qolgan paketlar: {len(names)}.")


async def sticker_primary_cmd(update, ctx):
    """Paketni asosiy (birinchi) qiladi: stikerlarning 50% shu paketdan olinadi."""
    cid = update.message.chat_id
    arg = " ".join(ctx.args).strip().rstrip("/")
    if not arg:
        await update.message.reply_text(
            "Ishlatish: /stiker_asosiy <nom> (ro'yxat: /stiker_royxat)")
        return
    name = arg.split("/")[-1]
    st = await asyncio.to_thread(get_settings, cid)
    names = _pack_names(st)
    if name not in names:
        await update.message.reply_text(
            "Bu paket ro'yxatda yo'q. Avval: /stiker_qosh <nom>")
        return
    names.remove(name)
    names.insert(0, name)
    await asyncio.to_thread(update_setting, cid, "sticker_set", ",".join(names))
    await update.message.reply_text(f"Asosiy paket: {name}. Stikerlarning yarmi shundan olinadi.")
