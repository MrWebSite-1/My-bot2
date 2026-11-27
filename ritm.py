"""ODAMGA O'XSHASH RITM (2-bosqich, 1-band):
1) javob uzunligi foydalanuvchi xabari uzunligiga va soatga moslanadi;
2) ba'zan asosiy javobdan oldin juda qisqa xabar ("hm, kutgin") yuboriladi.
Tunda qisqa gap qoidasi utils.time_text'da bor, bu yerda faqat kuchaytiriladi.
"""
import random, time
from datetime import datetime
from config import TZ
from character import NAME

PRE_P = 0.12          # qisqa oldingi xabar ehtimoli
PRE_GAP_S = 20 * 60   # ikki oldingi xabar orasi eng kami (soniya)
PRE = {
    "Reze": ["hm, kutgin 🤔", "ayt-chi, o'ylab olay...", "voy, bir soniya 🙈",
             "hmm, qiziq...", "bir daqiqa, o'ylayapman"],
    "Makima": ["hm, kutib tur.", "bir soniya.", "o'ylab olay.", "hmm...",
               "to'xta, o'ylayman."],
}
_LAST = {}


def length_text(msg, now=None):
    """Foydalanuvchi xabari uzunligi va soatga qarab uzunlik ko'rsatmasi."""
    now = now or datetime.now(TZ)
    n = len((getattr(msg, "text", None) or getattr(msg, "caption", None) or "").strip())
    out = ""
    if getattr(msg, "text", None) is not None:
        if n < 20:
            out = ("Foydalanuvchi juda qisqa yozdi: javobing ham 1 gap, "
                   "ortiqcha izoh yo'q (kino yoki sport rejasi so'ralgan bo'lsa bundan mustasno).")
        elif n > 300:
            out = ("Foydalanuvchi uzun yozdi: 3-5 gap bilan javob ber va "
                   "aytganining aniq bir joyiga to'xtal.")
    if now.hour >= 23 or now.hour < 5:
        out += " Hozir kech: bir gapdan oshirma."
    return ("\n\nRitm: " + out.strip()) if out.strip() else ""


def want_pre(cid, msg, answer, vm, now_s=None):
    """Asosiy javobdan oldin qisqa xabar yuborilsinmi."""
    t = (getattr(msg, "text", None) or "").strip()
    if not t or getattr(msg, "voice", None) or vm == "always":
        return False
    if len(t) < 30 and not t.endswith("?"):
        return False
    a = (answer or "").strip()
    if len(a) < 60 or "\n" in a:
        return False
    now_s = now_s or time.time()
    if now_s - _LAST.get(cid, 0) < PRE_GAP_S:
        return False
    if random.random() > PRE_P:
        return False
    _LAST[cid] = now_s
    return True


def pre_text():
    return random.choice(PRE.get(NAME) or PRE["Reze"])
