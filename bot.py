"""BOT: ishga tushirish fayli. Faqat buyruqlarni ulaydi.
Yangi buyruq qo'shish: commands.py da funksiya yozing, pastda ro'yxatga qo'shing.
"""
import asyncio, os, threading
from telegram.ext import (ApplicationBuilder, MessageHandler,
                          CommandHandler, CallbackQueryHandler,
                          ChatMemberHandler, filters)
from config import ACCESS, CHAT_OK
from guard import guarded, on_added
import relay
from bcommands import (botlar_cmd, rejim_cmd, gap_cmd, mustaqil_cmd,
                       soni_cmd, oraliq_cmd, kutish_cmd, kunlik_cmd, ortoq_fakt_cmd,
                       stop_cmd)
from server import run_web
from loops import start_loop
from chat import handle
from buttons import on_button
from commands import (forget, list_rem, cancel, msg_on, msg_off, my_id,
                      memory_cmd, fact_del, fact_add, summary_cmd,
                      refresh_cmd, style_cmd, voice_cmd, voice_test,
                      sticker_pack_cmd, sticker_off, sticker_on)

from commands import memory_muhim, memory_oddiy, memory_holat
from commands import holat_cmd, eksport_cmd, odat_rejim_cmd
from commands import sticker_list_cmd, sticker_add_cmd, sticker_del_cmd
from commands import (yozish_cmd, oraliq_cmd, saat_cmd, jimlik_cmd,
                      yozish_holat, odat_qosh, odatlar, odat_ochir,
                      kayfiyat_cmd, kayfiyat_qoy, kayfiyat_tozala)

threading.Thread(target=run_web, daemon=True).start()
from telegram import BotCommand

MENU = {'id': "Telegram ID'ingiz", 'unut': "Hamma xotirani o'chirish", 'holat': 'Bot holati va bugungi sarf', 'eslatmalar': "Eslatmalar ro'yxati", 'bekor': 'Eslatmani bekor qilish: /bekor 3', 'xabar_bor': "O'zi yozishni yoqish", 'xabar_yoq': "O'zi yozishni o'chirish", 'xotira': "Xotira bo'limlari", 'xotira_muhim': 'Muhim faktlar', 'xotira_oddiy': 'Oddiy faktlar', 'xotira_holat': 'Bugungi holat', 'fakt_ochir': "Faktni o'chirish: /fakt_ochir 2", 'eslab_qol': "Fakt qo'shish: /eslab_qol matn", 'odat_qosh': "Odat qo'shish", 'odatlar': "Odatlar ro'yxati", 'odat_ochir': "Odatni o'chirish: /odat_ochir 2", 'yozish': 'Kuniga necha marta yozish', 'yozish_oraliq': 'Xabarlar orasi (daqiqa)', 'yozish_saat': 'Yozish soatlari', 'jimlik': 'Necha soat yozmasangiz yozish', 'yozish_holat': 'Yozish sozlamalari', 'kayfiyat': 'Hozirgi kayfiyat', 'kayfiyat_qoy': "Kayfiyatni qo'yish", 'kayfiyat_tozala': "Qo'lda kayfiyatni olib tashlash", 'uslub': 'Javob uslubi', 'ovoz': 'Ovoz sozlamalari', 'ovoz_test': 'Ovozlarni sinash', 'stiker_paket': 'Stiker paketini tanlash', 'stiker_yoq': "Stikerlarni o'chirish", 'stiker_bor': 'Stikerlarni yoqish', 'xulosa': 'Suhbat xulosasi', 'yangila': 'Faktlarni yangilash'}

MENU["eksport"] = "Ma'lumotni fayl qilib olish"
MENU["stiker_royxat"] = "Stiker paketlari ro'yxati"
MENU["stiker_qosh"] = "Stiker paketi qo'shish: /stiker_qosh <nom>"
MENU["stiker_ochir"] = "Stiker paketini o'chirish: /stiker_ochir <nom>"
MENU["odat_rejim"] = "Odat rejimi: A, B, AB yoki yoq"
MENU.update({
    "botlar": "Guruhda botlar sozlamalari",
    "guruh_rejim": "Guruh rejimi: A (murojaat) yoki B (gapga qarab)",
    "botlar_gap": "Botlar o'zaro gaplashsin: on yoki off",
    "botlar_mustaqil": "Sizsiz gaplashuv: on yoki off",
    "botlar_soni": "Bir zanjirda bot xabarlari soni",
    "botlar_oraliq": "Sizsiz gaplashuv oralig'i (daqiqa)",
    "botlar_kutish": "Bot xabarlari orasi (soniya)",
    "botlar_kunlik": "Kunlik bot-bot chegarasi (0 = yo'q)",
    "botlar_stop": "Botlar gaplashuvini darhol to'xtatish",
    "ortoq_fakt": "Ikkala botga umumiy fakt (lichkada)",
})

async def post_init_all(app):
    """Buyruqlar menyusini Telegram'ga ro'yxatga olish, keyin fon vazifalari."""
    cmds = [BotCommand(n, MENU[n]) for n, _ in COMMANDS if n in MENU]
    try:
        await app.bot.set_my_commands(cmds)
        print("MENYU ro'yxatga olindi:", len(cmds))
    except Exception as e:
        print("MENYU xato:", repr(e))
    relay.attach(app, asyncio.get_running_loop())
    await start_loop(app)

app = (ApplicationBuilder().token(os.environ["BOT_TOKEN"])
       .post_init(post_init_all).build())

# buyruq nomi -> funksiya
COMMANDS = [
    ("unut", forget),
    ("eslatmalar", list_rem),
    ("bekor", cancel),
    ("xabar_bor", msg_on),
    ("xabar_yoq", msg_off),
    ("xotira", memory_cmd),
    ("xotira_muhim", memory_muhim),
    ("xotira_oddiy", memory_oddiy),
    ("xotira_holat", memory_holat),
    ("holat", holat_cmd),
    ("eksport", eksport_cmd),
    ("odat_rejim", odat_rejim_cmd),
    ("odat_qosh", odat_qosh),
    ("odatlar", odatlar),
    ("odat_ochir", odat_ochir),
    ("yozish", yozish_cmd),
    ("yozish_oraliq", oraliq_cmd),
    ("yozish_saat", saat_cmd),
    ("jimlik", jimlik_cmd),
    ("yozish_holat", yozish_holat),
    ("kayfiyat", kayfiyat_cmd),
    ("kayfiyat_qoy", kayfiyat_qoy),
    ("kayfiyat_tozala", kayfiyat_tozala),
    ("fakt_ochir", fact_del),
    ("eslab_qol", fact_add),
    ("uslub", style_cmd),
    ("ovoz", voice_cmd),
    ("ovoz_test", voice_test),
    ("stiker_paket", sticker_pack_cmd),
    ("stiker_yoq", sticker_off),
    ("stiker_bor", sticker_on),
    ("stiker_royxat", sticker_list_cmd),
    ("stiker_qosh", sticker_add_cmd),
    ("stiker_ochir", sticker_del_cmd),
    ("xulosa", summary_cmd),
    ("yangila", refresh_cmd),
    ("botlar", botlar_cmd),
    ("guruh_rejim", rejim_cmd),
    ("botlar_gap", gap_cmd),
    ("botlar_mustaqil", mustaqil_cmd),
    ("botlar_soni", soni_cmd),
    ("botlar_oraliq", oraliq_cmd),
    ("botlar_kutish", kutish_cmd),
    ("botlar_kunlik", kunlik_cmd),
    ("botlar_stop", stop_cmd),
    ("ortoq_fakt", ortoq_fakt_cmd),
]

app.add_handler(CommandHandler("id", guarded(my_id, True)))
app.add_handler(ChatMemberHandler(on_added, ChatMemberHandler.MY_CHAT_MEMBER))
app.add_handler(CallbackQueryHandler(on_button))
for name, fn in COMMANDS:
    app.add_handler(CommandHandler(
        name, guarded(fn, True), filters=ACCESS & CHAT_OK))
app.add_handler(MessageHandler(
    (filters.VOICE | filters.PHOTO | filters.Sticker.ALL |
     (filters.TEXT & ~filters.COMMAND)) & ACCESS & CHAT_OK,
    guarded(handle)))
app.run_polling(bootstrap_retries=-1)
