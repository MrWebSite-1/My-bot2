"""GEMINI: mijoz, xavfsizlik sozlamalari va gen().

gen() vazifalari:
- Yuklamani modellar orasida teng taqsimlash (round-robin): ikkala model ham ishlaydi.
- Bir vaqtda ko'pi bilan MAX_CONC ta so'rov (guruh + lichka + relay to'qnashmasin).
- Har so'rovga vaqt chegarasi (TIMEOUT soniya): osilib qolmaydi.
- 503/500 bo'lsa bir marta qisqa kutib qayta urinish, keyin keyingi model.
- 429 (limit) bo'lsa darhol keyingi model.
- 400 INVALID_ARGUMENT (oxirgi xabar model rolida) bo'lsa bitta "davom eting" qo'shib qayta urinish.
"""
import asyncio, os, itertools
from google import genai
from google.genai import types
from config import FALLBACKS

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

SAFETY = [
    types.SafetySetting(category=c, threshold="BLOCK_NONE")
    for c in ("HARM_CATEGORY_HARASSMENT",
              "HARM_CATEGORY_HATE_SPEECH",
              "HARM_CATEGORY_SEXUALLY_EXPLICIT",
              "HARM_CATEGORY_DANGEROUS_CONTENT")]

MAX_CONC = 2        # bir vaqtda ko'pi bilan shuncha so'rov
TIMEOUT = 40        # bitta so'rov uchun soniya
RETRY_WAIT = 5      # 503 dan keyin kutish
_SEM = asyncio.Semaphore(MAX_CONC)
_RR = itertools.count()


def _order(models):
    """Boshlang'ich modelni aylantirib, yuklamani teng taqsimlaydi."""
    order = list(models)
    if len(order) > 1:
        s = next(_RR) % len(order)
        order = order[s:] + order[:s]
    return order


def _fix_tail(kw):
    """Oxirgi xabar model rolida bo'lsa, 'davom eting' qo'shadi. Qo'shilsa True."""
    c = kw.get("contents")
    if not isinstance(c, list) or not c:
        return False
    last = c[-1]
    if getattr(last, "role", None) != "model":
        return False
    kw["contents"] = list(c) + [types.Content(
        role="user", parts=[types.Part(text="(Davom eting.)")])]
    return True


async def _call(model, kw):
    async with _SEM:
        return await asyncio.wait_for(
            client.aio.models.generate_content(model=model, **kw),
            timeout=TIMEOUT)


async def gen(models=None, **kw):
    kw.pop("model", None)
    last = None
    for model in _order(models or FALLBACKS):
        for attempt in range(2):
            try:
                resp = await _call(model, kw)
                if (resp.text or "").strip():
                    return resp
                fr = None
                try:
                    fr = resp.candidates[0].finish_reason
                except Exception:
                    pass
                print("BLOK/BO'SH:", model, fr,
                      getattr(resp, "prompt_feedback", None))
                last = RuntimeError("BLOK: bo'sh javob")
                break
            except asyncio.TimeoutError:
                last = RuntimeError("Gemini javob bermadi (vaqt tugadi)")
                print("VAQT TUGADI:", model)
                break
            except Exception as e:
                last = e
                s_ = str(e)
                if "429" in s_ or "RESOURCE_EXHAUSTED" in s_:
                    print("LIMIT, keyingi model:", model, s_[:80])
                    break
                if any(k in s_ for k in ("503", "UNAVAILABLE", "500")):
                    print("QAYTA URINISH:", model, s_[:80])
                    if attempt == 0:
                        await asyncio.sleep(RETRY_WAIT)
                        continue
                    break
                if ("400" in s_ or "INVALID_ARGUMENT" in s_) and attempt == 0 \
                        and _fix_tail(kw):
                    print("400: oxiriga 'davom eting' qo'shildi:", model)
                    continue
                print("MODEL xato, keyingisi:", model, s_[:80])
                break
    raise last or RuntimeError("Gemini: hech qanday model ishlamadi")
