"""BAZA (Supabase): xabarlar, faktlar, eslatmalar, sozlamalar, xulosa.
"""
import os
from datetime import datetime, timezone, timedelta
from supabase import create_client
from config import UTC_FMT, TZ, HISTORY, KEEP_DAYS

db = create_client(os.environ["SUPABASE_URL"],
                   os.environ["SUPABASE_KEY"])

def get_history(cid):
    r = (db.table("messages").select("role,content,created_at")
         .eq("chat_id", cid).order("id", desc=True)
         .limit(HISTORY).execute())
    return list(reversed(r.data))

def get_facts(cid):
    r = (db.table("facts").select("fact")
         .eq("chat_id", cid).order("id", desc=True)
         .limit(60).execute())
    return [x["fact"] for x in reversed(r.data)]

def save_msg(cid, role, content):
    db.table("messages").insert(
        {"chat_id": cid, "role": role,
         "content": content}).execute()

def count_user(cid):
    r = (db.table("messages").select("id", count="exact")
         .eq("chat_id", cid).eq("role", "user").execute())
    return r.count or 0

def save_fact(cid, fact, until=None):
    row = {"chat_id": cid, "fact": fact}
    if until:
        row["expires_at"] = until
    db.table("facts").insert(row).execute()

def wipe(cid):
    db.table("messages").delete().eq("chat_id", cid).execute()
    db.table("facts").delete().eq("chat_id", cid).execute()
    (db.table("settings").update({"summary": None})
     .eq("chat_id", cid).execute())

def save_reminder(cid, task, when_utc, repeat=None):
    row = {"chat_id": cid, "task": task, "remind_at": when_utc}
    if repeat:
        row["repeat"] = repeat
    db.table("reminders").insert(row).execute()

def due_reminders():
    now = datetime.now(timezone.utc).strftime(UTC_FMT)
    r = (db.table("reminders")
         .select("id,chat_id,task,remind_at,repeat")
         .eq("done", False).lte("remind_at", now).execute())
    return r.data

def get_reminder(rid):
    r = (db.table("reminders").select("chat_id,task")
         .eq("id", rid).execute())
    return r.data[0] if r.data else None

def next_time(t, repeat):
    now = datetime.now(timezone.utc)
    while t <= now:
        t += timedelta(days=7 if repeat == "weekly" else 1)
        if repeat == "weekdays":
            while t.astimezone(TZ).weekday() >= 5:
                t += timedelta(days=1)
    return t

def advance(rid, remind_at, repeat):
    t = datetime.fromisoformat(remind_at.replace("Z", "+00:00"))
    nt = next_time(t, repeat)
    (db.table("reminders")
     .update({"remind_at": nt.strftime(UTC_FMT)})
     .eq("id", rid).execute())

def mark_done(rid):
    db.table("reminders").update(
        {"done": True}).eq("id", rid).execute()

def pending(cid):
    r = (db.table("reminders").select("id,task,remind_at,repeat")
         .eq("chat_id", cid).eq("done", False)
         .order("remind_at").execute())
    return r.data

def del_rem(cid, rid):
    (db.table("reminders").delete()
     .eq("id", rid).eq("chat_id", cid).execute())

def ensure_settings(cid):
    db.table("settings").upsert(
        {"chat_id": cid}, on_conflict="chat_id",
        ignore_duplicates=True).execute()

def proactive_chats():
    try:
        r = (db.table("settings").select(
                "chat_id,last_slot,pro_min,pro_max,pro_gap,pro_from,pro_to,jimlik_h")
             .eq("proactive", True).execute())
    except Exception as e:
        print("Yozish ustunlari yo'q (SQL'ni ishga tushiring):", e)
        r = (db.table("settings").select("chat_id,last_slot")
             .eq("proactive", True).execute())
    return r.data

def set_slot(cid, slot):
    (db.table("settings").update({"last_slot": slot})
     .eq("chat_id", cid).execute())

def set_proactive(cid, on):
    db.table("settings").upsert(
        {"chat_id": cid, "proactive": on},
        on_conflict="chat_id").execute()

def get_recent(cid, limit):
    r = (db.table("messages").select("role,content,created_at")
         .eq("chat_id", cid).order("id", desc=True)
         .limit(limit).execute())
    return list(reversed(r.data))

def get_summary(cid):
    r = (db.table("settings").select("summary")
         .eq("chat_id", cid).execute())
    return (r.data[0].get("summary") or "") if r.data else ""

def set_summary(cid, text):
    (db.table("settings").update({"summary": text})
     .eq("chat_id", cid).execute())

BOT_OPEN_TAG = "Ochiq ish (bot): "


OPEN_MAX = 3  # lichkada bir vaqtda ko'pi bilan shuncha bot ochiq ishi


def set_open_topic(cid, text):
    """Bot lichkada bergan savolni 24 soatga 'ochiq ish' sifatida saqlaydi.
    Ko'pi bilan OPEN_MAX ta; eng eskisi o'chadi. Bir xili ikki marta yozilmaydi."""
    rows = (db.table("facts").select("id,fact").eq("chat_id", cid)
            .like("fact", BOT_OPEN_TAG + "%").order("id").execute()).data or []
    if any(r["fact"] == BOT_OPEN_TAG + text for r in rows):
        return
    until = (datetime.now(timezone.utc) + timedelta(hours=24)).strftime(UTC_FMT)
    save_fact(cid, BOT_OPEN_TAG + text, until)
    extra = rows[:max(0, len(rows) + 1 - OPEN_MAX)]
    for r in extra:
        db.table("facts").delete().eq("id", r["id"]).execute()


def clear_open_topics(cid):
    """Faqat bot yaratgan ochiq ishlarni o'chiradi (xotiradagilarga tegmaydi)."""
    (db.table("facts").delete().eq("chat_id", cid)
     .like("fact", BOT_OPEN_TAG + "%").execute())


def update_fact(cid, fid, text, until=None):
    (db.table("facts")
     .update({"fact": text, "expires_at": until})
     .eq("id", fid).eq("chat_id", cid).execute())

def cleanup_db():
    now = datetime.now(timezone.utc)
    (db.table("facts").delete()
     .lt("expires_at", now.strftime(UTC_FMT)).execute())
    old = (now - timedelta(days=KEEP_DAYS)).strftime(UTC_FMT)
    (db.table("messages").delete()
     .lt("created_at", old).execute())

def list_facts(cid):
    r = (db.table("facts").select("id,fact,expires_at")
         .eq("chat_id", cid).order("id").execute())
    return r.data

def del_fact(cid, fid):
    (db.table("facts").delete()
     .eq("id", fid).eq("chat_id", cid).execute())

def get_settings(cid):
    r = (db.table("settings").select("*")
         .eq("chat_id", cid).execute())
    return r.data[0] if r.data else {}

def update_setting(cid, key, value):
    db.table("settings").upsert(
        {"chat_id": cid, key: value},
        on_conflict="chat_id").execute()

def last_user_time(cid):
    r = (db.table("messages").select("created_at")
         .eq("chat_id", cid).eq("role", "user")
         .order("id", desc=True).limit(1).execute())
    if not r.data or not r.data[0].get("created_at"):
        return None
    return datetime.fromisoformat(
        r.data[0]["created_at"].replace("Z", "+00:00"))


def messages_between(cid, start, end):
    r = (db.table("messages").select("role,content,created_at")
         .eq("chat_id", cid).gte("created_at", start).lt("created_at", end)
         .order("id").execute())
    return r.data or []


def count_user_messages(cid):
    r = (db.table("messages").select("id", count="exact")
         .eq("chat_id", cid).eq("role", "user").limit(1).execute())
    return r.count or 0

# Sanali voqea haqida keyin so'rash: eslatma task'i shu belgi bilan boshlanadi
ASK_TAG = "[so'ra] "
