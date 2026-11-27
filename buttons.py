"""TUGMALAR: inline tugmalar bosilganda (eslatma, uslub, ovoz sozlamalari).
"""
import asyncio
from datetime import datetime, timezone, timedelta
from config import (ALLOWED, ALLOWED_CHATS, UTC_FMT, STYLES, VOICES, RATES, VMODES,
                    ENGINES, GVOICES)
from database import (get_reminder, save_reminder, update_setting,
                      get_settings)
from character import NAME
from voice import speak
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import fikr

async def on_button(update, ctx):
    q = update.callback_query
    if ALLOWED and q.from_user.id not in ALLOWED:
        await q.answer()
        return
    ch = q.message.chat if q.message else None
    if ch is not None and ch.type != "private" and ch.id not in ALLOWED_CHATS:
        await q.answer()
        return
    parts = (q.data or "").split(":")
    try:
        if parts[0] == "ok":
            await q.answer("Zo'r!")
            await q.edit_message_reply_markup(reply_markup=None)
        elif parts[0] == "snz":
            rid, mins = int(parts[1]), int(parts[2])
            row = await asyncio.to_thread(get_reminder, rid)
            if not row or row["chat_id"] != q.message.chat_id:
                await q.answer("Topilmadi")
                return
            when = (datetime.now(timezone.utc)
                    + timedelta(minutes=mins))
            await asyncio.to_thread(
                save_reminder, row["chat_id"], row["task"],
                when.strftime(UTC_FMT))
            await q.answer("Keyinroq eslataman")
            await q.edit_message_reply_markup(reply_markup=None)
            await q.message.reply_text(
                "Yaxshi, " + ("1 soatdan" if mins >= 60
                              else f"{mins} daqiqadan")
                + " keyin yana eslataman.")
        elif parts[0] == "fb" and len(parts) == 2:
            if parts[1] in fikr.TAGS:
                await fikr.add_tag(q.message.chat_id, parts[1])
                await q.answer("Rahmat!")
                await q.edit_message_text("Tushundim, shunga moslashaman 🤍")
            else:
                await q.answer()
                await q.message.delete()
        elif parts[0] == "set" and len(parts) == 3:
            key, val = parts[1], parts[2]
            table = {"style": STYLES, "voice": VOICES,
                     "rate": RATES, "vmode": VMODES,
                     "engine": ENGINES, "gvoice": GVOICES}
            if key not in table or val not in table[key]:
                await q.answer("?")
                return
            cid = q.message.chat_id
            await asyncio.to_thread(update_setting, cid, key, val)
            label = table[key][val]
            if isinstance(label, tuple):
                label = label[0]
            await q.answer("Saqlandi")
            await q.message.reply_text(f"✅ {label}")
            if key in ("voice", "rate", "engine", "gvoice"):
                st2 = await asyncio.to_thread(get_settings, cid)
                try:
                    await q.message.reply_voice(await speak(
                        f"Salom, men {NAME}. Ovozim shunday "
                        "eshitiladi.", st2))
                except Exception as e:
                    print("NAMUNA xato:", e)
        else:
            await q.answer()
    except Exception as e:
        print("TUGMA xato:", e)


async def on_reaction(update, ctx):
    """Javobga 👎 bosilsa bir so'zli izoh so'raydi, 👍/❤ bosilsa eslab qoladi."""
    r = update.message_reaction
    if r is None or r.chat.type != "private":
        return
    if ALLOWED and (r.user is None or r.user.id not in ALLOWED):
        return
    text = fikr.lookup(r.chat.id, r.message_id)
    if text is None:
        return
    old = {getattr(x, "emoji", None) for x in r.old_reaction}
    new = {getattr(x, "emoji", None) for x in r.new_reaction}
    added = new - old
    try:
        if "👎" in added:
            rows = [[InlineKeyboardButton(fikr.TAGS[k][0], callback_data=f"fb:{k}")
                     for k in ks] for ks in (("uzun", "sovuq"), ("hazil", "qisqa"))]
            rows.append([InlineKeyboardButton("Shunchaki", callback_data="fb:x")])
            await ctx.bot.send_message(
                r.chat.id, "Nimasi yoqmadi? 🥺",
                reply_to_message_id=r.message_id,
                reply_markup=InlineKeyboardMarkup(rows))
        elif added & {"👍", "❤"}:
            await fikr.add_like(r.chat.id, text)
    except Exception as e:
        print("REAKSIYA-FIKR xato:", e)
