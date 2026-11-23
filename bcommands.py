"""B VARIANT BUYRUQLARI: guruhda botlar gaplashuvini boshqarish (faqat egasi).
Guruhda buyruq /buyruq@botusername ko'rinishida beriladi. Sozlama bazaga yoziladi
va ikkinchi botga ham uzatiladi, shuning uchun ikkala botda bir xil bo'ladi.
Yoqish/o'chirish uchun on yoki off yoziladi ('yoq' ikki ma'noli bo'lgani uchun
ishlatilmaydi).
"""
import asyncio
from config import ALLOWED_CHATS, PEER_URL
from database import update_setting
from relay import COLS, DEFAULTS, group_cfg, invalidate, push_set

ON = {"on", "yoqish", "ha", "1"}
OFF = {"off", "ochirish", "o'chirish", "yo'q", "0"}


def _arg(ctx):
    return ctx.args[0].strip().lower() if ctx.args else ""


async def _group_only(update):
    m = update.message
    if m.chat.type == "private" or m.chat_id not in ALLOWED_CHATS:
        await m.reply_text("Bu buyruqni ruxsat etilgan guruhda bering "
                           "(/buyruq@botusername ko'rinishida).")
        return None
    return m.chat_id


async def _apply(update, pairs, text):
    """pairs: [(kalit, qiymat)]. Bazaga yozadi va ikkinchi botga uzatadi."""
    cid = update.message.chat_id
    try:
        for key, val in pairs:
            await asyncio.to_thread(update_setting, cid, COLS[key], val)
    except Exception as e:
        print("B sozlama xato:", repr(e))
        await update.message.reply_text(
            "Bazada B variant ustunlari yo'q. Supabase SQL Editor'da "
            "sql-B-variant.sql ni ishga tushiring.")
        return
    invalidate(cid)
    for key, val in pairs:
        push_set(cid, COLS[key], val)
    tail = ("\n(Ikkinchi botga ham uzatilmoqda.)" if PEER_URL else
            "\n(PEER_URL yo'q: faqat shu botga qo'llandi.)")
    await update.message.reply_text(text + tail)


def _yn(v):
    return "yoqilgan" if v else "o'chirilgan"


async def botlar_cmd(update, ctx):
    cid = await _group_only(update)
    if cid is None:
        return
    c = await group_cfg(cid, fresh=True)
    turns = "cheksiz" if c["turns"] == -1 else str(c["turns"])
    daily = "cheklovsiz" if c["daily"] <= 0 else str(c["daily"])
    warn = "" if PEER_URL else "\n⚠️ PEER_URL berilmagan: botlar bir-birini ko'rmaydi."
    await update.message.reply_text(
        "Guruh sozlamalari:\n"
        f"• Rejim: {'B (gapga qarab javob)' if c['mode'] == 'b' else 'A (faqat murojaat bilan)'}\n"
        f"• Botlar o'zaro gaplashadi (siz yozgandan keyin): {_yn(c['talk'])}\n"
        f"• Sizsiz gaplashuv: {_yn(c['auto'])} (har {c['every']} daqiqada)\n"
        f"• Bir zanjirda bot xabarlari: {turns}\n"
        f"• Bot xabarlari orasi: {c['delay']} soniya\n"
        f"• Kunlik bot-bot xabar chegarasi: {daily}\n\n"
        "Buyruqlar: /guruh_rejim a|b, /botlar_gap on|off, "
        "/botlar_mustaqil on|off, /botlar_soni N|cheksiz, "
        "/botlar_oraliq daqiqa, /botlar_kutish soniya, "
        "/botlar_kunlik N|0, /botlar_stop" + warn)


async def rejim_cmd(update, ctx):
    cid = await _group_only(update)
    if cid is None:
        return
    a = _arg(ctx)
    if a not in ("a", "b"):
        await update.message.reply_text(
            "Masalan: /guruh_rejim b\nA: faqat murojaat bilan javob. "
            "B: gapga qarab javob va botlar o'zaro gaplashadi.")
        return
    await _apply(update, [("mode", a)],
                 "Rejim: B, gapga qarab javob." if a == "b"
                 else "Rejim: A, faqat murojaat bilan javob.")


async def _onoff(update, ctx, key, label):
    cid = await _group_only(update)
    if cid is None:
        return
    a = _arg(ctx)
    if a in ON:
        v = True
    elif a in OFF:
        v = False
    else:
        await update.message.reply_text("on yoki off yozing. Masalan: /"
                                        + update.message.text.split()[0].lstrip("/").split("@")[0] + " on")
        return
    await _apply(update, [(key, v)], f"{label}: {_yn(v)}.")


async def gap_cmd(update, ctx):
    await _onoff(update, ctx, "talk", "Botlar o'zaro gaplashishi")


async def mustaqil_cmd(update, ctx):
    await _onoff(update, ctx, "auto", "Sizsiz gaplashuv")


async def soni_cmd(update, ctx):
    cid = await _group_only(update)
    if cid is None:
        return
    a = _arg(ctx)
    if a in ("cheksiz", "unlimited"):
        await _apply(update, [("turns", -1)],
                     "Zanjirdagi bot xabarlari: cheksiz. Ehtiyot bo'ling, "
                     "to'xtatish: /botlar_stop")
        return
    if not a.isdigit() or int(a) < 1:
        await update.message.reply_text(
            "Masalan: /botlar_soni 4 yoki /botlar_soni cheksiz")
        return
    await _apply(update, [("turns", int(a))],
                 f"Bir zanjirda ko'pi bilan {int(a)} ta bot xabari.")


async def _int_cmd(update, ctx, key, lo, text, example):
    cid = await _group_only(update)
    if cid is None:
        return
    a = _arg(ctx)
    if not a.isdigit() or int(a) < lo:
        await update.message.reply_text(f"Masalan: {example}")
        return
    await _apply(update, [(key, int(a))], text.format(n=int(a)))


async def oraliq_cmd(update, ctx):
    await _int_cmd(update, ctx, "every", 1,
                   "Sizsiz gaplashuv oralig'i: {n} daqiqa.",
                   "/botlar_oraliq 180")


async def kutish_cmd(update, ctx):
    await _int_cmd(update, ctx, "delay", 0,
                   "Bot xabarlari orasi: {n} soniya.", "/botlar_kutish 8")


async def kunlik_cmd(update, ctx):
    cid = await _group_only(update)
    if cid is None:
        return
    a = _arg(ctx)
    if not a.isdigit():
        await update.message.reply_text(
            "Masalan: /botlar_kunlik 40 (0 = cheklovsiz)")
        return
    n = int(a)
    await _apply(update, [("daily", n)],
                 "Kunlik bot-bot xabar chegarasi: "
                 + ("cheklovsiz." if n == 0 else f"{n}."))


async def stop_cmd(update, ctx):
    cid = await _group_only(update)
    if cid is None:
        return
    await _apply(update, [("talk", False), ("auto", False)],
                 "To'xtatildi: botlar o'zaro gaplashmaydi, sizsiz ham "
                 "yozmaydi. Siz yozsangiz, ular javob beraveradi.")
