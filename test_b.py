import sys, os, types, asyncio, json, threading, http.client, random
from unittest.mock import MagicMock, AsyncMock
from types import SimpleNamespace as NS
KOD = sys.argv[1]; sys.path.insert(0, KOD)
os.environ.update(BOT_TOKEN="x", ALLOWED_IDS="1", ALLOWED_CHATS="-100,-200",
    SUPABASE_URL="http://x", SUPABASE_KEY="k", GEMINI_API_KEY="g",
    PEER_URL="http://peer.test", RELAY_SECRET="s3cret", PEER_NAME="Reze", PORT="18765")
for m in ["telegram","telegram.ext","telegram.error","telegram.constants","google","google.genai",
          "google.genai.types","supabase","edge_tts","numpy","soundfile"]:
    sys.modules[m] = MagicMock()
sys.modules["httpx"] = MagicMock()
# ---- soxta baza
SETTINGS, MSGS = {}, []
fake = types.ModuleType("database")
def __getattr__(n): return MagicMock()
fake.__getattr__ = __getattr__
fake.get_settings = lambda cid: dict(SETTINGS.get(cid, {}))
def _upd(cid, k, v): SETTINGS.setdefault(cid, {})[k] = v
fake.update_setting = _upd
fake.ensure_settings = lambda cid: SETTINGS.setdefault(cid, {})
fake.save_msg = lambda cid, role, c: MSGS.append((cid, role, c))
fake.get_history = lambda cid: [{"role": r, "content": c} for (i, r, c) in MSGS if i == cid][-16:]
fake.list_facts = lambda cid: []
fake.get_summary = lambda cid: ""
fake.count_user_messages = lambda cid: 100
sys.modules["database"] = fake
# ---- soxta Gemini
GEN = {"calls": 0, "out": {"answer": "salom", "reply": True}, "err": None}
ai = types.ModuleType("ai"); ai.SAFETY = []
async def gen(models=None, **kw):
    GEN["calls"] += 1
    if GEN["err"]: raise GEN["err"]
    return NS(text=json.dumps(GEN["out"]))
ai.gen = gen; ai.client = MagicMock(); sys.modules["ai"] = ai
# tez uxlash
_real_sleep = asyncio.sleep
async def fast(x, *a, **k): await _real_sleep(0)
asyncio.sleep = fast
random.uniform = lambda a, b: 0

import relay, chat, guard, bcommands
chat.maybe_extract = AsyncMock()
OUT = []
async def fake_post(payload): OUT.append(payload); return True
relay._post = fake_post

class Bot:
    id = 99; username = "MiroBot"
    def __init__(s): s.sent = []; s.n = 1000
    async def send_message(s, cid, text, **kw):
        s.n += 1; s.sent.append((cid, text, kw)); return NS(message_id=s.n)
    async def send_chat_action(s, *a, **k): pass
    async def set_message_reaction(s, **k): pass
    async def get_sticker_set(s, n): raise RuntimeError
bot = Bot(); relay.APP = NS(bot=bot); relay.LOOP = None

fails = 0
def check(name, cond):
    global fails
    print(("OK   " if cond else "FAIL ") + name)
    if not cond: fails += 1
async def settle(): 
    for _ in range(5): await _real_sleep(0)
def relmsg(mid, turn, chain="5", owner="5", cid=-100, text="salom Makima", frm="Reze"):
    return {"type": "msg", "chat_id": cid, "from": frm, "text": text, "tg_msg_id": mid,
            "chain": chain, "owner": owner, "turn": turn}
def reset(cid=-100, **row):
    SETTINGS[cid] = row; MSGS.clear(); OUT.clear(); bot.sent.clear(); relay.CH.clear()
    relay._cache.clear(); relay.STATE.setdefault("rseen", {}).clear(); relay.BUSY.clear()
    relay.STATE.get("bday", {}).clear(); relay.ACTIVE.clear(); relay.OWNER_LAST.clear()
    relay.STATE.get("answered", {}).clear(); GEN.update(calls=0, out={"answer": "salom", "reply": True}, err=None)

def mk_msg(text, chat_type="supergroup", cid=-100, uid=1, mid=500, reply=None, isbot=False):
    m = NS(chat=NS(type=chat_type, id=cid), chat_id=cid, message_id=mid, text=text, caption=None,
           voice=None, photo=None, sticker=None, from_user=NS(id=uid, is_bot=isbot), reply_to_message=reply)
    m.sent = []
    async def rt(t, **k): m.sent.append(t); return NS(message_id=mid + 1)
    m.reply_text = rt
    m.reply_voice = AsyncMock()
    return m
def upd(m): return NS(message=m, effective_message=m)
ctx = NS(bot=bot, args=[])

async def main():
    # --- relay zanjiri
    reset(grp_mode="b", bot_turns=4, bot_delay=0)
    await relay.on_relay(relmsg(11, 1)); await settle()
    check("relay: 1-xabarga javob berdi", len(bot.sent) == 1 and OUT and OUT[-1]["turn"] == 2)
    check("relay: javob peer xabariga reply", bot.sent[0][2].get("reply_parameters") is not None)
    check("relay: peer gapi tarixda '[Reze]: ' bilan", (-100, "user", "[Reze]: salom Makima") in MSGS)
    await relay.on_relay(relmsg(12, 3)); await settle()
    check("relay: 3-xabarga javob (4-xabar)", len(bot.sent) == 2 and OUT[-1]["turn"] == 4)
    await relay.on_relay(relmsg(13, 4)); await settle()
    check("relay: chegara (4) tugagach javob yo'q", len(bot.sent) == 2)
    # dedupe
    reset(grp_mode="b", bot_delay=0)
    await relay.on_relay(relmsg(21, 1, chain="9")); await relay.on_relay(relmsg(21, 1, chain="9")); await settle()
    check("takror tg_msg_id bir marta ishlandi", len(bot.sent) == 1)
    reset(grp_mode="a", bot_delay=0)
    await relay.on_relay(relmsg(31, 1)); await settle()
    check("A rejimda relay javob bermaydi", not bot.sent)
    reset(grp_mode="b", bot_talk=False, bot_delay=0)
    await relay.on_relay(relmsg(32, 1)); await settle()
    check("bot_talk off: javob yo'q", not bot.sent)
    reset(grp_mode="b", bot_delay=0); GEN["out"] = {"answer": "x", "reply": False}
    await relay.on_relay(relmsg(33, 1)); await settle()
    check("model reply=false: jim", not bot.sent)
    reset(grp_mode="b", bot_delay=0); relay.BUSY.add((-100, 77))
    await relay.on_relay(relmsg(34, 1, owner="77")); await settle()
    check("egasi xabari ishlanayotgan bo'lsa relay-javob yo'q", not bot.sent and GEN["calls"] == 0)
    reset(grp_mode="b", bot_delay=0)
    await relay.on_relay(relmsg(35, 1, cid=-999)); await settle()
    check("ruxsatsiz chat e'tiborsiz", not bot.sent and not MSGS)
    reset(grp_mode="b", bot_turns=-1, bot_delay=0)
    await relay.on_relay(relmsg(36, 50)); await settle()
    check("cheksiz (-1): 50-navbatda ham javob", len(bot.sent) == 1)
    reset(-200, grp_mode="b", bot_daily=1, bot_delay=0, bot_turns=99)
    await relay.on_relay(relmsg(41, 1, chain="a", cid=-200)); await settle()
    await relay.on_relay(relmsg(42, 1, chain="b", cid=-200)); await settle()
    check("kunlik chegara 1: ikkinchisi rad", len(bot.sent) == 1)
    reset(grp_mode="b", bot_turns=4)
    await relay.on_relay({"type": "set", "chat_id": -100, "key": "bot_turns", "value": 7}); await settle()
    await relay.on_relay({"type": "set", "chat_id": -100, "key": "proactive", "value": False})
    await relay.on_relay({"type": "set", "chat_id": -555, "key": "bot_turns", "value": 9})
    check("set: ruxsat etilgan kalit yozildi", SETTINGS[-100].get("bot_turns") == 7)
    check("set: boshqa kalit va begona chat e'tiborsiz", "proactive" not in SETTINGS[-100] and -555 not in SETTINGS)
    # --- avto
    reset(grp_mode="b", bot_auto=True, bot_every=60, bot_delay=0)
    import datetime as dt
    now = dt.datetime(2026, 11, 23, 15, 0); relay.STATE.pop("auto_last", None)
    orig_rand = random.random; random.random = lambda: 0.0
    MSGS.append((-100, "user", "salom, qalaysizlar"))  # odam yozgan
    await relay.auto_tick(NS(bot=bot), -100, {}, now); await settle()
    check("avto: gap boshladi, chain auto...", len(bot.sent) == 1 and OUT[-1]["chain"].startswith("auto"))
    await relay.auto_tick(NS(bot=bot), -100, {}, now); await settle()
    check("avto: oraliq tugamaguncha qayta boshlamaydi", len(bot.sent) == 1)
    reset(grp_mode="b", bot_auto=True); relay.STATE.pop("auto_last", None)
    await relay.auto_tick(NS(bot=bot), -100, {}, now)
    check("avto: odam hali yozmagan -> jim", not bot.sent)
    reset(grp_mode="b", bot_auto=True); relay.STATE.pop("auto_last", None)
    MSGS.extend([(-100, "user", "salom"), (-100, "model", "a"), (-100, "user", "[Reze]: b"),
                 (-100, "model", "c"), (-100, "user", "[Reze]: d")])
    await relay.auto_tick(NS(bot=bot), -100, {}, now)
    check("avto: odamdan keyin 4+ bot xabari -> jim", not bot.sent)
    reset(grp_mode="b", bot_auto=False); relay.STATE.pop("auto_last", None)
    MSGS.append((-100, "user", "salom"))
    await relay.auto_tick(NS(bot=bot), -100, {}, now)
    check("avto o'chiq: yozmaydi", not bot.sent)
    reset(grp_mode="b", bot_auto=True); relay.STATE.pop("auto_last", None)
    await relay.auto_tick(NS(bot=bot), -100, {}, dt.datetime(2026, 11, 23, 3, 0))
    check("avto: tungi soatda yozmaydi", not bot.sent)
    random.random = orig_rand

    # --- 9-band: bot-bot zanjiri (qarshi-zanjir, eskirgan zanjir, takror)
    # qarshi-zanjir: ikkala bot egasiga parallel javob bergan; chegara JAMI 4 ta
    reset(grp_mode="b", bot_turns=4, bot_delay=0)
    relay.after_reply(-100, "5", "5", 900, "men egasiga javob berdim"); OUT.clear()
    await relay.on_relay(relmsg(11, 1)); await settle()          # ikkinchi botning parallel javobi
    check("qarshi-zanjir: kelgan xabar ham sanaladi (1+1=2, javob 3-xabar)",
          len(bot.sent) == 1 and OUT[-1]["turn"] == 3)
    await relay.on_relay(relmsg(12, 3)); await settle()
    check("qarshi-zanjir: jami 4 ta bo'lgach to'xtaydi", len(bot.sent) == 1 and relay.CH[(-100, "5")] == 4)
    # servis qayta ishga tushgan: sanoq turn dan tiklanadi
    reset(grp_mode="b", bot_turns=4, bot_delay=0)
    await relay.on_relay(relmsg(13, 4)); await settle()
    check("qayta ishga tushgandan keyin: turn=4 -> chegara, javob yo'q", not bot.sent)
    # eskirgan zanjir: egasi yangi xabar yozgan
    reset(grp_mode="b", bot_delay=0); relay.note_owner(-100, 10)
    await relay.on_relay(relmsg(14, 1, chain="5", owner="5")); await settle()
    check("eskirgan zanjir (egasi keyin yozgan): javob yo'q, Gemini chaqirilmadi",
          not bot.sent and GEN["calls"] == 0)
    check("eskirgan zanjir: peer gapi kontekstga saqlandi", (-100, "user", "[Reze]: salom Makima") in MSGS)
    reset(grp_mode="b", bot_delay=0); relay.note_owner(-100, 5)
    await relay.on_relay(relmsg(15, 1, chain="5", owner="5")); await settle()
    check("zanjir egasining oxirgi xabari bo'lsa: javob beradi", len(bot.sent) == 1)
    # auto zanjir: vaqt bo'yicha
    import time as _t
    reset(grp_mode="b", bot_delay=0); relay.note_owner(-100, 10)
    await relay.on_relay(relmsg(16, 1, chain="auto100", owner="")); await settle()
    check("avto zanjir: odam keyin yozgan -> javob yo'q", not bot.sent)
    reset(grp_mode="b", bot_delay=0); relay.note_owner(-100, 10)
    await relay.on_relay(relmsg(17, 1, chain="auto%d" % (int(_t.time()) + 1000), owner="")); await settle()
    check("avto zanjir: odam oldin yozgan -> javob beradi", len(bot.sent) == 1)
    # Gemini kutilayotganda egasi yozdi: yubormaydi
    reset(grp_mode="b", bot_delay=0)
    _g = relay.gen
    async def gen_then_owner(**kw):
        r = await _g(**kw); relay.note_owner(-100, 99); return r
    relay.gen = gen_then_owner
    await relay.on_relay(relmsg(18, 1, chain="5", owner="5")); await settle()
    relay.gen = _g
    check("Gemini paytida egasi yozdi: javob yuborilmaydi, relay yo'q", not bot.sent and not OUT)
    # Gemini kutilayotganda chegara tugadi
    reset(grp_mode="b", bot_delay=0, bot_turns=2)
    async def gen_then_turns(**kw):
        r = await _g(**kw); relay.CH[(-100, "5")] = 5; return r
    relay.gen = gen_then_turns
    await relay.on_relay(relmsg(19, 1, chain="5", owner="5")); await settle()
    relay.gen = _g
    check("Gemini paytida chegara tugadi: yuborilmaydi", not bot.sent)
    # bir zanjirga ketma-ket ikki relay: bitta javob
    reset(grp_mode="b", bot_delay=0)
    await asyncio.gather(relay.on_relay(relmsg(20, 1)), relay.on_relay(relmsg(21, 2))); await settle()
    check("bir zanjirga ikki relay: bitta javob, bitta Gemini", len(bot.sent) == 1 and GEN["calls"] == 1)
    check("bir zanjirga ikki relay: ikkalasi kontekstda",
          (-100, "user", "[Reze]: salom Makima") in MSGS and not relay.ACTIVE)
    # handle: egasi xabari eslab qolinadi; peer allaqachon javob bergan bo'lsa Gemini chaqirilmaydi
    reset(grp_mode="b", bot_delay=0)
    m = mk_msg("bugun ob-havo juda yaxshi ekan", mid=700)
    await chat.handle(upd(m), ctx); await settle()
    check("handle B: egasi xabari id eslab qolindi", relay.OWNER_LAST.get(-100, (0,))[0] == 700)
    reset(grp_mode="b", bot_delay=0); relay.mark_answered(-100, 701)
    m = mk_msg("bugun ob-havo juda yaxshi ekan", mid=701)
    await chat.handle(upd(m), ctx); await settle()
    check("handle B: peer allaqachon javob bergan -> Gemini chaqirilmadi, gap saqlandi",
          not m.sent and GEN["calls"] == 0 and (-100, "user", m.text) in MSGS and not OUT)
    reset(grp_mode="b", bot_delay=0); relay.mark_answered(-100, 702)
    m = mk_msg("Makima, bugun nima qilamiz", mid=702)
    await chat.handle(upd(m), ctx); await settle()
    check("handle B: murojaat qilinsa peer javob bergan bo'lsa ham javob beradi", m.sent == ["salom"])
    # --- handle (guruh B)
    reset(grp_mode="b", bot_delay=0)
    m = mk_msg("bugun ob-havo juda yaxshi ekan", mid=500)
    await chat.handle(upd(m), ctx); await settle()
    check("handle B: murojaatsiz gap, reply=true -> javob", m.sent == ["salom"])
    check("handle B: relay chain=xabar id, turn=1", OUT and OUT[-1]["chain"] == "500" and OUT[-1]["turn"] == 1)
    check("handle B: BUSY tozalandi", not relay.BUSY)
    reset(grp_mode="b"); GEN["out"] = {"answer": "x", "reply": False}
    m = mk_msg("bugun ob-havo juda yaxshi ekan")
    await chat.handle(upd(m), ctx); await settle()
    check("handle B: reply=false -> jim, gap kontekstda", not m.sent and (-100, "user", m.text) in MSGS and not OUT)
    reset(grp_mode="b")
    m = mk_msg("Reze, bugun nima qilamiz")
    await chat.handle(upd(m), ctx); await settle()
    check("handle B: Reze'ga qaratilgan -> Gemini chaqirilmadi, jim", not m.sent and GEN["calls"] == 0)
    reset(grp_mode="b"); GEN["out"] = {"answer": "ha shu yerdaman", "reply": False}
    m = mk_msg("Makima, salom")
    await chat.handle(upd(m), ctx); await settle()
    check("handle B: Makima'ga qaratilgan -> reply=false bo'lsa ham javob", m.sent == ["ha shu yerdaman"])
    reset(grp_mode="b")
    m = mk_msg("ok")
    await chat.handle(upd(m), ctx); await settle()
    check("handle B: juda qisqa gap -> Gemini chaqirilmadi", not m.sent and GEN["calls"] == 0)
    reset(grp_mode="b"); GEN["err"] = RuntimeError("limit")
    m = mk_msg("bugun nima gap bor ekan")
    await chat.handle(upd(m), ctx); await settle()
    check("handle B: xato bo'lsa murojaatsiz xabarga 'Xatolik' yozmaydi", not m.sent)
    m = mk_msg("Makima, salom")
    await chat.handle(upd(m), ctx); await settle()
    check("handle B: murojaat qilinsa xato haqida yozadi", len(m.sent) == 1)
    reset(grp_mode="a")
    m = mk_msg("Makima, salom")
    await chat.handle(upd(m), ctx); await settle()
    check("handle A rejim: avvalgidek javob, relay yo'q", m.sent == ["salom"] and not OUT)
    reset()
    m = mk_msg("salom", chat_type="private", cid=1)
    await chat.handle(upd(m), ctx); await settle()
    check("shaxsiy chat o'zgarmadi", m.sent == ["salom"] and not OUT)
    # --- guard + rejim
    called = []
    async def inner(u, c): called.append(1)
    g = guard.guarded(inner)
    reset(grp_mode="a"); called.clear()
    await g(upd(mk_msg("bugun yaxshi kun")), ctx)
    check("guard A: murojaatsiz o'tmaydi", not called)
    reset(grp_mode="b"); called.clear()
    await g(upd(mk_msg("bugun yaxshi kun")), ctx)
    check("guard B: murojaatsiz o'tadi", len(called) == 1)
    called.clear()
    await g(upd(mk_msg("bugun yaxshi kun", uid=2)), ctx)
    await g(upd(mk_msg("bugun yaxshi kun", uid=3, isbot=True)), ctx)
    await g(upd(mk_msg("bugun yaxshi kun", cid=-999)), ctx)
    await g(upd(mk_msg("bugun yaxshi kun", chat_type="channel")), ctx)
    check("guard B: boshqa odam, bot, begona guruh, kanal o'tmaydi", not called)
    # --- buyruqlar
    async def run_cmd(fn, text, args, chat_type="supergroup", cid=-100):
        m = mk_msg(text, chat_type=chat_type, cid=cid); c = NS(bot=bot, args=args)
        OUT.clear(); await fn(upd(m), c); await settle(); return m
    reset()
    m = await run_cmd(bcommands.soni_cmd, "/botlar_soni@MiroBot 6", ["6"])
    check("/botlar_soni 6: bazaga yozildi va peerga uzatildi",
          SETTINGS[-100]["bot_turns"] == 6 and OUT and OUT[0] == {"type": "set", "chat_id": -100, "key": "bot_turns", "value": 6})
    await run_cmd(bcommands.soni_cmd, "/botlar_soni@MiroBot cheksiz", ["cheksiz"])
    check("/botlar_soni cheksiz = -1", SETTINGS[-100]["bot_turns"] == -1)
    m = await run_cmd(bcommands.soni_cmd, "/botlar_soni@MiroBot x", ["x"])
    check("/botlar_soni noto'g'ri argument: yordam", "Masalan" in m.sent[0] and SETTINGS[-100]["bot_turns"] == -1)
    await run_cmd(bcommands.rejim_cmd, "/guruh_rejim b", ["b"]); check("/guruh_rejim b", SETTINGS[-100]["grp_mode"] == "b")
    await run_cmd(bcommands.gap_cmd, "/botlar_gap off", ["off"]); check("/botlar_gap off", SETTINGS[-100]["bot_talk"] is False)
    await run_cmd(bcommands.gap_cmd, "/botlar_gap on", ["on"]); check("/botlar_gap on", SETTINGS[-100]["bot_talk"] is True)
    m = await run_cmd(bcommands.gap_cmd, "/botlar_gap yoq", ["yoq"]); check("'yoq' ikki ma'noli: rad etiladi", SETTINGS[-100]["bot_talk"] is True and "on yoki off" in m.sent[0])
    await run_cmd(bcommands.mustaqil_cmd, "x", ["on"]); check("/botlar_mustaqil on", SETTINGS[-100]["bot_auto"] is True)
    await run_cmd(bcommands.oraliq_cmd, "x", ["90"]); check("/botlar_oraliq 90", SETTINGS[-100]["bot_every"] == 90)
    await run_cmd(bcommands.kutish_cmd, "x", ["0"]); check("/botlar_kutish 0 (ruxsat)", SETTINGS[-100]["bot_delay"] == 0)
    await run_cmd(bcommands.kunlik_cmd, "x", ["0"]); check("/botlar_kunlik 0 = cheklovsiz", SETTINGS[-100]["bot_daily"] == 0)
    m = await run_cmd(bcommands.stop_cmd, "x", [])
    check("/botlar_stop: talk va auto o'chdi, ikkala sozlama peerga ketdi",
          SETTINGS[-100]["bot_talk"] is False and SETTINGS[-100]["bot_auto"] is False and len(OUT) == 2)
    m = await run_cmd(bcommands.botlar_cmd, "/botlar@MiroBot", [])
    check("/botlar holat matni", "Guruh sozlamalari" in m.sent[0] and "B (gapga qarab" in m.sent[0])
    m = await run_cmd(bcommands.soni_cmd, "/botlar_soni 3", ["3"], chat_type="private", cid=1)
    check("shaxsiy chatda B buyruq rad etiladi", "guruhda" in m.sent[0] and "bot_turns" not in SETTINGS.get(1, {}))

asyncio.run(main())

# --- server (haqiqiy HTTP)
import server
relay.READY = False
th = threading.Thread(target=server.run_web, daemon=True); th.start()
import time; time.sleep(0.5)
def req(method, path, body=None, secret=None):
    c = http.client.HTTPConnection("127.0.0.1", 18765, timeout=5)
    h = {"Content-Type": "application/json"}
    if secret is not None: h["X-Relay-Secret"] = secret
    c.request(method, path, body=body, headers=h); r = c.getresponse(); return r.status
b = json.dumps({"type": "set", "chat_id": -100, "key": "bot_turns", "value": 11}).encode()
check("server GET ping 200", req("GET", "/") == 200)
check("server: noto'g'ri kalit 403", req("POST", "/relay", b, "xato") == 403)
check("server: kalitsiz 403", req("POST", "/relay", b) == 403)
check("server: tayyor emas 503", req("POST", "/relay", b, "s3cret") == 503)
loop = asyncio.new_event_loop(); threading.Thread(target=loop.run_forever, daemon=True).start()
relay.LOOP = loop; relay.READY = True; relay.STATE["locks"] = {}
check("server: to'g'ri kalit 200", req("POST", "/relay", b, "s3cret") == 200)
time.sleep(0.5)
check("server: relay ishladi (sozlama yozildi)", SETTINGS.get(-100, {}).get("bot_turns") == 11)
check("server: noto'g'ri JSON 400", req("POST", "/relay", b"{{", "s3cret") == 400)
check("server: katta tana 400", req("POST", "/relay", b"x" * 30000, "s3cret") == 400)
check("server: boshqa yo'l 404", req("POST", "/boshqa", b, "s3cret") == 404)
print("JAMI XATO:", fails); sys.exit(1 if fails else 0)
