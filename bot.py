import http.server
import json
import os
import socketserver
import sys
import threading
import time
import urllib.parse
import urllib.request


TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_RAW = os.environ.get("ADMIN_ID", "").strip()
PORT = int(os.environ.get("PORT", "10000"))

if not TOKEN:
    print("Missing BOT_TOKEN", file=sys.stderr, flush=True)
    sys.exit(1)

try:
    ADMIN_ID = int(ADMIN_RAW)
except ValueError:
    print("Invalid ADMIN_ID", file=sys.stderr, flush=True)
    sys.exit(1)

API_BASE = f"https://api.telegram.org/bot{TOKEN}"


class HealthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"OK"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def start_web_server():
    server = socketserver.ThreadingTCPServer(("0.0.0.0", PORT), HealthHandler)
    server.daemon_threads = True
    server.serve_forever()


def tg_request(method, params=None):
    url = f"{API_BASE}/{method}"
    data = None
    if params is not None:
        data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=40) as resp:
        return json.loads(resp.read().decode("utf-8"))


def send_message(chat_id, text):
    tg_request("sendMessage", {"chat_id": chat_id, "text": text})


def handle_update(update):
    message = update.get("message") or update.get("edited_message")
    if not message:
        return
    chat = message.get("chat") or {}
    sender = message.get("from") or {}
    chat_id = chat.get("id")
    user_id = sender.get("id")
    text = (message.get("text") or "").strip()

    if chat_id is None or user_id is None:
        return

    if user_id != ADMIN_ID:
        send_message(chat_id, "Unauthorized")
        return

    if text == "/start":
        send_message(chat_id, "Bot is online")
    elif text == "/ping":
        send_message(chat_id, "Pong")
    elif text == "/id":
        send_message(chat_id, f"Admin ID: {ADMIN_ID}")
    else:
        send_message(chat_id, "Commands: /start, /ping, /id")


def poll_loop():
    offset = None
    print("Bot polling started", flush=True)
    while True:
        try:
            params = {"timeout": 30}
            if offset is not None:
                params["offset"] = offset
            res = tg_request("getUpdates", params)
            if res.get("ok"):
                for upd in res.get("result", []):
                    offset = upd["update_id"] + 1
                    handle_update(upd)
            else:
                time.sleep(3)
        except Exception as exc:
            print(f"Poll error: {exc}", file=sys.stderr, flush=True)
            time.sleep(3)


def main():
    print(f"Starting server on port {PORT}", flush=True)
    server_thread = threading.Thread(target=start_web_server, daemon=True)
    server_thread.start()
    poll_loop()


if __name__ == "__main__":
    main()
