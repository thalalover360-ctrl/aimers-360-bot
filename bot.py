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

# 1. Web server for Render Free Tier
async def handle_ping(request):
    return web.Response(text="Aimers 360 running fine!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# 2. Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🎯 *Aimers 360 Active!*\n\n"
        "• Quiz generate karne ke liye: `/quiz <topic ya book>`\n"
        "  _Example:_ `/quiz class 11 black book quadratic equations`\n"
        "• Doubt puchne ke liye mujhe mention karo ya private me text karo!"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    # Agar group hai, toh tabhi bolo jab bot ko tag/reply kiya ho (group spam rokne ke liye)
    is_group = update.message.chat.type in ["group", "supergroup"]
    bot_username = (await context.bot.get_me()).username
    is_mentioned = f"@{bot_username}" in update.message.text if bot_username else False
    is_reply_to_bot = (
        update.message.reply_to_message 
        and update.message.reply_to_message.from_user 
        and update.message.reply_to_message.from_user.id == context.bot.id
    )

    if is_group and not (is_mentioned or is_reply_to_bot):
        return

    clean_text = update.message.text.replace(f"@{bot_username}", "").strip()
    if not clean_text:
        return

    try:
        res = ai_client.models.generate_content(
            model="gemini-3.6-flash",
            contents=f"You are Aimers 360 AI mentor for JEE & Class 10/11 boards. Crisp, clear, friendly in Hinglish. Query: {clean_text}"
        )
        if res and res.text:
            await update.message.reply_text(res.text)
    except Exception:
        pass

async def generate_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    topic = " ".join(context.args) if context.args else "Class 11 Physics Kinematics JEE Advanced"

    status = await update.message.reply_text(f"⚡ Generating quiz: `{topic}`...", parse_mode="Markdown")

    prompt = f"""
    Create 1 tough, conceptual multiple choice question on: '{topic}'.
    Reference level: HC Verma, Irodov, Black Book, or Oswaal Class 10.
    Output strictly raw JSON only (no markdown, no backticks):
    {{
      "question": "Problem text (max 280 chars)",
      "options": ["Opt A", "Opt B", "Opt C", "Opt D"],
      "correct_index": 0,
      "explanation": "Short logic (max 180 chars)"
    }}
    """

    data = None
    # 2 bar direct call karega thode gap ke sath agar Google busy ho
    for attempt in range(2):
        try:
            res = ai_client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt
            )
            if res and res.text:
                raw = res.text.strip()
                raw = re.sub(r"^```(json)?", "", raw).rstrip("`").strip()
                data = json.loads(raw)
                break
        except Exception:
            await asyncio.sleep(2)

    if not data:
        await status.edit_text("⚠️ Google servers par load spike hai. 10 second baad dobara command bhejo!")
        return

    try:
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
        await status.edit_text(f"⚠️ Error formatting poll: {err}")

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

    print("🚀 Aimers 360 live!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
    
