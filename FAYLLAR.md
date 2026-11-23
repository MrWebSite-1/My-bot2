# Qaysi o'zgarish qaysi faylda

| Nimani o'zgartirmoqchisiz | Fayl |
|---|---|
| Xarakter, uslub, javob uzunligi, qarshi chiqish, savol berish, hazil, yaqinlik chegarasi | `character.py` (BASE) |
| JSON javob formati (answer, reminder, memory, state, reaction, sticker, image) | `character.py` (RULES) |
| Salom, tasodifiy xabar, jimlik ko'rsatmalari; kayfiyatlar; odatlar ro'yxati | `character.py` (SLOT_PROMPTS, ANGLES, MOODS, HABITS) |
| Xotira daraja tavsifi (muhim/oddiy/yengil), ochiq ish, ichki hazil, esdalik | `character.py` (RULES), `memory.py` (prompt) |
| Xabar kelganda mantiq: javob, JSON, holat, eslatma, xotira, reaksiya, rasm, stiker, yuborish, samimiylik | `chat.py` |
| Fakt chiqarish (daraja, ochiq ish, ichki hazil), xulosa | `memory.py` |
| Xotira tartibi, daraja, bugungi holat, qo'lda kayfiyat, odat rejimi, samimiylik, vaqt konteksti, tun ohangi | `utils.py` |
| Yozish vaqtlari, reja soni, orasi, jimlik soati, kun oxiri oralig'i | `config.py` (PROACTIVE_*, JIMLIK_*) |
| Xotira tezligi (EXTRACT_EVERY=5), xulosa (SUMMARY_EVERY), tarix (HISTORY), uslublar, ovozlar, modellar (FALLBACKS, CHAT_MODELS), ruxsat | `config.py` |
| Gemini so'rovi, zaxira modellar, xavfsizlik sozlamalari (SAFETY) | `ai.py` |
| Salomlar: tasodifiy yozish, jimlik, odat tanlash, kechagi mavzu, kun oxiri hulosasi | `loops.py` |
| Eslatma sikli | `loops.py` (reminder_loop) |
| Buyruqlar: /xotira*, /odat*, /yozish*, /jimlik, /kayfiyat*, /holat, /eksport, /odat_rejim va boshqalar | `commands.py` |
| Guruh qoidalari: kim, qaysi guruh, murojaat, buyruq, kanal, chiqib ketish | `guard.py`, `config.py` (ALLOWED_CHATS, BOT_NAMES, CHAT_OK) |
| B variant: gapga qarab javob, ikki bot orasida xabar uzatish, mustaqil gaplashuv | `relay.py`, `server.py` (/relay), `chat.py` (handle) |
| B variant buyruqlari (/botlar, /guruh_rejim, /botlar_soni ...) | `bcommands.py`, menyu `bot.py` |
| Buyruqlar ro'yxati, menyu tavsiflari, startup, xato ushlagich, run_polling | `bot.py` |
| Rasm qidiruvi (Pixabay, Openverse, Pexels, Wikimedia), tarjima, filtr | `images.py` |
| Ovoz (Gemini TTS, Edge) | `voice.py` |
| Baza so'rovlari (faktlar, sozlamalar, xabarlar, eslatmalar, xabarlar soni) | `database.py` |
| Tugmalar | `buttons.py` |
| Ping server | `server.py` |

Ishga tushirish: `python bot.py`. Yangi baza ustunlari: `schema.sql` oxiridagi `alter table` qatorlari.
