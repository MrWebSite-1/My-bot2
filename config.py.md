# config.py

```python
"""SOZLAMALAR: raqamlar, ro'yxatlar, uslublar, ovozlar, jadval, ruxsat.
Oddiy o'zgartirishlar (soat, uslub nomi, ovoz ro'yxati) shu yerda.
"""
import os, re
from datetime import timezone, timedelta
from telegram.ext import filters

VOICE = "uz-UZ-MadinaNeural"

TZ = timezone(timedelta(hours=5))

UTC_FMT = "%Y-%m-%dT%H:%M:%SZ"

HISTORY = 16

EXTRACT_EVERY = 5

SUMMARY_EVERY = 30

KEEP_DAYS = 30

REPEATS = {"daily": "har kuni", "weekly": "har hafta",
           "weekdays": "ish kunlari"}

EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200d]")

STYLES = {
    "muloyim": ("🌸 Muloyim", ""),
    "quvnoq": ("😄 Quvnoq",
        "Hozirgi uslub: quvnoq, energiyali va o'ynoqi; emojini "
        "biroz ko'proq ishlat (lekin har gapda emas), ba'zan "
        "hazil qil, lekin g'amxo'rlikni yo'qotma."),
    "sokin": ("🌙 Sokin",
        "Hozirgi uslub: sokin, yumshoq va o'ychan; gaplar qisqa "
        "va mayin bo'lsin."),
    "hazilkash": ("😏 Hazilkash",
        "Hozirgi uslub: hazilkash, shirin qochirimlar va yengil "
        "hazillar bilan; hazil bilan, lekin fikringni aytishdan qochma."),
    "ishchan": ("📋 Ishchan",
        "Hozirgi uslub: aniq, tartibli va lo'nda; ortiqcha gap va "
        "emojisiz, foydali javobga e'tibor ber."),
}

VOICES = {"uz-UZ-MadinaNeural": "Madina (ayol)",
          "uz-UZ-SardorNeural": "Sardor (erkak)"}

RATES = {"-20%": "🐢 Sekin", "+0%": "Oddiy", "+20%": "🐇 Tez"}

VMODES = {"auto": "Ovozga ovoz bilan", "always": "Doim ovozli",
          "off": "Ovozsiz"}

ENGINES = {"edge": "Oddiy (Edge)", "gemini": "Insoniy (Gemini)"}

GVOICES = {"Sulafat": "Sulafat (iliq)",
           "Achernar": "Achernar (yumshoq)",
           "Vindemiatrix": "Vindemiatrix (mayin)",
           "Aoede": "Aoede (yengil)"}

GTTS_MODELS = ["gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts"]

TTS_STYLE = {
    "muloyim": "Speak in Uzbek as a young, soft-spoken woman. "
               "Warm and gentle, with a faint smile in the voice. "
               "Calm, unhurried pace, natural short pauses, soft "
               "intonation. Never robotic or like a news announcer.",
    "quvnoq": "Speak in Uzbek as a cheerful young woman, lively "
              "but still warm and sweet.",
    "sokin": "Speak in Uzbek, very softly and slowly, almost "
             "whispering, soothing like a quiet bedtime talk.",
    "hazilkash": "Speak in Uzbek, playful and affectionate, with "
                 "light teasing in the voice.",
    "ishchan": "Speak in Uzbek, clear, calm and friendly.",
}

STATE = {}

PIXABAY_KEY = os.environ.get("PIXABAY_API_KEY", "")

IMAGES_ON = True

SLOTS = [("ertalab", 9), ("tushlik", 13), ("kechqurun", 21)]

# Uzoq jimlikdan keyin botning o'zi yozishi
JIMLIK_HOURS = 8
JIMLIK_START = 10
JIMLIK_END = 22

ALLOWED = {int(x) for x in
           os.environ.get("ALLOWED_IDS", "").split(",")
           if x.strip()}

ACCESS = (filters.User(user_id=list(ALLOWED))
          if ALLOWED else filters.ALL)

# Guruhlar: faqat shu chat ID'lardagina ishlaydi (manfiy raqamlar, vergul bilan).
# Bo'sh bo'lsa yoki ALLOWED_IDS bo'sh bo'lsa, bot hech bir guruhda ishlamaydi.
ALLOWED_CHATS = ({int(x) for x in
                  os.environ.get("ALLOWED_CHATS", "").split(",")
                  if x.strip()} if ALLOWED else set())

# Guruhda murojaat uchun qo'shimcha nomlar (vergul bilan). Asosiy ism
# character.py dagi NAME'dan olinadi.
BOT_NAMES = [x.strip().lower() for x in
             os.environ.get("BOT_NAMES", "").split(",") if x.strip()]

# Qaysi chatlarda ishlash: shaxsiy chat har doim, guruh faqat ro'yxatdagi.
# Kanal xabarlari va tahrirlangan xabarlar o'tmaydi.
_PRIV = filters.ChatType.PRIVATE
if ALLOWED_CHATS:
    _PRIV = _PRIV | (filters.ChatType.GROUPS &
                     filters.Chat(chat_id=list(ALLOWED_CHATS)))
CHAT_OK = filters.UpdateType.MESSAGE & _PRIV

FALLBACKS = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]

_cm = os.environ.get("CHAT_MODEL", "").strip()

CHAT_MODELS = ([_cm] if _cm else []) + FALLBACKS

# Botning o'zi yozish rejasi: kuniga necha marta, qaysi soatlar oralig'ida,
# ikki xabar orasida kamida necha daqiqa
PROACTIVE_HOURS = (8, 23)
PROACTIVE_PER_DAY = (3, 5)
PROACTIVE_GAP = 75
```
