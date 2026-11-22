# ai.py

```python
"""GEMINI: mijoz, xavfsizlik sozlamalari va gen() (qayta urinish + zaxira model).
"""
import asyncio, os
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

async def gen(models=None, **kw):
    kw.pop("model", None)
    last = None
    for model in (models or FALLBACKS):
        for attempt in range(2):
            try:
                resp = await client.aio.models.generate_content(
                    model=model, **kw)
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
            except Exception as e:
                last = e
                s_ = str(e)
                if "429" in s_ or "RESOURCE_EXHAUSTED" in s_:
                    print("LIMIT, keyingi model:", model, s_[:80])
                    break
                if any(k in s_ for k in
                       ("503", "UNAVAILABLE", "500")):
                    print("QAYTA URINISH:", model, s_[:80])
                    await asyncio.sleep(2 * (attempt + 1))
                    continue
                print("MODEL xato, keyingisi:", model, s_[:80])
                break
    raise last
```
