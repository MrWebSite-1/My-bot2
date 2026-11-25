"""ASOSIY SUHBAT: foydalanuvchi xabari kelganda nima bo'lishi.
handle() bosqichlarni ketma-ket chaqiradi:
  1) build_system   - botga beriladigan ko'rsatma (xarakter + xotira)
  2) build_parts    - foydalanuvchi xabarini Gemini formatiga o'tkazish
  3) parse_reply    - Gemini javobini o'qish
  4) apply_reminder - eslatma qo'yish
  5) apply_memory   - faktni eslab qolish / unutish
  6) deliver        - javobni yuborish (matn yoki ovoz)
"""
import asyncio, random
from datetime import datetime, timezone
from google.genai import types
from telegram import ReactionTypeEmoji
from ai import gen, SAFETY
from character import BASE, RULES
from database import set_open_topic, clear_open_topics
from config import (TZ, UTC_FMT, REPEATS, CHAT_MODELS, IMAGES_ON, STICKER_PRIMARY_P)
from utils import primary_pack
from database import (ensure_settings, get_settings, get_history,
                      list_facts, get_summary, save_msg, save_fact,
                      del_fact, save_reminder, update_setting)
from images import send_photos
from database import count_user_messages
from memory import maybe_extract
from utils import (parse_json, send_text, style_text, get_pack,
                   mood_text, time_text, order_facts, with_tier, today_state, today_mood, intimacy_text)
from voice import speak
from relay import repeat_block, peer_answered
from relay import (group_ctx, group_block, worth_deciding, lock, BUSY,
                   after_reply)


async def build_system(cid, st, pack, msg, vm, frows, state=None, mood_over=None):
    facts = [f'{i}. {x["fact"]}' for i, x in enumerate(frows, 1)]
    now = datetime.now(TZ)
    system = (BASE + RULES + "\n\nHozirgi Toshkent vaqti: "
              + time_text(now)
              + f"\nAniq hozirgi sana va vaqt: {now:%Y-%m-%d %H:%M} (Toshkent). "
              "Eslatma vaqti (reminder.time) shu vaqtdan KEYIN bo'lsin; "
              "'5 daqiqadan keyin' bo'lsa, hozirgi vaqtga 5 daqiqa qo'shing.")
    system += style_text(st)
    system += intimacy_text(await asyncio.to_thread(count_user_messages, cid))
    system += mood_text(cid, mood_over)
    if vm == "always" or (vm == "auto" and msg.voice):
        system += ("\n\nBu javob OVOZ bilan yuboriladi: speech "
                   "maydonini to'ldir. Bu answer'ning og'zaki, "
                   "qisqa (1-3 gap), emojisiz, ro'yxatsiz "
                   "varianti; tabiiy pauzalar uchun vergul va "
                   "nuqta ishlat, raqam va sanalarni so'z bilan "
                   "yoz.")
    if pack:
        system += ("\n\nStiker: javobingga mos stiker "
                   "yuborish uchun sticker maydoniga quyidagi "
                   "emojilardan BITTASINI yoz (cheklov yo'q, "
                   "kayfiyatga qarab xohlagancha ishlat), "
                   "kerak bo'lmasa null: "
                   + " ".join(list(pack)[:40]))
    if IMAGES_ON:
        system += ("\n\nRasm yuborish: foydalanuvchi biror "
                   "narsaning haqiqiy rasmini ko'rsatishni "
                   "so'rasa, image maydoniga "
                   '{"query": "ingliz tilida 2-4 so\'zli '
                   'qidiruv", "count": 1} yoz (count 1 dan 4 '
                   "gacha). answer'da rasm yuborayotganingni "
                   "qisqa ayt. Faqat tayyor suratlar yuboriladi, "
                   "o'zing rasm chiza olmaysan. So'ralmasa "
                   "image null bo'lsin.")
    if facts:
        system += ("\n\nFoydalanuvchi haqida bilganlaring ([muhim] eng muhim, doim e'tiborda; sog'liq va moliya haqidagilarni faqat o'zi so'ralganda ishlat):\n- "
                   + "\n- ".join(facts))
    if any("Ochiq ish" in x["fact"] for x in frows):
        system += ("\n\nFaktlarda 'Ochiq ish' bor: suhbat o'rinli bo'lsa, natijasini tabiiy so'ra, bosim qilmasdan.")
    if state:
        system += ("\n\nBugungi holat (foydalanuvchi aytgan): " + state
                   + ". Shu kun davomida hisobga ol, lekin o'zing eslatib o'tirma.")
    summ = await asyncio.to_thread(get_summary, cid)
    if summ:
        system += ("\n\nOldingi suhbatlar xulosasi (faqat "
                   "kontekst uchun, o'zing qayta eslatib "
                   "turma):\n" + summ)
    return system


def history_contents(history):
    contents = [types.Content(
        role="user" if h["role"] == "user" else "model",
        parts=[types.Part(text=h["content"])])
        for h in history]
    while contents and contents[0].role == "model":
        contents.pop(0)
    return contents


async def build_parts(msg, ctx, cid, st, pack):
    """Xabarni (matn, ovoz, rasm, stiker) Gemini qismlariga aylantiradi.
    Yangi stiker paketi topilsa, pack ham yangilanib qaytadi."""
    if msg.voice:
        f = await msg.voice.get_file()
        data = bytes(await f.download_as_bytearray())
        parts = [types.Part.from_bytes(
            data=data, mime_type="audio/ogg"),
            types.Part(text="(ovozli xabar)")]
    elif msg.photo:
        f = await msg.photo[-1].get_file()
        data = bytes(await f.download_as_bytearray())
        cap = msg.caption or "Bu rasmda nima bor?"
        parts = [types.Part.from_bytes(
            data=data, mime_type="image/jpeg"),
            types.Part(text=cap)]
    elif msg.sticker:
        emo = msg.sticker.emoji or ""
        parts = [types.Part(
            text=f"[Foydalanuvchi stiker yubordi: {emo}]")]
        try:
            sk = msg.sticker
            tf = sk.thumbnail if sk.is_animated else None
            if sk.is_animated and not tf:
                raise ValueError("thumbnail yo'q")
            fobj = await (tf or sk).get_file()
            raw = bytes(await fobj.download_as_bytearray())
            ext = (fobj.file_path or "").lower().rsplit(".", 1)[-1]
            mime = {"webp": "image/webp", "jpg": "image/jpeg",
                    "jpeg": "image/jpeg", "png": "image/png",
                    "webm": "video/webm"}.get(ext)
            if mime and len(raw) < 4000000:
                parts = [
                    types.Part.from_bytes(
                        data=raw, mime_type=mime),
                    types.Part(text=(
                        f"(Foydalanuvchi stiker yubordi, "
                        f"emojisi: {emo}. Stikerning o'zini "
                        "ko'rib, mazmuniga mos, jonli javob "
                        "ber.)"))]
        except Exception as e:
            print("STIKER ko'rish xato:", e)
        # Yuborilgan stikerning paketi ro'yxatda bo'lmasa, qo'shiladi
        names_ = [x.strip() for x in str(st.get("sticker_set") or "").split(",")
                  if x.strip()]
        new_set = msg.sticker.set_name
        if (new_set and new_set not in names_
                and st.get("stickers") is not False):
            names_.append(new_set)
            await asyncio.to_thread(
                update_setting, cid, "sticker_set", ",".join(names_))
            await asyncio.to_thread(update_setting, cid, "stickers", True)
            st["sticker_set"] = ",".join(names_)
            pack = await get_pack(ctx.bot, st)
            try:
                await msg.reply_text(
                    f"Stiker paketi qo'shildi: {new_set} "
                    f"(jami {len(names_)} ta). Ro'yxat: /stiker_royxat")
            except Exception:
                pass
    else:
        parts = [types.Part(text=msg.text)]
    return parts, pack


def parse_reply(r, msg):
    """Gemini javobidan: answer, reminder, memory, sticker, image,
    speech va bazaga yoziladigan foydalanuvchi matnini ajratadi."""
    if msg.photo:
        fallback = "[rasm] " + (msg.caption or "")
    elif msg.sticker:
        fallback = "[stiker] " + (msg.sticker.emoji or "")
    else:
        fallback = msg.text or "[ovozli xabar]"
    j = parse_json(r.text)
    if j is not None:
        answer = j.get("answer") or "..."
        if msg.photo:
            user_text = fallback
        else:
            user_text = j.get("transcript") or fallback
        rem = j.get("reminder")
        mem = j.get("memory")
        stk = j.get("sticker")
        img = j.get("image")
        speech = j.get("speech")
        if not isinstance(speech, str) or not speech.strip():
            speech = None
    else:
        answer, rem, mem, stk, img, speech = (
            r.text, None, None, None, None, None)
        user_text = fallback
    return answer, rem, mem, stk, img, speech, user_text


async def apply_reminder(cid, rem):
    """Eslatma qo'yadi. Javobga qo'shiladigan izohni qaytaradi."""
    extra = ""
    if isinstance(rem, dict) and rem.get("task") \
            and rem.get("time"):
        try:
            local = datetime.strptime(
                rem["time"], "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
            if local <= datetime.now(TZ):
                extra = ("\n\n⚠️ Bu vaqt o'tib ketgan, "
                         "eslatma qo'yilmadi.")
            else:
                utc = local.astimezone(timezone.utc)
                rp = rem.get("repeat")
                if rp not in REPEATS:
                    rp = None
                await asyncio.to_thread(
                    save_reminder, cid, rem["task"],
                    utc.strftime(UTC_FMT), rp)
                tag = f" 🔁 {REPEATS[rp]}" if rp else ""
                extra = (f"\n\n✅ Eslatma qo'yildi: {rem['task']}"
                         f" ({local.strftime('%d.%m %H:%M')}){tag}")
        except Exception as e:
            print("ESLATMA xato:", e)
            extra = ("\n\n⚠️ Vaqtni tushunmadim, "
                     "eslatma qo'yilmadi.")
    return extra


async def apply_state(cid, state):
    """Bugungi kayfiyatni saqlaydi; eski holatni almashtiradi."""
    if not isinstance(state, str):
        return
    text = state.strip()[:150]
    if not text or text.lower() in ("null", "none"):
        return
    from database import del_fact as _del, list_facts as _lf
    from utils import STATE_TAG
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    rows = await asyncio.to_thread(_lf, cid)
    for x in rows:
        if x["fact"].startswith(STATE_TAG):
            await asyncio.to_thread(_del, cid, x["id"])
    await asyncio.to_thread(
        save_fact, cid, STATE_TAG + today + "] " + text)

async def apply_memory(cid, mem, frows):
    """Foydalanuvchi so'raganda faktni saqlaydi yoki o'chiradi."""
    extra = ""
    if isinstance(mem, dict):
        try:
            saved, gone, seen = [], [], set()
            for f in (mem.get("remember") or [])[:2]:
                if isinstance(f, str) and f.strip():
                    t = f.strip()[:200]
                    await asyncio.to_thread(
                        save_fact, cid, with_tier(t, "oddiy"))
                    saved.append(t)
            for n in (mem.get("forget") or [])[:3]:
                if (isinstance(n, int) and n not in seen
                        and 1 <= n <= len(frows)):
                    seen.add(n)
                    row = frows[n - 1]
                    await asyncio.to_thread(
                        del_fact, cid, row["id"])
                    gone.append(row["fact"])
            for t in gone:
                extra += f"\n\n🗑 Olib tashladim: «{t}»"
        except Exception as e:
            print("XOTIRA xato:", e)
            extra = ""
    return extra


async def deliver(msg, ctx, cid, vm, st, answer, speech, extra):
    """Javobni yuboradi: matn, ovoz yoki ikkalasi (ovoz sozlamasiga qarab).
    Yuborilgan asosiy xabarni qaytaradi."""
    want_voice = (vm == "always"
                  or (vm == "auto" and bool(msg.voice)))
    audio = None
    sent = None
    if want_voice:
        try:
            await ctx.bot.send_chat_action(cid, "record_voice")
            audio = await speak(speech or answer, st)
        except Exception as e:
            print("TTS xato:", e)
    if audio and vm == "auto":
        try:
            sent = await msg.reply_voice(audio)
            if extra.strip():
                await msg.reply_text(extra.strip())
        except Exception as e:
            print("OVOZ yuborish xato:", e)
            sent = await send_text(msg, ctx.bot, answer, extra)
    else:
        sent = await send_text(msg, ctx.bot, answer, extra)
        if audio:
            try:
                await msg.reply_voice(audio)
            except Exception as e:
                print("OVOZ yuborish xato:", e)
    return sent


# Telegram'ning ruxsat etilgan reaksiyalari (bitta belgili). Iliq xarakterga
# mos bo'lmaganlari (masalan 🖕, 💩, 🤬, 🤮, 🤡, 😈) va ko'p belgili emojilar chiqarib tashlangan.
REACTIONS = [
    "👍", "👎", "❤", "🔥", "🥰", "👏", "😁", "🤔", "🤯", "😱", "🎉", "🤩",
    "🙏", "👌", "🥱", "🥴", "😍", "🐳", "🌚", "🌭", "💯", "🤣", "⚡", "🍌",
    "🏆", "💔", "🤨", "😐", "🍓", "🍾", "💋", "😢", "😭", "🤓", "👻", "👀",
    "🎃", "🙈", "😇", "😨", "🤗", "🫡", "🎅", "🎄", "💅", "🤪", "🗿", "🆒",
    "💘", "🙉", "🦄", "😘", "💊", "🙊", "😎", "👾", "😡",
]

async def react_to(msg, ctx, emoji):
    """Model tanlagan (gapga mos) emoji; mos bo'lmasa kamroq tasodifiy reaksiya."""
    clean = emoji.replace("\ufe0f", "").strip() if isinstance(emoji, str) else ""
    if clean in REACTIONS:
        if random.random() > 0.7:
            return
        choice = clean
    else:
        if random.random() > 0.1:
            return
        choice = random.choice(REACTIONS)
    try:
        await ctx.bot.set_message_reaction(
            chat_id=msg.chat_id, message_id=msg.message_id,
            reaction=[ReactionTypeEmoji(emoji=choice)])
    except Exception as e:
        print("REAKSIYA xato:", e)

def _history_gap(history):
    """Oxirgi 2 soatdan eski xabarlarni olib tashlaydi (oxirgi 2 tasi doim qoladi).
    Qaytaradi: (yangi_tarix, oxirgi_xabardan_beri_daqiqa)."""
    from datetime import datetime, timezone

    def ts(h):
        try:
            t = datetime.fromisoformat(str(h.get("created_at")).replace("Z", "+00:00"))
        except Exception:
            return None
        return t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t

    if not history:
        return history, 0
    last = ts(history[-1])
    if last is None:
        return history, 0
    gap = int((datetime.now(timezone.utc) - last).total_seconds() // 60)
    n = len(history)
    kept = []
    for i, h in enumerate(history):
        t = ts(h)
        if i >= n - 2 or t is None or (last - t).total_seconds() <= 7200:
            kept.append(h)
    return kept, gap


def quoted_text(msg):
    """Foydalanuvchi biror xabarga reply yozgan bo'lsa, o'sha xabarni va kimniki ekanini qaytaradi."""
    r = getattr(msg, "reply_to_message", None)
    if r is None:
        return ""
    txt = ((r.text or r.caption or "").strip())[:300]
    if not txt:
        return ""
    from relay import peer_name
    frm = r.from_user
    if frm is None:
        return ""
    if frm.is_bot and frm.id == msg.get_bot().id:
        return (f"[Foydalanuvchi aynan sizning shu oldingi javobingizga javob yozdi: "
                f"\"{txt}\"]\n")
    if frm.is_bot:
        return (f"[Foydalanuvchi {peer_name()} ning shu xabariga javob yozdi: "
                f"\"{txt}\"]\n")
    return (f"[Foydalanuvchi o'zining shu oldingi xabariga qaytib javob yozdi: "
            f"\"{txt}\"]\n")


async def handle(update, ctx):
    """Kirish nuqtasi. Shaxsiy chat va guruh A rejimi avvalgidek; guruh B rejimida
    gapga qarab javob (relay.py)."""
    msg = update.message
    if msg.chat.type == "private":
        return await _handle_core(update, ctx, None)
    gx = await group_ctx(msg, ctx.bot)
    if gx["mode"] != "b":
        return await _handle_core(update, ctx, gx)
    cid = msg.chat_id
    key = (cid, msg.message_id)
    BUSY.add(key)
    try:
        if not gx["me"]:
            await asyncio.to_thread(ensure_settings, cid)
            text = (msg.text or msg.caption or "").strip()
            if gx["peer"] or not worth_deciding(msg):
                # javob yo'q, lekin kontekst uchun eslab qolamiz
                if text:
                    await asyncio.to_thread(save_msg, cid, "user", text)
                return
            await asyncio.sleep(random.uniform(2, 6))
        async with lock(cid):
            await _handle_core(update, ctx, gx)
    finally:
        BUSY.discard(key)


async def _handle_core(update, ctx, gx):
    msg = update.message
    cid = msg.chat_id
    group_b = bool(gx and gx["mode"] == "b")
    await asyncio.to_thread(ensure_settings, cid)
    if not (group_b and not gx["me"]):
        try:
            await ctx.bot.send_chat_action(cid, "typing")
        except Exception:
            pass
    st, pack = {}, {}
    try:
        st = await asyncio.to_thread(get_settings, cid)
        pack = await get_pack(ctx.bot, st)
        history = await asyncio.to_thread(get_history, cid)
        history, gap_min = _history_gap(history)
        raw_facts = await asyncio.to_thread(list_facts, cid)
        frows = order_facts(raw_facts)
        state_now = today_state(raw_facts)
        vm = st.get("vmode") or "auto"

        # 1) ko'rsatma + 2) suhbat tarixi + yangi xabar
        system = await build_system(cid, st, pack, msg, vm, frows, state_now,
                                    today_mood(raw_facts))
        if gap_min >= 20:
            system += ("\n\nDiqqat: suhbat %d daqiqa oldin to'xtagan. Eski "
                       "so'rovlarni (masalan 'hozir olib kelaman' degan va'dalarni) "
                       "davom ettirma. Faqat foydalanuvchining yangi xabariga javob ber; "
                       "agar eski so'rov hali bajarilmagan bo'lsa, qisqa so'rab qo'y." % gap_min)
        if group_b:
            system += group_block("me" if gx["me"] else "owner")
            system += repeat_block(history)
        contents = history_contents(history)
        parts, pack = await build_parts(msg, ctx, cid, st, pack)
        q_ = quoted_text(msg)
        if q_:
            parts = [types.Part(text=q_)] + list(parts)
        contents.append(types.Content(role="user", parts=parts))

        # 3) Gemini
        cfg = types.GenerateContentConfig(
            system_instruction=system, temperature=1.0,
            safety_settings=SAFETY,
            response_mime_type="application/json")
        r = await gen(
            models=CHAT_MODELS, contents=contents, config=cfg)

        # 4) javobni o'qish, eslatma va xotira
        answer, rem, mem, stk, img, speech, user_text = \
            parse_reply(r, msg)
        if (group_b and not gx["me"] and peer_answered(cid, msg.message_id)):
            # ikkinchi bot bu xabarga allaqachon javob berdi: jim turamiz
            await asyncio.to_thread(save_msg, cid, "user", user_text)
            return
        if (group_b and not gx["me"]
                and (parse_json(r.text) or {}).get("reply") is False):
            # bu safar jim turamiz, lekin gap kontekstda qoladi
            await asyncio.to_thread(save_msg, cid, "user", user_text)
            return
        extra = await apply_reminder(cid, rem)
        extra += await apply_memory(cid, mem, frows)
        state_val = (parse_json(r.text) or {}).get("state")
        await apply_state(cid, state_val)
        await react_to(msg, ctx, (parse_json(r.text) or {}).get("reaction"))

        # 5) yuborish va saqlash
        await asyncio.sleep(min(2.5, 0.6 + len(answer) / 150))
        try:
            await ctx.bot.send_chat_action(cid, "typing")
        except Exception:
            pass
        sent = await deliver(msg, ctx, cid, vm, st, answer, speech, extra)
        await asyncio.to_thread(save_msg, cid, "user", user_text)
        await asyncio.to_thread(save_msg, cid, "model", answer)
        if cid > 0:  # faqat lichka
            import re as _re
            low_ = (user_text or "").lower()
            if any(k in low_ for k in ("bo'ldi", "xayr", "qo'yib tur",
                                       "kerak emas", "mavzuni yop")):
                await asyncio.to_thread(clear_open_topics, cid)  # egasi yopdi
            parts_ = _re.split(r"(?<=[.!?])\s+", (answer or "").strip())
            qs = [p_ for p_ in parts_ if p_.rstrip().endswith("?")]
            last = qs[-1] if qs else ""
            sensitive = _re.search(
                r"kasal|dori|og'ri|shifokor|o'lim|yo'qot|depress|xafa|"
                r"yig'la|qarz|pul|ajrash|uyqu|qiyin", user_text + " " + last, _re.I)
            if last and not sensitive:
                await asyncio.to_thread(set_open_topic, cid, last[:120])
        if group_b and sent is not None:
            after_reply(cid, msg.message_id, msg.message_id,
                        sent.message_id, answer)
        if isinstance(img, dict) and img.get("query"):
            try:
                c_ = img.get("count")
                c_ = c_ if isinstance(c_, int) else 1
                await send_photos(
                    msg, str(img["query"])[:80], max(1, min(c_, 4)),
                    fallback=(msg.text or msg.caption or "")[:80] or None)
            except Exception as e:
                print("RASM xato:", e)
        has_image = isinstance(img, dict) and bool(img.get("query"))
        if isinstance(stk, str) and pack.get(stk.strip()) and not has_image:
            try:
                choices = pack[stk.strip()]
                prim = primary_pack(st).get(stk.strip())
                if prim and random.random() < STICKER_PRIMARY_P:
                    choices = prim  # asosiy paketdan (50%)
                await msg.reply_sticker(random.choice(choices))
            except Exception as e:
                print("STIKER xato:", e)
        await maybe_extract(cid)
    except Exception as e:
        print("XATO:", e)
        if group_b and not gx["me"]:
            return  # murojaat qilinmagan xabarda xato haqida yozmaymiz
        if "BLOK" in str(e):
            await msg.reply_text("Hmm, buni shu tarzda ayta "
                                 "olmadim. Boshqacha so'z bilan "
                                 "davom etamizmi?")
        else:
            await msg.reply_text("Xatolik yoki limit tugadi, "
                                 "birozdan keyin yozib ko'ring.")
