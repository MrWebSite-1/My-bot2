# server.py

```python
"""PING SERVER + RELAY: Render uxlab qolmasligi uchun ping (GET).
POST /relay: B variantda ikkinchi botdan xabar qabul qiladi (yashirin kalit bilan).
"""
import asyncio, hmac, json, os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

class Ping(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")
    do_HEAD = do_GET

    def _reply(self, code, body):
        self.send_response(code)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path.split("?")[0] != "/relay":
            return self._reply(404, b"no")
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0 or n > 20000:
            return self._reply(400, b"bad")
        body = self.rfile.read(n)
        from config import RELAY_SECRET
        got = self.headers.get("X-Relay-Secret") or ""
        if not RELAY_SECRET or not hmac.compare_digest(
                got.encode(), RELAY_SECRET.encode()):
            return self._reply(403, b"no")
        try:
            data = json.loads(body)
            if not isinstance(data, dict):
                raise ValueError
        except Exception:
            return self._reply(400, b"bad")
        import relay
        if not relay.READY:
            return self._reply(503, b"wait")
        asyncio.run_coroutine_threadsafe(relay.on_relay(data), relay.LOOP)
        self._reply(200, b"ok")

    def log_message(self, *a):
        pass

def run_web():
    port = int(os.environ.get("PORT", 10000))
    ThreadingHTTPServer(("0.0.0.0", port), Ping).serve_forever()
```
