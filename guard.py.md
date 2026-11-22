# guard.py

```python
"""GURUH QOIDALARI: bot guruhda faqat egasi murojaat qilganda ishlaydi.
Qoidalar (A variant):
  1) xabar yuboruvchi ALLOWED_IDS da bo'lishi shart (boshqa botlar ham o'tmaydi);
  2) guruh ALLOWED_CHATS da bo'lishi shart;
  3) guruhda faqat ism, @username yoki botning xabariga reply bo'lsa javob;
  4) guruhda buyruq faqat /buyruq@botusername ko'rinishida (ikki bot adashmasin);
  5) kanal xabarlariga javob yo'q, botni kanalga qo'shsa chiqib ketadi.
Guruhda o'zi yozish (salom, jimlik, kun oxiri) loops.py da o'chirilgan.
"""
import re
from functools import wraps
from config import ALLOWED, ALLOWED_CHATS, BOT_NAMES
from character import NAME

GROUPS = ("group", "supergroup")

_names = sorted({NAME.lower(), *BOT_NAMES}, key=len, reverse=True)
# Oxiriga \b qo'yilmagan: "Rezega", "Rezeni" kabi qo'shimchali shakllar ham o'tadi.
_NAME_RE = re.compile(r"(?<!\w)(?:" + "|".join(map(re.escape, _names)) + ")",
                      re.IGNORECASE)


def addressed(msg, bot):
    """Xabar aynan shu botga qaratilganmi (reply, @username yoki ism)."""
    r = msg.reply_to_message
    if r and r.from_user and r.from_user.id == bot.id:
        return True
    text = msg.text or msg.caption or ""
    uname = (bot.username or "").lower()
    if uname and ("@" + uname) in text.lower():
        return True
    return bool(_NAME_RE.search(text))


def command_for_me(msg, bot):
    """Guruhda /buyruq@botusername bo'lsa True; qo'shimchasiz buyruq ikkala botga ham boradi."""
    first = (msg.text or "").split(" ", 1)[0].lower()
    return ("@" + (bot.username or "").lower()) in first


def guarded(fn, command=False):
    """Handler'ni guruh qoidalari bilan o'raydi. Shaxsiy chatda hech narsa o'zgarmaydi."""
    @wraps(fn)
    async def wrapper(update, ctx):
        msg = update.effective_message
        if msg is None:
            return
        if msg.chat.type != "private":
            u = msg.from_user
            if (msg.chat.type not in GROUPS
                    or msg.chat.id not in ALLOWED_CHATS
                    or u is None or u.is_bot or u.id not in ALLOWED):
                return
            if command:
                if not command_for_me(msg, ctx.bot):
                    return
            elif not addressed(msg, ctx.bot):
                return
        return await fn(update, ctx)
    return wrapper


async def on_added(update, ctx):
    """Bot chatga qo'shilganda: kanalga yoki egasi bo'lmagan odam qo'shgan joyga chiqib ketadi.
    Egasi qo'shgan, lekin ALLOWED_CHATS da yo'q guruh bo'lsa, ID'sini egasiga yuboradi."""
    ev = update.my_chat_member
    if ev is None or ev.chat.type == "private":
        return
    if ev.new_chat_member.status not in ("member", "administrator"):
        return
    by = ev.from_user.id if ev.from_user else None
    chat = ev.chat
    if chat.type == "channel" or by not in ALLOWED:
        try:
            await ctx.bot.leave_chat(chat.id)
            print("CHIQDI:", chat.id, chat.type)
        except Exception as e:
            print("CHIQISH xato:", e)
        return
    if chat.id not in ALLOWED_CHATS:
        try:
            await ctx.bot.send_message(
                by, f"«{chat.title}» guruhi ruxsat ro'yxatida yo'q. "
                    f"Ishlashi uchun Render'da ALLOWED_CHATS ga shu ID'ni "
                    f"qo'shing: {chat.id}")
        except Exception as e:
            print("EGASIGA xabar xato:", e)
```
