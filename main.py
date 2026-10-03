import os
import re
from fastapi import FastAPI, Request, Response, Query
from deep_translator import GoogleTranslator
import httpx

app = FastAPI(title="What They Say Ah")

WHATSAPP_TOKEN = os.getenv("WHATSAPP_CLOUD_API_TOKEN")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN")

LANG_MAP = {
    "zh": "chinese (simplified)",
    "ms": "malay",
    "ta": "tamil",
    "en": "english",
    "es": "spanish",
    "fr": "french",
    "de": "german",
    "ja": "japanese",
    "ko": "korean",
    "th": "thai",
    "vi": "vietnamese",
    "id": "indonesian",
}

@app.get("/")
def home():
    return {"bot": "What They Say Ah", "status": "running"}

# 1. Verification handshake for Meta Webhook setup
@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(status_code=403)

# 2. Inbound WhatsApp message receiver
@app.post("/webhook")
async def receive_message(request: Request):
    data = await request.json()
    
    try:
        entry = data.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if messages:
            msg = messages[0]
            if msg.get("type") == "text":
                sender = msg["from"]
                text = msg["text"]["body"].strip()
                translated_response = translate_input(text)
                await send_whatsapp_reply(sender, translated_response)
    except Exception as e:
        print(f"Error handling event: {e}")

    return {"status": "ok"}

def translate_input(text: str) -> str:
    # Match pattern: /<lang_code> <message>
    slash_match = re.match(r"^/([a-zA-Z]{2})\s+(.+)$", text, re.DOTALL)
    if slash_match:
        target_code = slash_match.group(1).lower()
        content = slash_match.group(2)
        target_lang = LANG_MAP.get(target_code, target_code)
        try:
            res = GoogleTranslator(source="auto", target=target_lang).translate(content)
            return f"🌐 *What They Say Ah [{target_lang.capitalize()}]:*\n{res}"
        except Exception as e:
            return f"⚠ Alamak, translation error: {str(e)}"

    # Greeting / Help command
    if text.lower() in ["help", "/help", "hi", "hello", "start"]:
        return (
            "👋 *What They Say Ah* — Translation Bot\n\n"
            "Cannot understand? Don't panic. Prefix your text with a language code:\n\n"
            "• `/zh [text]` — Translate to Chinese\n"
            "• `/ms [text]` — Translate to Malay\n"
            "• `/ta [text]` — Translate to Tamil\n"
            "• `/en [text]` — Translate to English\n"
            "• `/ja [text]` — Translate to Japanese\n"
            "• `/ko [text]` — Translate to Korean\n"
            "• `/es [text]` — Translate to Spanish\n"
            "• `/fr [text]` — Translate to French\n\n"
            "_Example:_\n`/zh Where is the nearest MRT station?`"
        )

    # Fallback: Translate whatever was sent into English
    try:
        res = GoogleTranslator(source="auto", target="english").translate(text)
        return f"🌐 *What They Say Ah [English]:*\n{res}"
    except Exception:
        return "Type `/help` to view language codes, or prefix with `/en`, `/zh`, etc."

async def send_whatsapp_reply(recipient_id: str, text: str):
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient_id,
        "type": "text",
        "text": {"body": text},
    }
    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload, headers=headers)
