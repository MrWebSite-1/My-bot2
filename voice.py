"""OVOZ: Edge TTS va Gemini TTS (insoniy ovoz), speak().
"""
import asyncio, base64, io, re
import edge_tts
try:
    import numpy as np
    import soundfile as sf
except Exception:
    np = sf = None
from ai import client
from config import VOICE, EMOJI_RE, GVOICES, GTTS_MODELS, TTS_STYLE

def speech_clean(t):
    t = EMOJI_RE.sub("", t)
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"[*_`#>]", "", t)
    t = re.sub(r"\s*\n+\s*", ". ", t)
    return t.strip()[:1200]

async def tts(text, voice=None, rate=None):
    clean = speech_clean(text)
    if not clean:
        raise ValueError("matn bo'sh")
    comm = edge_tts.Communicate(
        clean, voice or VOICE, rate=rate or "-5%", pitch="+3Hz")
    buf = bytearray()
    async for ch in comm.stream():
        if ch["type"] == "audio":
            buf += ch["data"]
    return bytes(buf)

def _gemini_tts_blocking(text, voice, style):
    last = None
    for model in GTTS_MODELS:
        try:
            it = client.interactions.create(
                model=model,
                input=[{"type": "user_input", "content": [{
                    "type": "text", "text": text,
                    "annotations": [{"type": "speech_metadata",
                                     "style": style}]}]}],
                response_format={"type": "audio",
                                 "mime_type": "audio/l16",
                                 "sample_rate": 24000},
                generation_config={
                    "speech_config": [{"voice": voice}]})
            return base64.b64decode(it.output_audio.data)
        except Exception as e:
            last = e
    raise last

def _encode_voice(pcm):
    arr = np.frombuffer(pcm, dtype="<i2")
    buf = io.BytesIO()
    try:
        sf.write(buf, arr, 24000, format="OGG", subtype="OPUS")
    except Exception as e:
        print("OPUS xato, MP3 sinab ko'riladi:", e)
        buf = io.BytesIO()
        sf.write(buf, arr, 24000, format="MP3")
    return buf.getvalue()

async def tts_gemini(text, st):
    if sf is None:
        raise RuntimeError("soundfile o'rnatilmagan")
    clean = speech_clean(text)
    if not clean:
        raise ValueError("matn bo'sh")
    voice = (st or {}).get("gvoice")
    if voice not in GVOICES:
        voice = "Sulafat"
    style = TTS_STYLE.get((st or {}).get("style") or "muloyim",
                          TTS_STYLE["muloyim"])
    rate = (st or {}).get("rate")
    if rate == "-20%":
        style += ", speaking slowly"
    elif rate == "+20%":
        style += ", speaking a little faster"
    pcm = await asyncio.to_thread(
        _gemini_tts_blocking, clean, voice, style)
    return await asyncio.to_thread(_encode_voice, pcm)

async def speak(text, st):
    st = st or {}
    if (st.get("engine") or "gemini") == "gemini":
        try:
            return await tts_gemini(text, st)
        except Exception as e:
            print("GEMINI TTS xato:", e)
    return await tts(text, st.get("voice"), st.get("rate"))
