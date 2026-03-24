import os
import asyncio
import logging
import httpx
import tempfile
from fastapi import FastAPI, Request, HTTPException
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes
import anthropic
from openai import AsyncOpenAI
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── ENV ──────────────────────────────────────────────────────────────────────
GREEN_API_INSTANCE  = os.environ["GREEN_API_INSTANCE"]
GREEN_API_TOKEN     = os.environ["GREEN_API_TOKEN"]
TELEGRAM_BOT_TOKEN  = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID    = os.environ["TELEGRAM_CHAT_ID"]   # כלילת - chat id שלה בטלגרם
CLAUDE_API_KEY      = os.environ["CLAUDE_API_KEY"]
OPENAI_API_KEY      = os.environ["OPENAI_API_KEY"]
KALIL_PHONE         = "972559272658"                    # מספר הוואטסאפ של כלילת

# ── CLIENTS ──────────────────────────────────────────────────────────────────
claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
tg_app        = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# ── PENDING APPROVALS  { tg_message_id: (wa_chat_id, suggested_reply) } ─────
pending: dict[int, tuple[str, str]] = {}

# ── SYSTEM PROMPT ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """
אתה עוזר וירטואלי מקצועי של כלילת דורי, דיאטנית קלינית.
תפקידך לנסח תשובה מקצועית, חמה וקצרה לפנייה שהתקבלה בוואטסאפ.

הנחיות:
- טון: מקצועי ועסקי אך אנושי וחם
- שפה: עברית
- אורך: עד 3-4 משפטים
- אל תקבל החלטות רפואיות/תזונתיות - הפנה לפגישה
- אם שאלות על מחיר/זמינות - ציין שכלילת תחזור בהקדם עם פרטים
- אם בקשת תיאום פגישה - ציין שכלילת תיצור קשר לתיאום
- חתום תמיד: "כלילת דורי, דיאטנית קלינית 🌿"

דוגמת תשובה לפנייה כללית:
"שלום! תודה על פנייתך 😊 כלילת תחזור אליך בהקדם עם כל הפרטים.
כלילת דורי, דיאטנית קלינית 🌿"
"""

# ── GREENAPI HELPERS ──────────────────────────────────────────────────────────
BASE_URL = f"https://api.green-api.com/waInstance{GREEN_API_INSTANCE}"

async def receive_message() -> dict | None:
    """Pull one notification from Green API queue."""
    url = f"{BASE_URL}/receiveNotification/{GREEN_API_TOKEN}"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url)
        r.raise_for_status()
        data = r.json()
        return data if data else None

async def delete_notification(receipt_id: int):
    url = f"{BASE_URL}/deleteNotification/{GREEN_API_TOKEN}/{receipt_id}"
    async with httpx.AsyncClient(timeout=10) as client:
        await client.delete(url)

async def send_whatsapp(chat_id: str, text: str):
    url = f"{BASE_URL}/sendMessage/{GREEN_API_TOKEN}"
    payload = {"chatId": chat_id, "message": text}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()

async def download_voice(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.content

# ── TRANSCRIPTION ─────────────────────────────────────────────────────────────
async def transcribe_audio(audio_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name
    try:
        with open(tmp_path, "rb") as audio_file:
            transcript = await openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="he"
            )
        return transcript.text
    finally:
        os.unlink(tmp_path)

# ── AI REPLY DRAFT ────────────────────────────────────────────────────────────
async def draft_reply(incoming_text: str) -> str:
    message = claude_client.messages.create(
        model="claude-opus-4-5",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"פנייה שהתקבלה:\n{incoming_text}"}]
    )
    return message.content[0].text

# ── TELEGRAM: שלח לכלילת לאישור ──────────────────────────────────────────────
async def send_for_approval(chat_id: str, sender_name: str, incoming: str, draft: str):
    bot = tg_app.bot
    text = (
        f"📨 *פנייה חדשה בוואטסאפ*\n"
        f"👤 *שולח:* {sender_name}\n\n"
        f"💬 *ההודעה:*\n{incoming}\n\n"
        f"─────────────────\n"
        f"🤖 *תשובה מוצעת:*\n{draft}"
    )
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ שלחי", callback_data="approve"),
            InlineKeyboardButton("✏️ ערכי", callback_data="edit"),
            InlineKeyboardButton("🚫 דלגי", callback_data="skip"),
        ]
    ])
    msg = await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    pending[msg.message_id] = (chat_id, draft)
    logger.info(f"Sent for approval. TG msg_id={msg.message_id}")

# ── TELEGRAM: טיפול בלחיצות כפתור ────────────────────────────────────────────
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    msg_id = query.message.message_id

    if msg_id not in pending:
        await query.edit_message_reply_markup(reply_markup=None)
        return

    wa_chat_id, draft = pending.pop(msg_id)
    action = query.data

    if action == "approve":
        await send_whatsapp(wa_chat_id, draft)
        await query.edit_message_text(query.message.text + "\n\n✅ *נשלח!*", parse_mode="Markdown")

    elif action == "edit":
        # שמור בcontext כדי שכלילת תוכל לשלוח טקסט ידנית
        context.user_data["awaiting_edit"] = (wa_chat_id, msg_id)
        await query.edit_message_text(
            query.message.text + "\n\n✏️ *שלחי את הנוסח הרצוי כהודעה הבאה:*",
            parse_mode="Markdown"
        )

    elif action == "skip":
        await query.edit_message_text(query.message.text + "\n\n🚫 *דולג*", parse_mode="Markdown")

tg_app.add_handler(CallbackQueryHandler(button_handler))

# ── PROCESS INCOMING WHATSAPP MESSAGE ────────────────────────────────────────
async def process_notification(data: dict):
    body = data.get("body", {})
    msg_type = body.get("typeWebhook")

    # רק הודעות נכנסות מלקוחות (לא ממסגרת עצמה)
    if msg_type not in ("incomingMessageReceived",):
        return

    sender_data = body.get("senderData", {})
    sender_jid  = sender_data.get("chatId", "")
    sender_name = sender_data.get("senderName", sender_jid)

    # לא להגיב לעצמנו
    if sender_jid.startswith(KALIL_PHONE):
        return

    msg_data    = body.get("messageData", {})
    msg_subtype = msg_data.get("typeMessage")
    incoming_text = ""

    if msg_subtype == "textMessage":
        incoming_text = msg_data.get("textMessageData", {}).get("textMessage", "")

    elif msg_subtype == "audioMessage":
        # הורד ותמלל
        audio_url = msg_data.get("fileMessageData", {}).get("downloadUrl", "")
        if audio_url:
            try:
                audio_bytes   = await download_voice(audio_url)
                incoming_text = await transcribe_audio(audio_bytes)
                incoming_text = f"[הקלטה קולית] {incoming_text}"
            except Exception as e:
                logger.error(f"Transcription failed: {e}")
                incoming_text = "[הקלטה קולית — לא ניתן לתמלל]"

    elif msg_subtype == "extendedTextMessage":
        incoming_text = msg_data.get("extendedTextMessageData", {}).get("text", "")

    if not incoming_text.strip():
        return

    logger.info(f"Incoming from {sender_name}: {incoming_text[:80]}")

    try:
        draft = await draft_reply(incoming_text)
        await send_for_approval(sender_jid, sender_name, incoming_text, draft)
    except Exception as e:
        logger.error(f"Failed to draft/send approval: {e}")

# ── POLLING LOOP (fallback אם Webhook לא זמין) ────────────────────────────────
async def polling_loop():
    logger.info("Starting Green API polling loop...")
    while True:
        try:
            notif = await receive_message()
            if notif:
                receipt_id = notif.get("receiptId")
                await process_notification(notif)
                if receipt_id:
                    await delete_notification(receipt_id)
            else:
                await asyncio.sleep(3)
        except Exception as e:
            logger.error(f"Polling error: {e}")
            await asyncio.sleep(5)

# ── FASTAPI (Webhook endpoint לGreen API) ─────────────────────────────────────
app = FastAPI()

@app.post("/webhook")
async def webhook(request: Request):
    try:
        data = await request.json()
        asyncio.create_task(process_notification({"body": data}))
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "alive"}

# ── STARTUP ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    await tg_app.initialize()
    await tg_app.start()
    # הפעל polling בbackground
    asyncio.create_task(polling_loop())
    # הפעל את ה-Telegram updater
    asyncio.create_task(tg_app.updater.start_polling())
    logger.info("Bot started ✅")

@app.on_event("shutdown")
async def shutdown():
    await tg_app.stop()

if __name__ == "__main__":
    import uvicorn
    import os
    
    port = int(os.environ.get("PORT", 8080))
    
    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info")
