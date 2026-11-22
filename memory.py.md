# memory.py

```python
"""UZOQ XOTIRA: faktlarni chiqarish, xulosa yozish, qachon ishga tushishi.
"""
import asyncio, json
from datetime import datetime
from google.genai import types
from ai import gen
from character import NAME
from config import TZ, FALLBACKS, EXTRACT_EVERY, SUMMARY_EVERY
from utils import tier_of, with_tier
from database import (get_recent, list_facts, update_fact, del_fact,
                      save_fact, get_summary, set_summary, count_user)

def norm_item(it):
    if isinstance(it, str):
        return (it.strip()[:200] or None), None
    if isinstance(it, dict):
        f, u = it.get("fact"), it.get("until")
        if isinstance(f, str) and f.strip():
            try:
                datetime.strptime(u, "%Y-%m-%d")
            except Exception:
                u = None
            return f.strip()[:200], u
    return None, None

async def update_facts(cid):
    hist = await asyncio.to_thread(get_recent, cid, 30)
    rows = [r for r in (await asyncio.to_thread(list_facts, cid))
            if not r["fact"].startswith("[odat]")
            and not r["fact"].startswith("[botkayf ")
            and not r["fact"].startswith("[kecha ")
            and not r["fact"].startswith("[kunoxi ")
            and not r["fact"].startswith("[odatrejim] ")][-80:]
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    old = "\n".join(f'{i}. {x["fact"]}'
                    for i, x in enumerate(rows, 1)) or "(hali yo'q)"
    text = "\n".join(h["content"] for h in hist
                     if h["role"] == "user")
    prompt = (
        "Sen foydalanuvchi haqidagi faktlar ro'yxatini "
        "yuritasan. Quyida mavjud raqamlangan faktlar va "
        "foydalanuvchining oxirgi xabarlari.\n\n"
        "DARAJA: har yangi fakt [muhim], [oddiy] yoki [yengil] bilan boshlansin. [muhim]: ism, oila, yaqinlar, muhim sanalar, katta qarorlar, sog'liq va moliya. [oddiy]: hobbi, odat, did, loyiha. [yengil]: bir martalik mayda gaplar va kayfiyat (bularni qo'shma, saqlanmaydi).\n"
        "DOIMIY FAKT: ism va laqab, oila va yaqinlar, ish yoki "
        "o'qish, doimiy qiziqish va hobbi, uzoq muddatli "
        "maqsad va loyihalar, doimiy odat va afzalliklar, "
        "muhim sana.\n"
        "ICHKI HAZIL: foydalanuvchi bilan botning o'rtasidagi takrorlanadigan hazil, laqab, ichki so'z yoki birgalikdagi esdalik. Shunday yoz: 'Ichki hazil: ...'.\n"
        "OCHIQ ISH: foydalanuvchi aytgan, hali natijasi noma'lum narsa (intervyu, imtihon natijasi, shifokor javobi, kutilayotgan qaror). Shunday yoz: 'Ochiq ish: ...'. Natijasi aytilganda o'sha faktni replace yoki delete qil.\n"
        "MUDDATLI FAKT: aniq sanasi bor kelgusi voqea "
        "(imtihon, safar, uchrashuv, topshiriq muddati). "
        "Unga \"until\" qo'sh: voqeadan keyingi kun "
        "(YYYY-MM-DD). Bugungi sana: " + today + ".\n"
        "KIRMAYDI: bir martalik savol; sanasiz vaqtinchalik "
        "holat (kayfiyat, nima yeyotgani); eslatma va "
        "vazifalar; salomlashish; sinov xabarlari; parol, "
        "karta, hujjat ma'lumotlari; taxmin va xulosalar "
        "(faqat aniq aytilgani).\n\n"
        "AMALLAR:\n"
        '- "add": mavjud faktlarda yo\'q yangi fakt.\n'
        '- "replace": foydalanuvchi mavjud faktni aniq '
        "o'zgartirgan yoki yangilagan bo'lsa: "
        '{"n": raqam, "fact": "yangi matn", "until": null}.\n'
        '- "delete": foydalanuvchi mavjud fakt endi to\'g\'ri '
        "emasligini aniq aytgan bo'lsa yoki fakt boshqasining "
        "takrori bo'lsa: raqam.\n"
        "add elementi oddiy matn YOKI "
        '{"fact": "...", "until": "YYYY-MM-DD"} bo\'lishi '
        "mumkin. Bir ma'noli faktni qayta qo'shma. Shubha "
        "bo'lsa hech narsa qilma. Har ro'yxatda ko'pi bilan "
        "3 ta. Har fakt qisqa, bitta gap.\n\n"
        "FAQAT JSON qaytar: "
        '{"add": [], "replace": [], "delete": []}\n\n'
        "Mavjud faktlar:\n" + old +
        "\n\nFoydalanuvchi xabarlari:\n" + text)
    r = await gen(
        models=FALLBACKS[::-1], contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"))
    try:
        d = json.loads(r.text)
    except Exception:
        return
    if not isinstance(d, dict):
        return
    for it in (d.get("replace") or [])[:3]:
        if not isinstance(it, dict):
            continue
        n = it.get("n")
        f, u = norm_item(it)
        if f and isinstance(n, int) and 1 <= n <= len(rows):
            f = with_tier(f, tier_of(rows[n - 1]["fact"]))
        if isinstance(n, int) and 1 <= n <= len(rows) and f:
            await asyncio.to_thread(
                update_fact, cid, rows[n - 1]["id"], f, u)
    for n in (d.get("delete") or [])[:3]:
        if (isinstance(n, int) and 1 <= n <= len(rows)
                and tier_of(rows[n - 1]["fact"]) != "muhim"
                and not rows[n - 1]["fact"].startswith("[holat ")):
            await asyncio.to_thread(
                del_fact, cid, rows[n - 1]["id"])
    have = {x["fact"] for x in rows}
    for it in (d.get("add") or [])[:3]:
        f, u = norm_item(it)
        if f:
            f = with_tier(f, "oddiy")
        if f and tier_of(f) == "yengil":
            continue
        if f and f not in have:
            await asyncio.to_thread(save_fact, cid, f, u)

async def make_summary(cid):
    msgs = await asyncio.to_thread(get_recent, cid, 60)
    old = await asyncio.to_thread(get_summary, cid)
    text = "\n".join(
        ("Foydalanuvchi: " if m["role"] == "user" else NAME + ": ")
        + m["content"] for m in msgs)
    prompt = (
        "Quyida oldingi xulosa va yangi suhbat. Ularni "
        "birlashtirib, foydalanuvchi bilan suhbatlar haqida "
        "yangilangan qisqa xulosa yoz (ko'pi bilan 6 gap, "
        "o'zbek tilida): nimalar haqida gaplashildi, "
        "foydalanuvchi nima bilan band, muhim voqealar, "
        "kayfiyat o'zgarishlari, hal bo'lmagan masalalar. "
        "Mayda tafsilot, salomlashish va bajarilgan "
        "eslatmalarni yozma. Parol, karta kabi maxfiy "
        "narsalarni yozma. Faqat xulosa matnini qaytar.\n\n"
        "Oldingi xulosa: " + (old or "(yo'q)") +
        "\n\nYangi suhbat:\n" + text)
    r = await gen(models=FALLBACKS[::-1], contents=prompt)
    out = (r.text or "").strip()
    if out:
        await asyncio.to_thread(set_summary, cid, out[:1500])

async def maybe_extract(cid):
    n = await asyncio.to_thread(count_user, cid)
    if n == 0:
        return
    if n % EXTRACT_EVERY == 0:
        try:
            await update_facts(cid)
        except Exception as e:
            print("FAKT xato:", e)
    if n % SUMMARY_EVERY == 0:
        try:
            await make_summary(cid)
        except Exception as e:
            print("XULOSA xato:", e)
```
