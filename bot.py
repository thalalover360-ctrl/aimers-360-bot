import asyncio
import json
import os
import re
from aiohttp import web
from google import genai
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

ai_client = genai.Client(api_key=GEMINI_KEY)

# 1. Dummy Web Server (Render Free Tier)
async def handle_ping(request):
    return web.Response(text="Aimers 360 is Running Fast!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Server started on port {port}")

# 2. Telegram Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🎯 *Aimers 360 - Superfast Academic Bot!*\n\n"
        "• Quiz ke liye: `/quiz <topic ya book>`\n"
        "  _Examples:_ `/quiz irodov relative motion`, `/quiz hc verma friction`, `/quiz class 10 light`\n"
        "• Doubts ya chat ke liye: Seedha message type karo!"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# Fast AI Chat (Sirf 3.6 aur 3)
async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    user_text = update.message.text

    chat_prompt = f"You are Aimers 360 AI mentor for JEE & Class 10/11 boards. Crisp, sharp, helpful in Hinglish/English. User: {user_text}"
    
    reply_text = None
    for model_name in ["gemini-3.6-flash", "gemini-3-flash"]:
        try:
            res = ai_client.models.generate_content(
                model=model_name,
                contents=chat_prompt
            )
            if res and res.text:
                reply_text = res.text
                break
        except Exception:
            continue

    if reply_text:
        await update.message.reply_text(reply_text)
    else:
        await update.message.reply_text("Ek second, dobara send karo!")

# Fast Quiz Handler (Sirf 3.6 aur 3, Zero Delay)
async def generate_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    topic = " ".join(context.args) if context.args else "Class 11 Physics Kinematics JEE Advanced"

    status = await update.message.reply_text(f"⚡ Generating quiz for `{topic}`...", parse_mode="Markdown")

    prompt = f"""
    Create 1 tough, conceptual multiple choice question for: '{topic}'.
    Reference level: HC Verma, Irodov, Black Book, or Oswaal Class 10.
    Output strictly raw JSON only (no markdown formatting, no code fences):
    {{
      "question": "Problem text (max 280 chars)",
      "options": ["Opt A", "Opt B", "Opt C", "Opt D"],
      "correct_index": 0,
      "explanation": "Short logic (max 180 chars)"
    }}
    """

    res_text = None
    last_err = None

    # Sirf 3.6 aur 3 me switch karega
    for model_name in ["gemini-3.6-flash", "gemini-3-flash"]:
        try:
            res = ai_client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            if res and res.text:
                res_text = res.text
                break
        except Exception as e:
            last_err = e
            continue

    if not res_text:
        await status.edit_text(f"⚠️ Server thoda busy hai: {last_err}")
        return

    try:
        raw = res_text.strip()
        raw = re.sub(r"^```(json)?", "", raw).rstrip("`").strip()
        data = json.loads(raw)

        await context.bot.send_poll(
            chat_id=chat_id,
            question=data["question"][:300],
            options=[opt[:100] for opt in data["options"][:4]],
            type="quiz",
            correct_option_id=int(data["correct_index"]),
            explanation=data["explanation"][:200],
            open_period=60
        )
        await status.delete()

    except Exception as err:
        await status.edit_text(f"⚠️ Error: {err}")

# 3. Main Runner
async def main():
    await start_web_server()

    tg_app = ApplicationBuilder().token(BOT_TOKEN).build()
    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(CommandHandler("quiz", generate_quiz))
    tg_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), chat_handler))

    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling()

    print("🚀 Aimers 360 is live!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
    
